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
        g = load(["_age_h", "_count_items", "_HEALTH_SPEC", "hirasa"], extra={
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
        h, _ = self._run({})
        self.assertTrue(all(s["state"] == "dead" for s in h["sections"]))
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
