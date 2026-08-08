# -*- coding: utf-8 -*-
"""«المَوّاج» 🌊 — وكلاءُ متابعةِ الموجةِ الديناميكيّون.

يتتبّعُ «موجاتِ» الأخبارِ المُسنَدةِ عبرَ الدورات، ويُوكِّلُ لكلِّ موجةٍ حيّةٍ
وكيلًا فرعيًّا يرصدُ زخمَها. حتميٌّ بالكامل — لا نموذجَ لغويّ، لا مفاتيح،
صفرُ كلفةِ API. الموجةُ عنقودُ موادَّ مُسنَدةٍ (صحيح/حسن) يتشاركُ موضوعًا؛
تُفرَّخُ عند الظهور وتُتقاعَدُ تلقائيًّا حين تخبو (بلا موادَّ جديدةٍ ٣ دورات).

المُخرَجات:
  • daily/waves.json          — ذاكرةُ الموجاتِ عبرَ الدورات (الحالة)
  • daily/agents_dynamic.json — طاقمُ الوكلاءِ الفرعيّين الأحياء (يدمجُه save_agents)
"""
from __future__ import annotations

import json
import os
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path

OUT = os.environ.get("SANAD_DAILY", "daily")
WAVES_F = Path(OUT, "waves.json")
DYN_F = Path(OUT, "agents_dynamic.json")

MAX_WAVES = 6          # سقفٌ صارمٌ يمنعُ انفجارَ الطاقم
MIN_CLUSTER = 2        # موجةٌ تحتاجُ مصدرين مُسنَدين على الأقل
RETIRE_AFTER = 3       # دوراتٌ بلا موادَّ جديدةٍ ← تقاعد
SIM_MATCH = 0.30       # تداخلُ كلماتٍ لمطابقةِ موجةٍ قائمة
SIM_CLUSTER = 0.42     # تقاطعُ جاكارد لعنقدةِ العناوين

# كلماتٌ شائعةٌ تُستبعَدُ من البصمة (لا تميّزُ موضوعًا)
_STOP = {
    "الذي", "التي", "الذين", "على", "عن", "إلى", "من", "في", "مع", "بعد", "قبل",
    "بين", "هذا", "هذه", "ذلك", "كان", "كانت", "قال", "قالت", "أعلن", "أعلنت",
    "اليوم", "أمس", "خلال", "حول", "ضد", "عبر", "أمام", "لدى", "منذ", "حتى",
    "وزير", "وزارة", "رئيس", "الحكومة", "مصدر", "مصادر", "تقارير", "وكالة",
    "news", "with", "from", "that", "this", "have", "will", "amid", "says",
    "after", "over", "into", "their", "about", "would", "could", "which",
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


def _load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _norm(s: str) -> str:
    s = str(s or "")
    s = re.sub(r"[ً-ْٰ]", "", s)              # حذفُ التشكيل
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    return s


def _tok(s: str) -> set:
    """توكناتٌ دالّةٌ ≥3 أحرف بعدَ تجريدِ حرفِ العطفِ (و/ف) وأداةِ التعريف (ال)،
    دون الشائع — كي يلتقيَ «القطاع/قطاع» و«غزة» القصيرةُ الدالّة."""
    s = _norm(s).lower()
    out = set()
    for w in re.findall(r"[a-zء-ي]{3,}", s):
        if w[:1] in ("و", "ف") and len(w) > 4:
            w = w[1:]
        if w.startswith("ال") and len(w) > 4:
            w = w[2:]
        if len(w) >= 3 and w not in _STOP:
            out.add(w)
    return out


def _auth_items() -> list:
    """الموادُّ المُسنَدةُ (صحيح/حسن) من دورةِ اليوم."""
    news = _load(Path(OUT, "news.json"), {})
    out = []
    for cat, lst in (news.get("cats") or {}).items():
        for it in lst or []:
            if isinstance(it, dict) and it.get("grade") in ("صحيح", "حسن"):
                d = dict(it)
                d["cat"] = cat
                d["_tok"] = _tok(str(it.get("head", "")) + " " + str(it.get("he", "")))
                out.append(d)
    out.sort(key=lambda i: (3 if i.get("grade") == "صحيح" else 2,
                            i.get("score") or 0, str(i.get("at") or "")), reverse=True)
    return out


def _jac(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _cluster(items: list) -> list:
    """عنقدةٌ جشعةٌ للعناوينِ المتشابهةِ إلى مواضيع."""
    clusters = []
    for it in items:
        tk = it.get("_tok") or set()
        if len(tk) < 2:
            continue
        # أفضلُ عنقودٍ: أكثرُ توكناتٍ مشتركةً (مع جاكارد للترجيح) — عنوانان
        # يتشاركان ≥٢ توكنًا دالًّا غالبًا خبرٌ واحد.
        best, b_shared, b_jac = None, 0, 0.0
        for c in clusters:
            shared = len(tk & c["kw"])
            j = _jac(tk, c["kw"])
            if (shared, j) > (b_shared, b_jac):
                b_shared, b_jac, best = shared, j, c
        if best and (b_shared >= 2 or b_jac >= SIM_CLUSTER):
            best["items"].append(it)
            best["kw"] |= tk
        else:
            clusters.append({"kw": set(tk), "items": [it]})
    clusters = [c for c in clusters if len(c["items"]) >= MIN_CLUSTER]
    # ترتيبٌ بالحجمِ ثمّ أعلى درجةٍ مُسنَدة
    clusters.sort(key=lambda c: (len(c["items"]),
                                 max((i.get("score") or 0) for i in c["items"])), reverse=True)
    return clusters[:MAX_WAVES]


def _label(cluster: dict):
    """اسمٌ عربيٌّ/إنجليزيٌّ قصيرٌ من أبرزِ موادِّ العنقود."""
    top = max(cluster["items"], key=lambda i: (3 if i.get("grade") == "صحيح" else 2, i.get("score") or 0))
    ar = re.sub(r"\s+", " ", str(top.get("head") or "")).strip()[:46]
    en = re.sub(r"\s+", " ", str(top.get("he") or "")).strip()[:46]
    return ar or "موجة", en or ar or "Wave"


def _momentum(count: int, last: int) -> str:
    if last <= 0:
        return "rising"
    if count > last:
        return "rising"
    if count == last:
        return "peaking"
    return "fading"


def _slug(kw: set) -> str:
    return "mawja_" + hashlib.md5(" ".join(sorted(kw)).encode("utf-8")).hexdigest()[:6]


def wave_agents() -> dict:
    """يبني/يحدّثُ/يتقاعدُ الموجاتِ ويكتبُ الذاكرةَ والطاقمَ الديناميكيّ."""
    items = _auth_items()
    clusters = _cluster(items)
    prev = _load(WAVES_F, {}).get("waves", [])
    prev_by_id = {w["id"]: w for w in prev if isinstance(w, dict) and w.get("id")}

    now = _now()
    matched_ids = set()
    waves = []

    for c in clusters:
        kw = c["kw"]
        count = len(c["items"])
        # مطابقةُ موجةٍ قائمةٍ: أكثرُ توكناتٍ مشتركةً (متينٌ رغمَ تفاوتِ حجمِ
        # المجموعتين عبرَ الدورات) مع جاكارد للترجيح — فيثبتُ مُعرِّفُ الموجة.
        match, m_shared, m_jac = None, 0, 0.0
        for w in prev:
            if w.get("id") in matched_ids:
                continue
            wk = set(w.get("kw") or [])
            shared = len(kw & wk)
            j = _jac(kw, wk)
            if (shared, j) > (m_shared, m_jac):
                m_shared, m_jac, match = shared, j, w
        ar, en = _label(c)
        links = [i.get("link") for i in c["items"][:5] if i.get("link")]
        if match and (m_shared >= 2 or m_jac >= SIM_MATCH):
            wid = match["id"]
            matched_ids.add(wid)
            last = int(match.get("last_count") or 0)
            waves.append({
                "id": wid, "kw": sorted(kw | set(match.get("kw") or []))[:24],
                "name_ar": ar, "name_en": en,
                "first_seen": match.get("first_seen") or now, "last_seen": now,
                "cycles": int(match.get("cycles") or 0) + 1,
                "peak": max(int(match.get("peak") or 0), count),
                "last_count": count, "momentum": _momentum(count, last),
                "fresh_gap": 0, "links": links, "status": "live",
            })
        else:
            wid = _slug(kw)
            if wid in {w["id"] for w in waves}:
                continue
            waves.append({
                "id": wid, "kw": sorted(kw)[:24], "name_ar": ar, "name_en": en,
                "first_seen": now, "last_seen": now, "cycles": 1,
                "peak": count, "last_count": count, "momentum": "rising",
                "fresh_gap": 0, "links": links, "status": "live",
            })

    # الموجاتُ التي لم تُطابَقْ هذه الدورةَ: زيادةُ فجوةِ الطزاجة، وتقاعدُ الميّت
    live_ids = {w["id"] for w in waves}
    for w in prev:
        wid = w.get("id")
        if not wid or wid in live_ids:
            continue
        gap = int(w.get("fresh_gap") or 0) + 1
        if gap >= RETIRE_AFTER:
            continue  # تقاعد — يُحذَفُ من الذاكرة
        w2 = dict(w)
        w2.update({"fresh_gap": gap, "last_count": 0, "momentum": "fading", "status": "fading"})
        waves.append(w2)

    # سقفٌ نهائيٌّ: الأعلى زخمًا (الأحياءُ أوّلًا ثمّ الأكبرُ ذروة)
    waves.sort(key=lambda w: (w.get("status") == "live", w.get("last_count") or 0, w.get("peak") or 0), reverse=True)
    waves = waves[:MAX_WAVES]

    WAVES_F.write_text(json.dumps({"updated": now, "note": "موجاتُ الأخبارِ المُسنَدةِ — عدٌّ حتميٌّ شفّاف",
                                   "waves": waves}, ensure_ascii=False, indent=1), encoding="utf-8")

    # طاقمُ الوكلاءِ الفرعيّين الأحياء (يدمجُه save_agents في agents.json)
    _MO_AR = {"rising": "زخمٌ صاعد", "peaking": "في الذروة", "fading": "زخمٌ خافت"}
    _MO_EN = {"rising": "rising", "peaking": "peaking", "fading": "fading"}
    roster = []
    for w in waves:
        mo = w.get("momentum") or "rising"
        st = "ok" if mo in ("rising", "peaking") else "skip"
        n = int(w.get("last_count") or 0)
        roster.append({
            "id": w["id"], "icon": "🌊", "parent": "mawj", "wave_id": w["id"],
            "name": "موجة · " + (w.get("name_ar") or ""),
            "name_en": "Wave · " + (w.get("name_en") or ""),
            "role": "يتتبّعُ موجةَ: " + (w.get("name_ar") or ""),
            "role_en": "Tracks the wave: " + (w.get("name_en") or ""),
            "status": st,
            "note": f"{_MO_AR.get(mo, mo)} · {n} موادَّ مُسنَدة",
            "note_en": f"{_MO_EN.get(mo, mo)} · {n} verified items",
            "at": now,
        })
    # دمجٌ لا استبدال: الملفُّ يتشاركُه المَوّاجُ والمراسلون — نستبدلُ صفوفَنا فقط
    _prev = _load(DYN_F, {})
    _others = [a for a in (_prev.get("agents") or [])
               if isinstance(a, dict) and a.get("parent") != "mawj"]
    DYN_F.write_text(json.dumps({"updated": now, "agents": _others + roster},
                                ensure_ascii=False, indent=1), encoding="utf-8")

    live = sum(1 for w in waves if w.get("status") == "live")
    print(f"🌊 المَوّاج: {live} موجةً حيّة · {len(roster)} وكيلًا فرعيًّا · طَوى {max(0, len(prev) - len(waves))}")
    return {"why": f"{live} موجةً حيّة · {len(roster)} وكيلًا فرعيًّا"}


if __name__ == "__main__":
    print(json.dumps(wave_agents(), ensure_ascii=False))
