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
import os
from datetime import datetime, timezone
from pathlib import Path

OUT = os.environ.get("SANAD_DAILY", "daily")
MAP_F = Path(OUT, "map.json")
DYN_F = Path(OUT, "agents_dynamic.json")

MIN_STORIES = int(os.environ.get("MURASIL_MIN", "3"))   # أقلُّ عددِ موادَّ مُسنَدةٍ لتفريخِ مراسل
MAX_CORRESPONDENTS = int(os.environ.get("MURASIL_MAX", "12"))
PARENT = "murasil"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


def _load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def correspondents() -> dict:
    """يبني طاقمَ المراسلين من map.json ويدمجُه في agents_dynamic.json."""
    mp = _load(MAP_F, {})
    countries = [c for c in (mp.get("countries") or [])
                 if isinstance(c, dict) and int(c.get("n") or 0) >= MIN_STORIES]
    countries.sort(key=lambda c: (int(c.get("n") or 0), int(c.get("sahih") or 0)), reverse=True)
    countries = countries[:MAX_CORRESPONDENTS]

    now = _now()
    roster = []
    for c in countries:
        cid = str(c.get("id") or "").strip()
        if not cid:
            continue
        ar = str(c.get("name") or cid)
        en = str(c.get("en") or cid)
        n = int(c.get("n") or 0)
        sahih = int(c.get("sahih") or 0)
        hasan = int(c.get("hasan") or 0)
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
            "note": f"{n} مادّةً مُسنَدة · {sahih} صحيح · {hasan} حسن",
            "note_en": f"{n} verified items · {sahih} sahih · {hasan} hasan",
            "at": now,
        })

    # دمجٌ لا استبدال: ملفُّ الطاقمِ الديناميكيّ يتشاركُه المَوّاجُ والمراسلون،
    # فكلُّ وحدةٍ تستبدلُ صفوفَها هي فقط وتُبقي صفوفَ غيرِها.
    prev = _load(DYN_F, {})
    others = [a for a in (prev.get("agents") or [])
              if isinstance(a, dict) and a.get("parent") != PARENT]
    DYN_F.write_text(json.dumps({"updated": now, "agents": others + roster},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"📍 المُراسِلون: {len(roster)} مراسلًا من {len(mp.get('countries') or [])} دولةً مرصودة")
    return {"why": f"{len(roster)} مراسلًا"}


if __name__ == "__main__":
    print(json.dumps(correspondents(), ensure_ascii=False))
