# -*- coding: utf-8 -*-
"""«المُراسِلون» 📍 — مراسلٌ لكلِّ دولةٍ لها أخبارٌ مُسنَدةٌ اليوم.

حتميٌّ بالكامل — لا نموذجَ لغويّ، لا مفاتيح، صفرُ كلفةِ API. كلُّ ما يفعلُه
تجميعُ ما جمعَه الأنبوبُ أصلًا في `daily/map.json` (أخبارٌ مُسنَدةٌ لكلِّ دولة)
وتقديمُه بوجهٍ مفهوم: مراسلٌ للدولةِ يُحيلُ إلى مصادرِها.

قيدُ نزاهةٍ صريح: هؤلاء **مكاتبُ رصدٍ آليّة** لا صحفيّون في الميدان — لا يكتبون
خبرًا ولا يشهدون واقعة؛ يُحيلون إلى موادَّ منشورةٍ بمصادرِها ودرجاتِها. ولذلك
صِيغَ الدورُ بلفظِ «ينقلُ ويُحيل» لا «يُغطّي من الميدان».

يُفرَّخُ المراسلُ حين يكونُ لبلدِه موادُّ مُسنَدةٌ اليوم، ويختفي تلقائيًّا حين
تخلو — نفسُ منطقِ تقاعدِ وكلاءِ الموجة.
"""
from __future__ import annotations

import json
import re
import os
from datetime import datetime, timezone
from pathlib import Path

OUT = os.environ.get("SANAD_DAILY", "daily")
MAP_F = Path(OUT, "map.json")
DYN_F = Path(OUT, "agents_dynamic.json")
MEM_F = Path(OUT, "correspondents.json")   # ذاكرةُ المراسلين عبرَ الدورات

MIN_STORIES = int(os.environ.get("MURASIL_MIN", "3"))   # أقلُّ عددِ موادَّ مُسنَدةٍ لتفريخِ مراسل
MAX_CORRESPONDENTS = int(os.environ.get("MURASIL_MAX", "12"))
PARENT = "murasil"

# ═══ حدودُ التطوّر (نفسُ حرّاسِ المنصّة) ═══
# المراسلُ «يتطوّر»: يتراكمُ لديه سجلٌّ عبرَ الدورات فيعرفُ منافذَ بلدِه الأوثقَ
# ومحاورَه المتكرّرة. لكنّ التطوّرَ محكومٌ بالحرّاسِ نفسِها التي تحكمُ بقيّةَ المنصّة:
#  ١) لا يتعلّمُ إلّا من موادَّ **مُسنَدةٍ** (صحيح/حسن) — لا شيءَ آخرَ يدخلُ الذاكرة.
#  ٢) حتميٌّ بالكامل: عدٌّ وترتيب، بلا نموذجٍ لغويّ — فلا مجالَ لاختلاقٍ أصلًا.
#  ٣) **حارسُ الانجراف**: يتعلّمُ وثاقةَ المنفذِ ومحاورَ التغطيةِ فقط — ولا يتعلّمُ
#     أبدًا من الانتشارِ أو التفاعلِ أو الأداء. (نفسُ ثابتِ مسارِ الشائعات: الحكمُ
#     يُسنَدُ للمصدرِ لا للأداء.) فلا يصيرُ ما يُنشَرُ رهنًا بما يُعجِب.
#  ٤) الذاكرةُ تتقادم: ما لم يظهرْ منذ MEM_FORGET_DAYS يُنسى، والسجلُّ مسقوف.
#  ٥) لا يكتبُ المراسلُ خبرًا ولا يُعدّلُ عنوانًا — يُحيلُ إلى موادَّ منشورةٍ بمصادرِها.
MEM_FORGET_DAYS = float(os.environ.get("MURASIL_FORGET_DAYS", "21"))
MEM_TOP_SOURCES = 5
MEM_TOP_BEATS = 5

_STOP = {
    "الذي","التي","على","عن","الى","إلى","من","في","مع","بعد","قبل","بين","هذا","هذه",
    "ذلك","كان","كانت","قال","قالت","اليوم","امس","أمس","خلال","حول","ضد","عبر","لدى",
    "منذ","حتى","بشان","بشأن","اثر","إثر","وسط","نحو","عند","دون","بلا","the","and",
    "for","with","from","that","this","says","after","over","into","their","about",
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


def _load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _tok(s):
    """توكناتٌ دالّةٌ من عنوانٍ عربيّ/لاتينيّ — لاستخراجِ محاورِ التغطية."""
    s = re.sub(r"[ً-ْٰ]", "", str(s or "")).lower()
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    out = set()
    for w in re.findall(r"[a-zء-ي]{4,}", s):
        if w.startswith("ال") and len(w) > 5:
            w = w[2:]
        if w not in _STOP:
            out.add(w)
    return out


def _evolve(mem, cid, country, now):
    """يُحدِّثُ ذاكرةَ مراسلٍ من موادِّ اليومِ المُسنَدةِ وحدَها — عدٌّ حتميٌّ لا تعلّمَ أداء."""
    rec = mem.get(cid) or {"first_seen": now, "cycles": 0, "total": 0,
                           "sources": {}, "beats": {}, "peak": 0}
    stories = [s for s in (country.get("stories") or [])
               if isinstance(s, dict) and s.get("grade") in ("صحيح", "حسن")]
    rec["cycles"] = int(rec.get("cycles", 0)) + 1
    rec["total"] = int(rec.get("total", 0)) + len(stories)
    rec["peak"] = max(int(rec.get("peak", 0)), int(country.get("n") or 0))
    rec["last_seen"] = now
    src = dict(rec.get("sources") or {})
    beats = dict(rec.get("beats") or {})
    for s in stories:
        nm = str(s.get("src") or "").strip()
        if nm:
            # وزنُ «صحيح» ضِعفُ «حسن»: وثاقةُ المنفذِ من درجةِ الإسنادِ لا من الرواج
            e = src.get(nm) or {"n": 0, "sahih": 0, "at": now}
            e["n"] += 1
            if s.get("grade") == "صحيح":
                e["sahih"] += 1
            e["at"] = now
            src[nm] = e
        for t in list(_tok(s.get("head")))[:8]:
            b = beats.get(t) or {"n": 0, "at": now}
            b["n"] += 1
            b["at"] = now
            beats[t] = b
    # تقادُم: ما لم يظهرْ منذ مدّةٍ يُنسى — الذاكرةُ تتبعُ الواقعَ لا تتضخّم
    def _fresh(d):
        try:
            t = datetime.fromisoformat(str(d.get("at")).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - t).days <= MEM_FORGET_DAYS
        except Exception:
            return True
    src = {k: v for k, v in src.items() if _fresh(v)}
    beats = {k: v for k, v in beats.items() if _fresh(v)}
    rec["sources"] = dict(sorted(src.items(), key=lambda kv: -kv[1]["n"])[:24])
    rec["beats"] = dict(sorted(beats.items(), key=lambda kv: -kv[1]["n"])[:24])
    mem[cid] = rec
    return rec


def correspondents() -> dict:
    """يبني طاقمَ المراسلين من map.json ويدمجُه في agents_dynamic.json."""
    mp = _load(MAP_F, {})
    countries = [c for c in (mp.get("countries") or [])
                 if isinstance(c, dict) and int(c.get("n") or 0) >= MIN_STORIES]
    countries.sort(key=lambda c: (int(c.get("n") or 0), int(c.get("sahih") or 0)), reverse=True)
    countries = countries[:MAX_CORRESPONDENTS]

    now = _now()
    mem = _load(MEM_F, {})
    if not isinstance(mem, dict):
        mem = {}
    mem = mem.get("countries", mem) if "countries" in mem else mem
    roster = []
    live_ids = set()
    for c in countries:
        cid = str(c.get("id") or "").strip()
        if not cid:
            continue
        live_ids.add(cid)
        ar = str(c.get("name") or cid)
        en = str(c.get("en") or cid)
        n = int(c.get("n") or 0)
        sahih = int(c.get("sahih") or 0)
        hasan = int(c.get("hasan") or 0)
        rec = _evolve(mem, cid, c, now)
        top_src = list(rec.get("sources") or {})[:MEM_TOP_SOURCES]
        top_beats = list(rec.get("beats") or {})[:MEM_TOP_BEATS]
        # خبرةٌ متراكمة تُعرَض بصدق: عددُ الدوراتِ وما تراكمَ من موادَّ مُسنَدة
        learned = f" · خبرةُ {rec['cycles']} دورةٍ ({rec['total']} مادّةً)" if rec["cycles"] > 1 else ""
        learned_en = f" · {rec['cycles']} cycles ({rec['total']} items)" if rec["cycles"] > 1 else ""
        roster.append({
            "id": f"murasil_{cid}",
            "icon": "📍",
            "parent": PARENT,
            "country": cid,
            "name": f"مراسل {ar}",
            "name_en": f"{en} correspondent",
            # لفظُ «ينقل/يُحيل» مقصود: مكتبُ رصدٍ آليّ، لا مراسلٌ في الميدان
            "role": f"ينقلُ أخبارَ {ar} المُسنَدةَ ويُحيلُ إلى مصادرِها",
            "role_en": f"Relays verified {en} stories and links their sources",
            "status": "ok",
            "note": f"{n} مادّةً مُسنَدة · {sahih} صحيح · {hasan} حسن" + learned,
            "note_en": f"{n} verified items · {sahih} sahih · {hasan} hasan" + learned_en,
            # ما تعلّمَه: منافذُ بلدِه الأوثقُ ومحاورُه المتكرّرة — عدًّا لا تخمينًا
            "sources": top_src,
            "beats": top_beats,
            "cycles": rec["cycles"],
            "at": now,
        })

    # دمجٌ لا استبدال: ملفُّ الطاقمِ الديناميكيّ يتشاركُه المَوّاجُ والمراسلون،
    # فكلُّ وحدةٍ تستبدلُ صفوفَها هي فقط وتُبقي صفوفَ غيرِها.
    prev = _load(DYN_F, {})
    others = [a for a in (prev.get("agents") or [])
              if isinstance(a, dict) and a.get("parent") != PARENT]
    DYN_F.write_text(json.dumps({"updated": now, "agents": others + roster},
                                ensure_ascii=False, indent=1), encoding="utf-8")

    # الذاكرةُ تبقى لمن غابَ مؤقّتًا (يعودُ بخبرتِه)، وتُنسى بعدَ التقادُم
    def _stale(rec):
        try:
            t = datetime.fromisoformat(str(rec.get("last_seen")).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - t).days > MEM_FORGET_DAYS
        except Exception:
            return False
    mem = {k: v for k, v in mem.items() if not _stale(v)}
    MEM_F.write_text(json.dumps({"updated": now,
        "note": "ذاكرةُ المراسلين — تتراكمُ من موادَّ مُسنَدةٍ وحدَها، عدًّا حتميًّا بلا تعلّمِ أداء",
        "countries": mem}, ensure_ascii=False, indent=1), encoding="utf-8")

    veteran = sum(1 for r in roster if r.get("cycles", 0) > 1)
    print(f"📍 المُراسِلون: {len(roster)} مراسلًا ({veteran} بخبرةٍ متراكمة) "
          f"من {len(mp.get('countries') or [])} دولةً مرصودة")
    return {"why": f"{len(roster)} مراسلًا · {veteran} متمرّس"}


if __name__ == "__main__":
    print(json.dumps(correspondents(), ensure_ascii=False))
