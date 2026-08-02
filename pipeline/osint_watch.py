# -*- coding: utf-8 -*-
"""Enterprise OSINT keyword / hashtag watch — open-source intel layer.

Scans seeded hashtags & keywords across:
  • Sanad graded corpus (today + recent archive)
  • Google News RSS (Arabic / KW)

Produces daily/osint.json for the Enterprise portal.
Inspired by multi-channel reach patterns (Agent-Reach philosophy:
prefer free, attributable open paths — no paid social API keys in CI).
Deep Twitter/X session reach remains org-side via Agent-Reach if needed.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = os.environ.get("SANAD_DAILY", "daily")
_UA = (
    "Mozilla/5.0 (compatible; SanadOSINT/1.0; +https://isnad.news/enterprise)"
)

# Default Gulf / regional intel seeds (hashtags + keywords)
_DEFAULT_SEEDS = [
    {"term": "#إيران", "kind": "hashtag", "en": "#Iran", "topic": "إيران"},
    {"term": "#غزة", "kind": "hashtag", "en": "#Gaza", "topic": "فلسطين"},
    {"term": "#الكويت", "kind": "hashtag", "en": "#Kuwait", "topic": "الخليج"},
    {"term": "#السعودية", "kind": "hashtag", "en": "#Saudi", "topic": "الخليج"},
    {"term": "#مضيق_هرمز", "kind": "hashtag", "en": "#StraitOfHormuz", "topic": "ملاحة"},
    {"term": "مضيق هرمز", "kind": "keyword", "en": "Strait of Hormuz", "topic": "ملاحة"},
    {"term": "الحوثي", "kind": "keyword", "en": "Houthi", "topic": "اليمن"},
    {"term": "حزب الله", "kind": "keyword", "en": "Hezbollah", "topic": "لبنان"},
    {"term": "سنتكم", "kind": "keyword", "en": "CENTCOM", "topic": "أمن"},
    {"term": "ترامب إيران", "kind": "keyword", "en": "Trump Iran", "topic": "إيران"},
    {"term": "عقوبات", "kind": "keyword", "en": "sanctions", "topic": "اقتصاد"},
    {"term": "ناقلة نفط", "kind": "keyword", "en": "oil tanker", "topic": "طاقة"},
]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


def _load_seeds() -> list:
    path = Path(OUT, "osint_seeds.json")
    seeds = list(_DEFAULT_SEEDS)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            extra = raw.get("seeds") if isinstance(raw, dict) else raw
            for s in extra or []:
                if isinstance(s, str):
                    term = s.strip()
                    if not term:
                        continue
                    seeds.append(
                        {
                            "term": term,
                            "kind": "hashtag" if term.startswith("#") else "keyword",
                            "en": term,
                            "topic": "مخصص",
                        }
                    )
                elif isinstance(s, dict) and s.get("term"):
                    seeds.append(
                        {
                            "term": str(s["term"]).strip(),
                            "kind": s.get("kind")
                            or ("hashtag" if str(s["term"]).startswith("#") else "keyword"),
                            "en": s.get("en") or s["term"],
                            "topic": s.get("topic") or "مخصص",
                        }
                    )
        except Exception as e:
            print("osint_seeds: " + str(e)[:80])
    env = os.environ.get("OSINT_KEYWORDS", "").strip()
    if env:
        for part in re.split(r"[,|\n]", env):
            term = part.strip()
            if term:
                seeds.append(
                    {
                        "term": term,
                        "kind": "hashtag" if term.startswith("#") else "keyword",
                        "en": term,
                        "topic": "env",
                    }
                )
    # de-dupe by normalized term
    seen = set()
    out = []
    for s in seeds:
        key = re.sub(r"\s+", " ", s["term"]).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out[:40]  # hard cap for CI cost/time


def _norm(s: str) -> str:
    s = str(s or "").lower()
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ة", "ه").replace("ى", "ي")
    s = s.replace("#", "")
    return s


def _hit_blob(term: str, *parts) -> bool:
    t = _norm(term)
    if not t:
        return False
    blob = _norm(" ".join(str(p or "") for p in parts))
    if term.startswith("#") or " " not in term.strip():
        return t in blob
    # multi-word: all tokens
    return all(tok in blob for tok in t.split() if tok)


def _collect_sanad_items(days: int = 3) -> list:
    items = []
    seen = set()

    def add(cats, stamp):
        if not isinstance(cats, dict):
            return
        for cat, lst in cats.items():
            for it in lst or []:
                if not isinstance(it, dict):
                    continue
                g = it.get("grade") or ""
                if g not in ("صحيح", "حسن"):
                    continue
                key = (it.get("link") or it.get("head") or "")[:180]
                if not key or key in seen:
                    continue
                seen.add(key)
                d = dict(it)
                d["cat"] = cat
                d["_snap"] = stamp
                d["_channel"] = "sanad"
                items.append(d)

    try:
        news = json.loads(Path(OUT, "news.json").read_text(encoding="utf-8"))
        add(news.get("cats"), "today")
    except Exception:
        pass

    idx = Path(OUT, "archive", "index.json")
    try:
        snaps = (json.loads(idx.read_text(encoding="utf-8")).get("snaps") or [])[-40:]
    except Exception:
        snaps = []
    days_have = set()
    for s in reversed(snaps):
        sid = s.get("id") or ""
        day = sid[:10]
        if not re.match(r"\d{4}-\d{2}-\d{2}", day):
            continue
        if day in days_have:
            continue
        path = Path(OUT, "archive", f"{sid}.json")
        if not path.exists():
            continue
        try:
            snap = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        add(snap.get("cats"), sid)
        days_have.add(day)
        if len(days_have) >= days:
            break
    return items


def _fetch_bytes(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/rss+xml,application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(400_000)


def _parse_rss(data: bytes) -> list:
    out = []
    try:
        root = ET.fromstring(data)
    except Exception:
        return out
    # RSS 2.0
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        src_el = item.find("{http://purl.org/dc/elements/1.1/}source")
        if src_el is None:
            src_el = item.find("source")
        src = (src_el.text if src_el is not None and src_el.text else "") or ""
        pub = (item.findtext("pubDate") or "").strip()
        if title and link:
            out.append({"head": title, "link": link, "src": src or "Google News", "at": pub, "grade": "", "channel": "gnews"})
    return out[:25]


def _gnews_hits(term: str) -> list:
    # strip # for query; keep Arabic
    q = term.lstrip("#").strip()
    if not q:
        return []
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(q)
        + "&hl=ar&gl=KW&ceid=KW:ar"
    )
    try:
        return _parse_rss(_fetch_bytes(url))
    except Exception as e:
        print(f"osint gnews [{q[:30]}]: " + str(e)[:80])
        return []


def _heat(n_sanad: int, n_open: int, sahih: int) -> int:
    return min(100, sahih * 20 + n_sanad * 10 + min(40, n_open * 4))


def build_osint() -> dict:
    seeds = _load_seeds()
    corpus = _collect_sanad_items(3)
    watches = []
    total_hits = 0

    for seed in seeds:
        term = seed["term"]
        sanad_hits = []
        for it in corpus:
            if _hit_blob(term, it.get("head"), it.get("he"), it.get("src"), it.get("cat")):
                sanad_hits.append(
                    {
                        "head": it.get("head") or "",
                        "he": it.get("he") or "",
                        "grade": it.get("grade") or "",
                        "src": it.get("src") or "",
                        "link": it.get("link") or "",
                        "at": it.get("at") or "",
                        "channel": "sanad",
                    }
                )
        sanad_hits = sorted(
            sanad_hits,
            key=lambda x: (3 if x["grade"] == "صحيح" else 2, x.get("at") or ""),
            reverse=True,
        )[:8]

        open_hits = []
        for h in _gnews_hits(term):
            # skip if already in sanad by link/head
            key = (h.get("link") or h.get("head") or "")[:120]
            if any((x.get("link") or "")[:120] == key for x in sanad_hits):
                continue
            open_hits.append(
                {
                    "head": h.get("head") or "",
                    "he": "",
                    "grade": "",
                    "src": h.get("src") or "Google News",
                    "link": h.get("link") or "",
                    "at": h.get("at") or "",
                    "channel": "gnews",
                }
            )
        open_hits = open_hits[:8]

        sahih = sum(1 for x in sanad_hits if x["grade"] == "صحيح")
        hasan = sum(1 for x in sanad_hits if x["grade"] == "حسن")
        n_s, n_o = len(sanad_hits), len(open_hits)
        heat = _heat(n_s, n_o, sahih)
        total_hits += n_s + n_o

        summary = (
            f"«{term}»: {n_s} خبرًا مُسنَدًا من سَنَد"
            + (f" ({sahih} صحيح · {hasan} حسن)" if n_s else "")
            + (f" و{n_o} إشارة مفتوحة من الأخبار" if n_o else "")
            + "."
        )
        summary_en = (
            f"“{seed.get('en') or term}”: {n_s} graded Sanad hits"
            + (f" ({sahih} verified · {hasan} credible)" if n_s else "")
            + (f" and {n_o} open news signals" if n_o else "")
            + "."
        )

        watches.append(
            {
                "term": term,
                "en": seed.get("en") or term,
                "kind": seed.get("kind") or "keyword",
                "topic": seed.get("topic") or "",
                "heat": heat,
                "n_sanad": n_s,
                "n_open": n_o,
                "sahih": sahih,
                "hasan": hasan,
                "summary": summary,
                "summary_en": summary_en,
                "hits": sanad_hits + open_hits,
            }
        )

    watches.sort(key=lambda w: (-w["heat"], -w["n_sanad"], w["term"]))
    active = sum(1 for w in watches if w["heat"] > 0)
    out = {
        "updated": _now(),
        "note": "رصدُ كلماتٍ وهاشتاقاتٍ للمؤسسات — حصيلة سَنَد المُسنَدة + إشارات أخبار مفتوحة منسوبة. ليس حكمًا استخباراتيًّا رسميًّا.",
        "note_en": "Enterprise keyword/hashtag watch — graded Sanad corpus + attributable open news signals. Not an official intelligence assessment.",
        "channels": ["sanad", "gnews"],
        "reach_note": "Deep social (X/Twitter, Reddit sessions) is org-operated; see Agent-Reach for session-based reach: https://github.com/Panniantong/Agent-Reach",
        "seeds": len(seeds),
        "active": active,
        "total_hits": total_hits,
        "watches": watches,
    }
    Path(OUT).mkdir(parents=True, exist_ok=True)
    Path(OUT, "osint.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"🛰️ OSINT: {active}/{len(watches)} مصطلحًا نشطًا · {total_hits} إشارة")
    return out


def osint_watch():
    return build_osint()


if __name__ == "__main__":
    m = osint_watch()
    print(json.dumps({k: m.get(k) for k in ("updated", "active", "seeds", "total_hits")}, ensure_ascii=False))
