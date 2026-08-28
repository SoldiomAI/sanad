# -*- coding: utf-8 -*-
"""«الورّاق» 📚 — باحثُ أوراقِ الذكاءِ الاصطناعيّ.

ينقلُ أحدثَ الأوراقِ البحثيّةِ من منبعَيها الأوّلَين — arXiv وHugging Face —
ويكتبُ daily/papers.json: لكلِّ ورقةٍ عنوانُها وملخّصٌ موجزٌ ورابطُها الأصليّ.

منهجُ سَنَد نفسُه مُطبَّقٌ على البحثِ العلميّ:
 ١) **الورقةُ مصدرٌ أوّل** — الرابطُ يُحيلُ إلى الورقةِ نفسِها لا إلى خبرٍ عنها،
    فالاتصالُ هنا أعلى درجاتِ الإسناد (لا واسطةَ بين القارئِ والمصدر).
 ٢) لا اختلاق: العنوانُ والمؤلّفون والملخّصُ الإنجليزيّ من الـAPI حرفيًّا؛
    التعريبُ — إن توفّرَ مفتاحُ Gemini — تلخيصٌ أمينٌ، وغيابُه لا يمنعُ النشر.
 ٣) صفرُ كلفةٍ افتراضًا: arXiv API وHF مجّانيّان بلا مفاتيح؛ Gemini اختياريّ
    وتحت سقفِ ميزانيّةِ المنصّةِ المعتاد.
 ٤) نوبةٌ لا تكرار: يُحدَّثُ كلَّ WARRAQ_EVERY_H (افتراضًا ١٢ ساعة) — الأوراقُ
    لا تتقادمُ بوتيرةِ الأخبار، والتخطّي الصامتُ يوفّرُ النداءات.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

OUT = os.environ.get("SANAD_DAILY", "daily")
PAPERS_F = f"{OUT}/papers.json"
EVERY_H = float(os.environ.get("WARRAQ_EVERY_H", "12"))
MAX_PAPERS = int(os.environ.get("WARRAQ_MAX", "6"))
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

ARXIV_URL = ("https://export.arxiv.org/api/query?"
             "search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG"
             "&sortBy=submittedDate&sortOrder=descending&max_results=10")
HF_URL = "https://huggingface.co/api/daily_papers?limit=8"
_ATOM = "{http://www.w3.org/2005/Atom}"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


def _clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def _fresh_enough():
    try:
        doc = json.load(open(PAPERS_F, encoding="utf-8"))
        age = (datetime.now(timezone.utc)
               - datetime.fromisoformat(doc["updated"])).total_seconds() / 3600
        return age < EVERY_H, age
    except Exception:
        return False, None


def _fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (isnad.news warraq)"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def _arxiv_papers():
    """أوراقُ arXiv الأحدث — منبعٌ أوّلُ مفتوحٌ بلا مفتاح."""
    out = []
    try:
        root = ET.fromstring(_fetch(ARXIV_URL))
        for e in root.iter(f"{_ATOM}entry"):
            link = _clean(e.findtext(f"{_ATOM}id"))
            title = _clean(e.findtext(f"{_ATOM}title"))
            if not (link and title):
                continue
            authors = [_clean(a.findtext(f"{_ATOM}name"))
                       for a in e.iter(f"{_ATOM}author")][:4]
            out.append({
                "id": link.rsplit("/", 1)[-1],
                "title": title,
                "abstract": _clean(e.findtext(f"{_ATOM}summary"))[:600],
                "authors": authors,
                "link": link.replace("http://", "https://"),
                "src": "arXiv",
                "via": "مستودعُ الأوراقِ العلميّةِ المفتوح",
                "published": _clean(e.findtext(f"{_ATOM}published"))[:16],
            })
    except Exception as e:
        print(f"warraq/arxiv: {str(e)[:80]}")
    return out


def _hf_papers():
    """أوراقُ اليومِ على Hugging Face — انتقاءُ مجتمعِ الباحثين نفسِه."""
    out = []
    try:
        for row in json.loads(_fetch(HF_URL)):
            p = row.get("paper") or {}
            pid = _clean(p.get("id"))
            title = _clean(p.get("title"))
            if not (pid and title):
                continue
            out.append({
                "id": pid,
                "title": title,
                "abstract": _clean(p.get("summary"))[:600],
                "authors": [_clean(a.get("name")) for a in (p.get("authors") or [])[:4]],
                "link": f"https://huggingface.co/papers/{pid}",
                "src": "Hugging Face Papers",
                "via": "انتقاءُ مجتمعِ الباحثين اليوميّ",
                "published": _clean(p.get("publishedAt"))[:16],
            })
    except Exception as e:
        print(f"warraq/hf: {str(e)[:80]}")
    return out


def _arabize(papers):
    """تعريبٌ أمينٌ اختياريّ: عنوانٌ وملخّصٌ من سطرين لكلِّ ورقة — نداءٌ واحدٌ للجميع.
    غيابُ المفتاحِ أو فشلُ النداءِ لا يمنعُ النشرَ: يُعرَضُ الأصلُ الإنجليزيّ."""
    if not GEMINI_KEY or not papers:
        return 0
    lst = "\n".join(f"{n}| {p['title']} :: {p['abstract'][:300]}"
                    for n, p in enumerate(papers))
    prompt = ("عرّب أوراقًا بحثية في الذكاء الاصطناعي. لكل سطر مُرقَّم أدناه أخرج سطرًا"
              " بالشكل: الرقم| العنوان بالعربية :: ملخص عربي أمين في جملتين كحدٍّ أقصى."
              " لا تُضِف معلومة ليست في النص، ولا تُخرج شيئًا آخر.\n" + lst)
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.2,
                                 "thinkingConfig": {"thinkingBudget": 0}}}
    try:
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_KEY},
            method="POST")
        d = json.loads(urllib.request.urlopen(req, timeout=60).read())
        txt = d["candidates"][0]["content"]["parts"][0]["text"]
        n = 0
        for ln in txt.splitlines():
            m = re.match(r"\s*(\d+)\s*\|\s*(.+?)\s*::\s*(.+)", ln)
            if not m:
                continue
            i = int(m.group(1))
            if 0 <= i < len(papers):
                papers[i]["title_ar"] = _clean(m.group(2))[:200]
                papers[i]["summary_ar"] = _clean(m.group(3))[:400]
                n += 1
        return n
    except Exception as e:
        print(f"warraq/gemini: {str(e)[:80]}")
        return 0


def warraq():
    fresh, age = _fresh_enough()
    if fresh:
        left = max(0, round(EVERY_H - (age or 0), 1))
        return {"skipped": 1, "why": f"نوبتُه بعد ~{left}س"}

    papers, seen = [], set()
    for p in _hf_papers() + _arxiv_papers():
        key = p["title"][:60].lower()
        if key in seen:
            continue
        seen.add(key)
        papers.append(p)
        if len(papers) >= MAX_PAPERS:
            break

    if not papers:
        # لا نمسحُ آخرَ إصدارٍ صالحٍ بفشلِ جلبٍ عابر — الصمتُ خيرٌ من صفحةٍ فارغة
        if os.path.exists(PAPERS_F):
            return {"failed": 1, "why": "تعذّرَ الجلبُ — أُبقيت النسخةُ الأخيرة"}
        json.dump({"updated": _now(), "items": [], "n": 0},
                  open(PAPERS_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return {"failed": 1, "why": "تعذّرَ الجلبُ من المنبعَين"}

    ar = _arabize(papers)
    doc = {"updated": _now(),
           "note": "الورقةُ مصدرٌ أوّل — الرابطُ يُحيلُ إليها نفسِها لا إلى خبرٍ عنها",
           "items": papers, "n": len(papers)}
    json.dump(doc, open(PAPERS_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"📚 الورّاق: {len(papers)} ورقةً ({ar} معرّبة)")
    return {"why": f"{len(papers)} ورقةً · {ar} معرّبة"}


if __name__ == "__main__":
    print(json.dumps(warraq(), ensure_ascii=False))
