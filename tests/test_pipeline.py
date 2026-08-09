# -*- coding: utf-8 -*-
"""اختباراتُ حرّاسِ النزاهةِ والطزاجةِ في الأنبوب.

`daily_anchor.py` سكربتٌ تسلسليٌّ يُنفَّذُ كاملًا عند الاستيراد (يجلبُ من الشبكةِ
ويكتبُ ملفّات)، فلا يصحُّ استيرادُه في اختبار. لذلك نستخرجُ الدوالَّ النقيّةَ
بتحليلِ AST ونُنفّذُها في نطاقٍ معزول — فنختبرُ منطقَ الحراسةِ وحدَه بلا أيِّ
أثرٍ جانبيّ ولا نداءِ شبكة.
"""
import ast
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = os.path.join(ROOT, "pipeline", "daily_anchor.py")
SRC = open(SRC_PATH, encoding="utf-8").read()
TREE = ast.parse(SRC)


def load(names, extra=None):
    """يُنفّذُ تعريفاتٍ عليا (دوالَّ أو ثوابت) بأسمائِها، بترتيبِ ورودِها في الملفّ."""
    want = set(names)
    g = {"re": re, "os": os, "json": json, "sys": sys,
         "datetime": datetime, "timezone": timezone, "timedelta": timedelta}
    g.update(extra or {})
    for node in TREE.body:
        got = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            got = node.name
        elif isinstance(node, ast.Assign):
            tg = [t.id for t in node.targets if isinstance(t, ast.Name)]
            got = tg[0] if tg else None
        if got in want:
            exec(compile(ast.Module([node], []), SRC_PATH, "exec"), g)
    missing = want - set(g)
    if missing:
        raise AssertionError("تعذّر استخراج: " + ", ".join(sorted(missing)))
    return g


def iso_ago(**kw):
    return (datetime.now(timezone.utc) - timedelta(**kw)).isoformat(timespec="minutes")


class TestSourceGrading(unittest.TestCase):
    """درجةُ المنفذِ هي أساسُ الإسناد — لا يُنشَرُ ما لا يُسنَد."""

    def setUp(self):
        self.g = load(["TIER1", "TIER2", "grade"])

    def test_tier1_is_sahih(self):
        self.assertEqual(self.g["grade"]("reuters"), "صحيح")

    def test_unknown_outlet_is_unsourced(self):
        self.assertEqual(self.g["grade"]("some-random-blog.example"), "غير مُسند")

    def test_grade_returns_only_known_labels(self):
        for s in ("kuna.net.kw", "العربية", "مدونة مجهولة", ""):
            self.assertIn(self.g["grade"](s), ("صحيح", "حسن", "غير مُسند"))


class TestFreshnessGate(unittest.TestCase):
    """حارسُ الطزاجة: لا تُنشَرُ مادّةٌ قديمةٌ بوصفِها خبرَ اليوم."""

    def setUp(self):
        self.g = load(["FRESH_MAX_H", "_STALE_DROP", "_too_old", "_age_h"])

    def test_recent_item_kept(self):
        self.assertFalse(self.g["_too_old"](iso_ago(hours=2)))

    def test_ancient_item_dropped(self):
        self.assertTrue(self.g["_too_old"]("2024-05-01T10:00+00:00"))

    def test_item_just_past_window_dropped(self):
        self.assertTrue(self.g["_too_old"](iso_ago(hours=80)))

    def test_item_inside_window_kept(self):
        self.assertFalse(self.g["_too_old"](iso_ago(hours=60)))

    def test_missing_timestamp_is_not_dropped(self):
        # لا نُسقِطُ ما لا نملكُ إثباتَ قِدَمِه
        self.assertFalse(self.g["_too_old"](""))
        self.assertFalse(self.g["_too_old"](None))

    def test_age_h_unparseable_is_none(self):
        self.assertIsNone(self.g["_age_h"]("ليس تاريخًا"))
        self.assertIsNone(self.g["_age_h"](""))


class TestAlertStaleness(unittest.TestCase):
    """التحذيرُ السياديُّ لا يُنشَرُ بتاريخٍ غامضٍ ولا قديم."""

    def setUp(self):
        self.g = load(["_KW", "_AR_MON", "_stmt_old_days", "_vague_when", "_alert_stale"])

    def test_vague_month_only_is_vague(self):
        self.assertTrue(self.g["_vague_when"]("يوليو 2026"))

    def test_explicit_day_is_not_vague(self):
        self.assertFalse(self.g["_vague_when"]("18 يوليو 2026"))

    def test_no_month_name_is_not_vague(self):
        self.assertFalse(self.g["_vague_when"]("اليوم"))

    def test_vague_alert_is_stale(self):
        self.assertTrue(self.g["_alert_stale"]({"when": "يوليو 2026", "cap": iso_ago(hours=1)}))

    def test_old_capture_stamp_is_stale(self):
        self.assertTrue(self.g["_alert_stale"]({"when": "اليوم", "cap": iso_ago(hours=60)}))

    def test_fresh_capture_survives(self):
        self.assertFalse(self.g["_alert_stale"]({"when": "اليوم", "cap": iso_ago(hours=1)}))


class TestUrlGuard(unittest.TestCase):
    def setUp(self):
        self.g = load(["_ok_url"])

    def test_https_ok(self):
        self.assertTrue(self.g["_ok_url"]("https://kuna.net.kw/x"))

    def test_non_http_rejected(self):
        for bad in ("javascript:alert(1)", "", None, "ftp://x/y"):
            self.assertFalse(self.g["_ok_url"](bad))


class TestAgentFailureReporting(unittest.TestCase):
    """الدرس: وكيلٌ يبتلعُ استثناءَه كان يُنشَرُ «سليمًا» — فبقيَ قسمٌ ميّتًا
    ٦ أيّامٍ واللوحةُ تقول ١٩/١٩. الآن يُبلِّغُ بـ{"failed":1} فيُسجَّلُ fail."""

    def setUp(self):
        self.log = {}
        self.g = load(["agent", "mark"], extra={
            "_LOG": self.log, "PAUSED": set(), "time": __import__("time")})

    def test_failed_signal_marks_fail(self):
        @self.g["agent"]("tester")
        def boom():
            return {"failed": 1, "why": "الشبكةُ انقطعت"}
        boom()
        self.assertEqual(self.log["tester"]["status"], "fail")
        self.assertIn("الشبكة", self.log["tester"]["note"])

    def test_skipped_signal_marks_skip(self):
        @self.g["agent"]("tester2")
        def skip():
            return {"skipped": 1, "why": "نوبته لاحقًا"}
        skip()
        self.assertEqual(self.log["tester2"]["status"], "skip")

    def test_plain_return_is_ok(self):
        @self.g["agent"]("tester3")
        def fine():
            return {"why": "تمّ"}
        fine()
        self.assertEqual(self.log["tester3"]["status"], "ok")

    def test_uncaught_exception_still_fails(self):
        @self.g["agent"]("tester4")
        def raiser():
            raise ValueError("انفجار")
        raiser()
        self.assertEqual(self.log["tester4"]["status"], "fail")


class TestHealthWatchdog(unittest.TestCase):
    """الحِراسة تقيسُ النتيجةَ (عُمر + عدد) لا نجاحَ التشغيل."""

    def _run(self, files):
        d = tempfile.mkdtemp()
        for name, doc in files.items():
            with open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False)
        log = {}
        g = load(["_age_h", "_count_items", "_HEALTH_SPEC", "_HEALTH_DORMANT", "hirasa"], extra={
            "OUT": d, "HEALTH_F": os.path.join(d, "health.json"),
            "_LOG": log, "_AUX": {},
            "mark": lambda a, s="ok", n="": log.__setitem__(a, {"status": s, "note": n}),
        })
        g["hirasa"]()
        with open(os.path.join(d, "health.json"), encoding="utf-8") as fh:
            return json.load(fh), log

    def test_fresh_section_is_fresh(self):
        h, _ = self._run({"news": {"updated": iso_ago(minutes=10),
                                   "cats": {"عاجل": [{"h": i} for i in range(20)]}}})
        news = [s for s in h["sections"] if s["key"] == "news"][0]
        self.assertEqual(news["state"], "fresh")
        self.assertEqual(news["items"], 20)

    def test_stale_section_flagged_and_owner_marked(self):
        h, log = self._run({"alerts": {"updated": iso_ago(hours=140), "list": []}})
        al = [s for s in h["sections"] if s["key"] == "alerts"][0]
        self.assertIn(al["state"], ("stale", "dead"))
        self.assertIn("munabbih", log)          # الوكيلُ المالكُ لم يعُدْ «سليمًا»
        self.assertNotEqual(h["overall"], "ok")

    def test_missing_file_is_dead(self):
        h, log = self._run({})
        live = [s for s in h["sections"] if s["key"] not in ("corrections", "verify")]
        self.assertTrue(live)
        self.assertTrue(all(s["state"] == "dead" for s in live))
        # حتى الغيابُ الكاملُ للملفِّ لا يُحوِّلُ الخامدَ إلى اتّهامٍ لوكيلِه
        for key, owner in (("verify", "mutabiq"), ("corrections", "rasid")):
            sec = [s for s in h["sections"] if s["key"] == key][0]
            self.assertEqual(sec["state"], "dormant")
            self.assertNotIn(owner, log)

    def test_dormant_sections_are_declared_not_blamed(self):
        """قسمٌ مُغذّيه مُعطَّلٌ عمدًا يُعلَنُ «خامدًا» ولا يُتَّهَمُ به وكيلُه."""
        h, log = self._run({"verify": {"updated": iso_ago(hours=24 * 16), "rows": []},
                            "corrections": {"updated": iso_ago(hours=24 * 18), "log": []}})
        for key, owner in (("verify", "mutabiq"), ("corrections", "rasid")):
            sec = [s for s in h["sections"] if s["key"] == key][0]
            self.assertEqual(sec["state"], "dormant")     # يُقالُ ولا يُخفى
            self.assertNotIn(owner, log)                  # ولا يُحاسَبُ عليه وكيلُه

    def test_dormant_does_not_mask_a_real_outage(self):
        """الخمودُ لا يبتلعُ عطلًا حقيقيًّا في قسمٍ عامل."""
        h, log = self._run({"verify": {"updated": iso_ago(hours=24 * 16), "rows": []},
                            "alerts": {"updated": iso_ago(hours=140), "list": []}})
        self.assertNotEqual(h["overall"], "ok")
        self.assertIn("munabbih", log)
        self.assertEqual(h["overall"], "dead")

    def test_empty_below_minimum_is_flagged(self):
        h, _ = self._run({"news": {"updated": iso_ago(minutes=5), "cats": {"عاجل": []}}})
        news = [s for s in h["sections"] if s["key"] == "news"][0]
        self.assertEqual(news["state"], "empty")

    def test_count_items_handles_shapes(self):
        g = load(["_count_items"])
        self.assertEqual(g["_count_items"]({"list": [1, 2, 3]}, "list"), 3)
        self.assertEqual(g["_count_items"]({"cats": {"a": [1], "b": [2, 3]}}, "cats"), 3)
        self.assertIsNone(g["_count_items"]({"x": 1}, None))


class TestGeminiBilling(unittest.TestCase):
    """الدرس: bill() يقرأ حقلَ xAI وحدَه، فبقيَ كلُّ إنفاقِ Gemini خارجَ سقفِ اليوم."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.g = load(["GEM_IN_PER_M", "GEM_OUT_PER_M", "bill_gem"], extra={"OUT": self.d})

    def _cost(self):
        with open(os.path.join(self.d, "cost.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_tokens_become_usd_in_the_same_ledger(self):
        usd = self.g["bill_gem"]({"usageMetadata": {
            "promptTokenCount": 1_000_000, "candidatesTokenCount": 0}}, "اختبار")
        self.assertAlmostEqual(usd, self.g["GEM_IN_PER_M"], places=6)
        self.assertGreater(self._cost()["usd"], 0)

    def test_output_tokens_priced_higher(self):
        out = self.g["bill_gem"]({"usageMetadata": {
            "promptTokenCount": 0, "candidatesTokenCount": 1_000_000}}, "اختبار")
        self.assertAlmostEqual(out, self.g["GEM_OUT_PER_M"], places=6)

    def test_thinking_tokens_counted(self):
        self.g["bill_gem"]({"usageMetadata": {
            "promptTokenCount": 10, "candidatesTokenCount": 10, "thoughtsTokenCount": 500}}, "اختبار")
        self.assertEqual(self._cost()["gem_tokens"], 520)

    def test_response_without_usage_is_free(self):
        self.assertEqual(self.g["bill_gem"]({}, "اختبار"), 0)
        self.assertEqual(self.g["bill_gem"]({"candidates": []}, "اختبار"), 0)

    def test_accumulates_across_calls(self):
        for _ in range(3):
            self.g["bill_gem"]({"usageMetadata": {"promptTokenCount": 1000}}, "اختبار")
        self.assertEqual(self._cost()["calls"], 3)


class TestCorrespondents(unittest.TestCase):
    """مراسلٌ لكلِّ دولةٍ لها موادُّ مُسنَدةٌ اليوم — حتميّ، ويتقاعدُ تلقائيًّا."""

    def _run(self, countries, existing=None):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "map.json"), "w", encoding="utf-8") as fh:
            json.dump({"countries": countries}, fh, ensure_ascii=False)
        if existing is not None:
            with open(os.path.join(d, "agents_dynamic.json"), "w", encoding="utf-8") as fh:
                json.dump({"updated": "t", "agents": existing}, fh, ensure_ascii=False)
        env = dict(os.environ, SANAD_DAILY=d)
        import subprocess
        mod = os.path.join(ROOT, "pipeline", "correspondents.py")
        subprocess.run([sys.executable, mod], env=env, cwd=d,
                       capture_output=True, check=True)
        with open(os.path.join(d, "agents_dynamic.json"), encoding="utf-8") as fh:
            return json.load(fh)["agents"]

    def test_country_with_enough_stories_gets_a_correspondent(self):
        rows = self._run([{"id": "kw", "name": "الكويت", "en": "Kuwait",
                           "n": 9, "sahih": 2, "hasan": 7}])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "murasil_kw")
        self.assertIn("الكويت", rows[0]["name"])
        self.assertEqual(rows[0]["name_en"], "Kuwait correspondent")
        self.assertEqual(rows[0]["parent"], "murasil")

    def test_country_below_threshold_gets_none(self):
        rows = self._run([{"id": "kw", "name": "الكويت", "en": "Kuwait", "n": 1}])
        self.assertEqual([r for r in rows if r["parent"] == "murasil"], [])

    def test_retires_when_country_goes_quiet(self):
        stale = [{"id": "murasil_zz", "parent": "murasil", "name": "مراسل قديم"}]
        rows = self._run([{"id": "kw", "name": "الكويت", "en": "Kuwait", "n": 5}], existing=stale)
        self.assertNotIn("murasil_zz", [r["id"] for r in rows])

    def test_does_not_clobber_wave_agents(self):
        wave = [{"id": "mawja_abc", "parent": "mawj", "name": "موجة"}]
        rows = self._run([{"id": "kw", "name": "الكويت", "en": "Kuwait", "n": 5}], existing=wave)
        self.assertIn("mawja_abc", [r["id"] for r in rows])

    def test_memory_accumulates_across_cycles(self):
        """التطوّر: الخبرةُ تتراكمُ عبرَ الدورات بلا نموذجٍ لغويّ."""
        import subprocess
        d = tempfile.mkdtemp()
        stories = [{"head": "الكويت تعلن ميزانية التعليم", "grade": "صحيح", "src": "كونا"},
                   {"head": "وزارة التعليم تفتتح مدارس", "grade": "حسن", "src": "الجريدة"},
                   {"head": "ميزانية التعليم في البرلمان", "grade": "حسن", "src": "القبس"}]
        with open(os.path.join(d, "map.json"), "w", encoding="utf-8") as fh:
            json.dump({"countries": [{"id": "kw", "name": "الكويت", "en": "Kuwait",
                                      "n": 3, "sahih": 1, "hasan": 2, "stories": stories}]},
                      fh, ensure_ascii=False)
        env = dict(os.environ, SANAD_DAILY=d)
        mod = os.path.join(ROOT, "pipeline", "correspondents.py")
        for _ in range(3):
            subprocess.run([sys.executable, mod], env=env, cwd=d, capture_output=True, check=True)
        with open(os.path.join(d, "correspondents.json"), encoding="utf-8") as fh:
            mem = json.load(fh)["countries"]["kw"]
        self.assertEqual(mem["cycles"], 3)
        self.assertEqual(mem["total"], 9)
        # وثاقةُ المنفذِ من درجةِ الإسناد: «كونا» صحيح ⇒ يتصدّر
        self.assertEqual(list(mem["sources"])[0], "كونا")
        self.assertGreater(mem["sources"]["كونا"]["sahih"], 0)
        # حارسُ الانجراف: لا حقلَ أداءٍ/انتشارٍ في الذاكرة إطلاقًا
        for rec in mem["sources"].values():
            self.assertEqual(set(rec) - {"n", "sahih", "at"}, set())

    def test_memory_only_learns_from_verified(self):
        import subprocess
        d = tempfile.mkdtemp()
        stories = [{"head": "خبر ضعيف الإسناد", "grade": "غير مُسند", "src": "مدونة"},
                   {"head": "الكويت تعلن ميزانية", "grade": "صحيح", "src": "كونا"}]
        with open(os.path.join(d, "map.json"), "w", encoding="utf-8") as fh:
            json.dump({"countries": [{"id": "kw", "name": "الكويت", "en": "Kuwait",
                                      "n": 3, "stories": stories}]}, fh, ensure_ascii=False)
        subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "correspondents.py")],
                       env=dict(os.environ, SANAD_DAILY=d), cwd=d, capture_output=True, check=True)
        with open(os.path.join(d, "correspondents.json"), encoding="utf-8") as fh:
            mem = json.load(fh)["countries"]["kw"]
        self.assertIn("كونا", mem["sources"])
        self.assertNotIn("مدونة", mem["sources"])   # غيرُ المُسنَدِ لا يدخلُ الذاكرة

    def test_roster_is_capped(self):
        many = [{"id": f"c{i}", "name": f"د{i}", "en": f"C{i}", "n": 5} for i in range(40)]
        rows = self._run(many)
        self.assertLessEqual(len([r for r in rows if r["parent"] == "murasil"]), 12)


class TestPushGuards(unittest.TestCase):
    """«المُنادي»: الإشعارُ مقاطعةٌ — فبواباتُه أضيقُ من بواباتِ العرض.

    الأنبوبُ يدورُ كلَّ ٣٠ دقيقةً على نفسِ `alerts.json`، فبلا سِجلِّ إرسالٍ
    يُقصَفُ القارئُ بنفسِ التحذيرِ ٤٨ مرّةً في اليوم. هذه الاختباراتُ تحرسُ ذلك.
    """

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "pipeline"))
        import push_fcm
        self.m = push_fcm
        self.d = tempfile.mkdtemp()
        self.m.ALERTS_F = os.path.join(self.d, "alerts.json")
        self.m.SENT_F = __import__("pathlib").Path(self.d, "push_sent.json")
        self.sent_msgs = []
        self.m._sa = lambda: {"client_email": "x@y.z", "private_key": "k", "project_id": "p"}
        self.m._access_token = lambda sa: "tok"
        self.m._send = lambda p, t, title, body, data: (
            self.sent_msgs.append({"title": title, "body": body, "data": data}) or True)

    def _alert(self, txt, hours_ago=0.2, url="https://example.com/a"):
        cap = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="minutes")
        return {"kind": "تحذير", "body": "الدفاع المدني", "txt": txt, "u": url,
                "when": "8 أغسطس 2026", "cap": cap}

    def _write(self, items):
        with open(self.m.ALERTS_F, "w", encoding="utf-8") as fh:
            json.dump({"updated": "x", "list": items}, fh, ensure_ascii=False)

    def test_same_alert_is_never_pushed_twice(self):
        self._write([self._alert("إخلاء فوري في المنطقة أ")])
        self.assertEqual(len(self.sent_msgs), 0)
        self.m.push_alerts()
        self.assertEqual(len(self.sent_msgs), 1)
        self.m.push_alerts()          # الدورةُ التالية بعد ٣٠ دقيقة
        self.m.push_alerts()          # والتي تليها
        self.assertEqual(len(self.sent_msgs), 1, "أُرسِلَ نفسُ التحذيرِ أكثرَ من مرّة")

    def test_id_survives_link_resolution(self):
        """رابطُ غوغل يُفَكُّ لاحقًا إلى رابطِ الناشر — والبصمةُ من النصِّ فلا يتكرّر."""
        a = self._alert("حريق في المستودع", url="https://news.google.com/rss/articles/CBMi123")
        b = dict(a, u="https://alqabas.com/article/999")
        self.assertEqual(self.m.alert_id(a), self.m.alert_id(b))

    def test_stale_alert_does_not_wake_anyone(self):
        self._write([self._alert("تحذيرٌ فاتَ أوانُه", hours_ago=30)])
        r = self.m.push_alerts()
        self.assertEqual(len(self.sent_msgs), 0)
        self.assertTrue(r.get("skipped"))

    def test_insecure_link_is_refused(self):
        self._write([self._alert("تحذير", url="http://insecure.example/a")])
        self.m.push_alerts()
        self.assertEqual(len(self.sent_msgs), 0)

    def test_daily_cap_holds_the_line(self):
        self._write([self._alert(f"تحذير رقم {i}") for i in range(20)])
        self.m.push_alerts()
        self.assertLessEqual(len(self.sent_msgs), self.m.DAILY_CAP)

    def test_body_carries_the_source(self):
        """الإشعارُ نفسُه مُسنَد: يحملُ اسمَ الراوي، لا صوتًا مجهولًا."""
        self._write([self._alert("إغلاق طريق")])
        self.m.push_alerts()
        self.assertIn("الدفاع المدني", self.sent_msgs[0]["body"])

    def test_rumor_notice_is_never_pushed_as_official_warning(self):
        """`alerts.json` يحملُ صنفَين — والإشعارُ يخرجُ بعنوانِ «تحذيرٌ رسميّ».

        بثُّ «تنبيه من شائعة» تحتَه يجعلُ سَنَد تخلطُ ما قامت لتفريقِه.
        (٣ من آخرِ ٨ عناصرَ منشورةٍ كانت من هذا الصنف — الخطرُ حقيقيٌّ لا نظريّ.)
        """
        rumor = self._alert("تداول مزاعم عن انفجار")
        rumor["kind"] = "تنبيه من شائعة"
        self._write([rumor])
        r = self.m.push_alerts()
        self.assertEqual(len(self.sent_msgs), 0, "أُرسِلَ تنبيهُ شائعةٍ كتحذيرٍ رسميّ")
        self.assertTrue(r.get("skipped"))

    def test_official_warning_still_passes_alongside_a_rumor(self):
        rumor = self._alert("مزاعم متداولة"); rumor["kind"] = "تنبيه من شائعة"
        self._write([rumor, self._alert("إخلاء فوري")])
        self.m.push_alerts()
        self.assertEqual(len(self.sent_msgs), 1)
        self.assertIn("إخلاء فوري", self.sent_msgs[0]["body"])

    def test_no_secret_means_silent_skip(self):
        self.m._sa = lambda: None
        self._write([self._alert("تحذير")])
        r = self.m.push_alerts()
        self.assertTrue(r.get("skipped"))
        self.assertEqual(len(self.sent_msgs), 0)


class TestAuxStatusHonesty(unittest.TestCase):
    """وحدةٌ مساعِدةٌ تقولُ «تخطّيتُ» لا تُسجَّلُ «سليمة»."""

    def _aux(self, ret):
        aux = {}
        g = load(["_run_aux"], extra={
            "_AUX": aux, "time": __import__("time"),
            "sys": sys, "os": os,
        })
        mod = type(sys)("fake_aux_mod")
        mod.go = lambda: ret
        sys.modules["fake_aux_mod"] = mod
        try:
            g["_run_aux"]("fake_aux_mod", "go", "fake")
        finally:
            sys.modules.pop("fake_aux_mod", None)
        return aux["fake"]

    def test_skipped_return_is_recorded_as_skip(self):
        rec = self._aux({"skipped": 1, "why": "لا سرَّ Firebase"})
        self.assertEqual(rec["status"], "skip")
        self.assertIn("Firebase", rec["note"])

    def test_failed_return_is_recorded_as_fail(self):
        self.assertEqual(self._aux({"failed": 1, "why": "انقطاع"})["status"], "fail")

    def test_plain_return_is_ok(self):
        self.assertEqual(self._aux({"why": "3 تحذيرات"})["status"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
