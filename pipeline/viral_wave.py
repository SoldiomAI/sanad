# -*- coding: utf-8 -*-
"""Viral wave + market pulse for the public home feed.

Builds daily/wave.json:
  • pulse: oil / gold / BTC (public quotes, not investment advice)
  • cards: top graded story, hottest map country, AI/tech pick

Designed for shareability — short labels, clear CTAs, no trading tips.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = os.environ.get("SANAD_DAILY", "daily")
_UA = "Mozilla/5.0 (compatible; SanadWave/1.0; +https://isnad.news)"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


def _get_json(url: str, timeout: int = 12):
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(500_000).decode("utf-8", "replace"))


def _yahoo_quote(symbol: str) -> dict | None:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + symbol
        + "?interval=1d&range=5d"
    )
    try:
        d = _get_json(url)
        meta = ((d.get("chart") or {}).get("result") or [{}])[0].get("meta") or {}
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if price is None:
            return None
        chg = None
        if prev:
            chg = ((float(price) - float(prev)) / float(prev)) * 100.0
        return {
            "price": round(float(price), 2),
            "prev": round(float(prev), 2) if prev else None,
            "chg_pct": round(float(chg), 2) if chg is not None else None,
            "currency": meta.get("currency") or "USD",
            "src": "Yahoo Finance",
        }
    except Exception as e:
        print(f"pulse yahoo {symbol}: " + str(e)[:80])
        return None


def _btc_quote() -> dict | None:
    try:
        d = _get_json(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
        )
        b = d.get("bitcoin") or {}
        if "usd" not in b:
            return None
        return {
            "price": round(float(b["usd"]), 2),
            "prev": None,
            "chg_pct": round(float(b.get("usd_24h_change") or 0), 2),
            "currency": "USD",
            "src": "CoinGecko",
        }
    except Exception as e:
        print("pulse btc: " + str(e)[:80])
        return None


def _load_json(name: str):
    p = Path(OUT, name)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _auth_items(news: dict) -> list:
    out = []
    for cat, lst in (news.get("cats") or {}).items():
        for it in lst or []:
            if not isinstance(it, dict):
                continue
            if it.get("grade") not in ("صحيح", "حسن"):
                continue
            d = dict(it)
            d["cat"] = cat
            out.append(d)
    out.sort(
        key=lambda i: (
            3 if i.get("grade") == "صحيح" else 2,
            i.get("score") or 0,
            str(i.get("at") or ""),
        ),
        reverse=True,
    )
    return out


def _is_ai(it: dict) -> bool:
    if it.get("cat") == "تقنية":
        return True
    blob = " ".join(str(it.get(k) or "") for k in ("head", "he", "src")).lower()
    keys = (
        "ذكاء اصطناع",
        "الذكاء الاصطناعي",
        "openai",
        "chatgpt",
        "gpt-",
        "claude",
        "gemini",
        "deepmind",
        "huggingface",
        " large language",
        "llm",
        "artificial intelligence",
        "generative ai",
    )
    return any(k in blob for k in keys)


def _card_story(it: dict) -> dict:
    return {
        "kind": "story",
        "head": it.get("head") or "",
        "he": it.get("he") or "",
        "grade": it.get("grade") or "",
        "src": it.get("src") or "",
        "link": it.get("link") or "",
        "at": it.get("at") or "",
        "cat": it.get("cat") or "",
        "score": it.get("score"),
        "isnad": it.get("isnad") or {},
    }


def build_wave() -> dict:
    news = _load_json("news.json")
    mmap = _load_json("map.json")
    items = _auth_items(news)

    # pulse
    oil = _yahoo_quote("CL=F")
    gold = _yahoo_quote("GC=F")
    btc = _btc_quote()
    pulse = []
    for key, label, label_en, unit, q in (
        ("oil", "نفط", "Oil", "USD/bbl", oil),
        ("gold", "ذهب", "Gold", "USD/oz", gold),
        ("btc", "بيتكوين", "Bitcoin", "USD", btc),
    ):
        if not q:
            continue
        pulse.append(
            {
                "id": key,
                "label": label,
                "label_en": label_en,
                "unit": unit,
                "price": q["price"],
                "chg_pct": q.get("chg_pct"),
                "currency": q.get("currency") or "USD",
                "src": q.get("src") or "",
            }
        )

    cards = []
    # 1) top graded story
    if items:
        top = items[0]
        cards.append(
            {
                **_card_story(top),
                "slot": "top",
                "kicker": "أبرز مُسنَد",
                "kicker_en": "Top graded",
                "cta": "شارك",
                "cta_en": "Share",
                "action": "share_story",
            }
        )

    # 2) hottest map country with summary
    countries = [c for c in (mmap.get("countries") or []) if c.get("id") != "il" and c.get("n")]
    countries.sort(key=lambda c: (-(c.get("heat") or 0), -(c.get("n") or 0)))
    if countries:
        c = countries[0]
        cards.append(
            {
                "kind": "country",
                "slot": "map",
                "id": c.get("id"),
                "name": c.get("name") or "",
                "en": c.get("en") or "",
                "heat": c.get("heat") or 0,
                "n": c.get("n") or 0,
                "summary": c.get("summary") or "",
                "summary_en": c.get("summary_en") or "",
                "kicker": "دولة على الخريطة",
                "kicker_en": "On the map",
                "cta": "افتح الخريطة",
                "cta_en": "Open map",
                "action": "open_map",
                "head": c.get("name") or "",
                "he": c.get("en") or "",
            }
        )

    # 3) AI / tech pick (prefer تقنية), else verify CTA
    ai = next((i for i in items if i.get("cat") == "تقنية"), None)
    if not ai:
        ai = next((i for i in items if _is_ai(i)), None)
    if ai and (not items or ai.get("link") != (items[0].get("link") if items else None)):
        cards.append(
            {
                **_card_story(ai),
                "slot": "ai",
                "kicker": "تقنية · ذكاء",
                "kicker_en": "Tech · AI",
                "cta": "اقرأ",
                "cta_en": "Read",
                "action": "open_story",
            }
        )
    else:
        cards.append(
            {
                "kind": "action",
                "slot": "verify",
                "kicker": "تحقّق",
                "kicker_en": "Verify",
                "head": "الصق رابطًا — حكمٌ واضح بلا كشف أدوات الغرفة",
                "he": "Paste a link — clear verdict, no toolkit exposed",
                "cta": "افحص رابطًا",
                "cta_en": "Check a link",
                "action": "open_verify",
                "grade": "",
                "src": "",
                "link": "",
            }
        )

    out = {
        "updated": _now(),
        "note": "موجة اليوم للجمهور — مشاركة سريعة. الأسعار للتوضيح العام وليست نصيحة استثمارية.",
        "note_en": "Today’s wave for everyone — quick shares. Prices are for general awareness, not investment advice.",
        "disclaimer": "الأسعار للتوضيح العام وليست نصيحة استثمارية.",
        "disclaimer_en": "Prices are for general awareness — not investment advice.",
        "pulse": pulse,
        "cards": cards[:3],
    }
    Path(OUT).mkdir(parents=True, exist_ok=True)
    Path(OUT, "wave.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        "🌊 الموجة: %d بطاقة · نبض %d%s"
        % (
            len(out["cards"]),
            len(pulse),
            (" · " + " · ".join("%s=%s" % (p["id"], p["price"]) for p in pulse)) if pulse else "",
        )
    )
    return out


def viral_wave():
    return build_wave()


if __name__ == "__main__":
    m = viral_wave()
    print(json.dumps({"updated": m["updated"], "cards": len(m["cards"]), "pulse": len(m["pulse"])}, ensure_ascii=False))
