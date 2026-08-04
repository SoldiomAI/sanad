# -*- coding: utf-8 -*-
"""Daily viral social pack: feed + story PNGs, Arabic voice, Telegram delivery.

RTL: when Pillow is built with RAQM/HarfBuzz, pass logical Arabic as-is.
Manual arabic-reshaper+bidi is only a fallback (and must never double-apply).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, features as _pil_features

    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
    except Exception:
        arabic_reshaper = None  # type: ignore
        get_display = None  # type: ignore
except Exception as e:  # pragma: no cover
    Image = None  # type: ignore
    _IMPORT_ERR = e
    _HAS_RAQM = False
else:
    _IMPORT_ERR = None
    try:
        _HAS_RAQM = bool(_pil_features.check("raqm"))
    except Exception:
        _HAS_RAQM = False

if os.environ.get("SANAD_REQUIRE_RAQM") and Image is not None and not _HAS_RAQM:
    raise SystemExit(
        "SANAD_REQUIRE_RAQM=1 but Pillow has no RAQM — refusing to generate broken Arabic cards"
    )

OUT = os.environ.get("SANAD_DAILY", "daily")
SITE = "https://isnad.news"
_KW = timezone(timedelta(hours=3))
FONTS = Path(__file__).resolve().parent / "assets" / "fonts"

# Kuwaiti male news voice — brand-aligned for Sanad
VOICE = os.environ.get("SANAD_SOCIAL_VOICE", "ar-KW-FahedNeural")
VOICE_RATE = os.environ.get("SANAD_SOCIAL_VOICE_RATE", "-2%")

VIRAL_CATS = {"عاجل", "الخليج", "إيران", "فلسطين", "تقنية"}
VIRAL_RE = re.compile(
    r"مسير|صاروخ|غارة|عاجل|قصف|تفجير|توتر|هجوم|إسقاط|تدمير|اشتباك|"
    r"ذكاء اصطناع|حظر|عقوبات|ناقلة|هرمز|غزة|شهيد|شهداء|انفجار|اختراق|"
    r"drone|strike|missile|sanction|hormuz|gaza",
    re.I,
)
VIRAL_MIN = int(os.environ.get("SANAD_SOCIAL_VIRAL_MIN", "55"))

HOOKS = [
    "خبرٌ وُزِن قبل النشر.",
    "درجة إسناد ظاهرة — لا ضباب.",
    "من غرفة سَنَد: حكمٌ واضح على الخبر.",
    "صحيح أو حسن فقط على البطاقة.",
    "المصدر ظاهر · الدرجة ظاهرة.",
]


def _ar(text: str) -> str:
    """Prepare Arabic for Pillow draw/measure.

    With RAQM: return logical Arabic (HarfBuzz shapes correctly).
    Without RAQM: reshape + bidi once for visual LTR blit.
    """
    text = str(text or "")
    if not text.strip():
        return ""
    if _HAS_RAQM:
        return text
    if arabic_reshaper and get_display:
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            return text
    return text


def _font(name: str, size: int):
    path = FONTS / name
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _font_ar(bold: bool, size: int):
    return _font("NotoNaskhArabic-Bold.ttf" if bold else "NotoNaskhArabic-Regular.ttf", size)


def _font_lat(bold: bool, size: int):
    return _font("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)


def _draw_kw():
    """Pillow text kwargs for correct Arabic shaping."""
    if _HAS_RAQM:
        return {"direction": "rtl", "language": "ar"}
    return {}


# Latin/ASCII + punctuation missing from Naskh cmap → DejaVu
_LAT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/@-]*|[|/·•—–−-]+")


def _script_runs(text: str) -> list[tuple[str, bool]]:
    """Split into (chunk, is_arabic_font) runs. Keep Arabic phrases intact (incl. spaces)."""
    text = str(text or "")
    parts: list[tuple[str, bool]] = []
    pos = 0
    for m in _LAT_RE.finditer(text):
        if m.start() > pos:
            parts.append((text[pos : m.start()], True))
        parts.append((m.group(), False))
        pos = m.end()
    if pos < len(text):
        parts.append((text[pos:], True))
    return [(c, ar) for c, ar in parts if c]


def _text_w(draw, text: str, font_ar, font_lat) -> float:
    """Width of mixed Arabic/Latin (drawn RTL: Arabic Naskh + Latin DejaVu)."""
    kw = _draw_kw()
    w = 0.0
    for chunk, is_ar in _script_runs(text):
        if is_ar:
            w += draw.textlength(_ar(chunk), font=font_ar, **kw)
        else:
            w += draw.textlength(chunk, font=font_lat)
    return w


def _draw_rtl(draw, xy, text: str, *, font_ar, font_lat, fill, v_anchor: str = "a"):
    """Draw mixed text right-aligned; Arabic shaped via RAQM, Latin via DejaVu.

    Logical order is painted from the right edge (first logical run sits on the right).
    v_anchor: 'a' (baseline) or 'm' (vertical middle).
    """
    text = str(text or "")
    if not text:
        return
    x, y = xy
    y_anchor = "rm" if v_anchor == "m" else "ra"
    kw = _draw_kw()
    cursor = x
    for chunk, is_ar in _script_runs(text):
        font = font_ar if is_ar else font_lat
        s = _ar(chunk) if is_ar else chunk
        draw_kw = kw if is_ar else {}
        width = draw.textlength(s, font=font, **draw_kw)
        draw.text((cursor, y), s, font=font, fill=fill, anchor=y_anchor, **draw_kw)
        cursor -= width


def _wrap(draw, text, font_ar, font_lat, max_w):
    """Wrap logical Arabic; measure the same form that will be drawn."""
    words = str(text or "").split()
    if not words:
        return []
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = cur + " " + w
        if _text_w(draw, trial, font_ar, font_lat) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _cmt_hash(s: str) -> str:
    h = 2166136261
    for ch in str(s or ""):
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return f"{h:08x}"


def post_pid(it: dict) -> str:
    raw = (it.get("link") or it.get("head") or "") + ""
    return _cmt_hash(raw)


def kw_today() -> str:
    return datetime.now(_KW).date().isoformat()


def load_news():
    p = Path(OUT) / "news.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def all_items(news: dict):
    out = []
    for cat, arr in (news.get("cats") or {}).items():
        for i in arr or []:
            d = dict(i)
            d["cat"] = cat
            out.append(d)
    return out


def viral_score(i: dict) -> int:
    """0–100-ish shareability score. Only high scores become social packs."""
    if not i or i.get("grade") not in ("صحيح", "حسن"):
        return 0
    if not i.get("isnad") and i.get("grade") != "صحيح":
        # prefer items with isnad; still allow صحيح
        pass
    score = 0
    score += 38 if i.get("grade") == "صحيح" else 22
    score += min(25, int(i.get("score") or 0) * 4)
    if i.get("cat") in VIRAL_CATS:
        score += 14
    if i.get("cat") == "عاجل":
        score += 10
    head = i.get("head") or ""
    if VIRAL_RE.search(head):
        score += 18
    try:
        age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(i.get("at") or "1970-01-01")).total_seconds() / 3600
        if age_h < 6:
            score += 12
        elif age_h < 18:
            score += 6
    except Exception:
        pass
    # length: punchy headlines share better
    n = len(head)
    if 28 <= n <= 90:
        score += 6
    elif n > 140:
        score -= 8
    return score


def select_social_story(news: dict | None = None, *, viral_only: bool = True):
    news = news if news is not None else load_news()
    items = all_items(news)
    auth = [i for i in items if i.get("grade") in ("صحيح", "حسن")]
    if not auth:
        return None
    ranked = sorted(auth, key=lambda i: (viral_score(i), i.get("score") or 0), reverse=True)
    top = ranked[0]
    vs = viral_score(top)
    if viral_only and vs < VIRAL_MIN:
        print(f"⏭️ social skip — top viral_score={vs} < {VIRAL_MIN}: {(top.get('head') or '')[:60]}")
        return None
    top = dict(top)
    top["_viral_score"] = vs
    return top


def _draw_card(size, story: dict, variant: str) -> Image.Image:
    W, H = size
    img = Image.new("RGB", (W, H), "#F3EEE3")
    d = ImageDraw.Draw(img)
    # warm top wash + gold edge
    for y in range(0, int(H * 0.22)):
        mix = y / max(1, H * 0.22)
        r = int(228 + (243 - 228) * mix)
        g = int(214 + (238 - 214) * mix)
        b = int(188 + (227 - 188) * mix)
        d.line([(0, y), (W, y)], fill=(r, g, b))
    d.rectangle([0, 0, 16 if variant == "feed" else 20, H], fill="#C9A227")
    # subtle bottom ink band
    d.rectangle([0, H - 140 if variant == "feed" else H - 180, W, H], fill="#1A1206")

    brand = _font_ar(True, 62 if variant == "feed" else 70)
    head_f = _font_ar(True, 56 if variant == "feed" else 60)
    meta_f = _font_ar(False, 30 if variant == "feed" else 32)
    small = _font_ar(False, 26)
    lat_meta = _font_lat(False, 28 if variant == "feed" else 30)
    lat_small = _font_lat(False, 24)

    pad = 64 if variant == "feed" else 72
    _draw_rtl(d, (W - pad, pad), "سَنَد", font_ar=brand, font_lat=lat_meta, fill="#1A1206")
    _draw_rtl(
        d,
        (W - pad, pad + 74),
        "بطاقة اليوم — وُزِن قبل النشر",
        font_ar=small,
        font_lat=lat_small,
        fill="#7A6A4A",
    )

    grade = story.get("grade") or ""
    cat = story.get("cat") or ""
    badge = "صحيح" if grade == "صحيح" else ("حسن" if grade == "حسن" else grade)
    badge_col = "#2F6B4F" if grade == "صحيح" else "#8A6A1F"
    by = pad + 124
    bw = int(_text_w(d, badge, meta_f, lat_meta)) + (52 if grade == "صحيح" else 36)
    bx = W - pad - bw
    d.rounded_rectangle([bx, by, bx + bw, by + 50], radius=12, fill=badge_col)
    if grade == "صحيح":
        # geometric check — avoid Unicode ✓ (missing from Naskh)
        cx0, cy0 = bx + 18, by + 25
        d.line([(cx0 - 6, cy0), (cx0 - 1, cy0 + 6), (cx0 + 9, cy0 - 7)], fill="#F7F1E4", width=3)
        text_right = bx + bw - 14
    else:
        text_right = bx + bw / 2 + _text_w(d, badge, meta_f, lat_meta) / 2
    _draw_rtl(
        d, (text_right, by + 25), badge, font_ar=meta_f, font_lat=lat_meta, fill="#F7F1E4", v_anchor="m"
    )
    if cat:
        cw = int(_text_w(d, cat, small, lat_small)) + 28
        cx = bx - 14 - cw
        d.rounded_rectangle([cx, by + 4, cx + cw, by + 46], radius=12, outline="#C9A227", width=2)
        _draw_rtl(
            d,
            (cx + cw - 14, by + 25),
            cat,
            font_ar=small,
            font_lat=lat_small,
            fill="#8A6F1B",
            v_anchor="m",
        )

    head = story.get("head") or ""
    max_w = W - pad * 2
    lines = _wrap(d, head, head_f, lat_meta, max_w)[:6]
    y = int(H * 0.36) if variant == "feed" else int(H * 0.32)
    for line in lines:
        _draw_rtl(d, (W - pad, y), line, font_ar=head_f, font_lat=lat_meta, fill="#1A1206")
        y += int(head_f.size * 1.42)

    src = story.get("src") or "مصدر"
    foot_y = H - (90 if variant == "feed" else 120)
    _draw_rtl(
        d,
        (W - pad, foot_y),
        f"المصدر — {src}",
        font_ar=meta_f,
        font_lat=lat_meta,
        fill="#E8DFC8",
    )
    _draw_rtl(
        d,
        (W - pad, foot_y + 44),
        "isnad.news",
        font_ar=meta_f,
        font_lat=_font_lat(True, 28 if variant == "feed" else 30),
        fill="#C9A227",
    )
    return img


def build_texts(story: dict, date: str) -> dict:
    pid = post_pid(story)
    url = f"{SITE}/#/post/{pid}"
    grade = story.get("grade") or ""
    src = story.get("src") or ""
    head = story.get("head") or ""
    hook = HOOKS[int(hashlib.md5(date.encode()).hexdigest(), 16) % len(HOOKS)]
    caption_ar = (
        f"{hook}\n\n"
        f"«{head}»\n"
        f"درجة الإسناد: {grade}" + (f" · {src}" if src else "") + "\n\n"
        f"——\n"
        f"سَنَد يزن الخبر قبل النشر\n"
        f"{url}"
    )
    he = (story.get("he") or "").strip()
    caption_en = ""
    if he and not any("\u0600" <= c <= "\u06FF" for c in he):
        g_en = "Verified ✓" if grade == "صحيح" else ("Credible" if grade == "حسن" else grade)
        caption_en = (
            f"Graded before publish.\n\n"
            f"“{he}”\n"
            f"Attribution: {g_en}" + (f" · {src}" if src else "") + "\n\n"
            f"——\nSanad · {url}"
        )
    story_text = f"سَنَد — {grade}\n{head[:90]}{'…' if len(head) > 90 else ''}\n{url}"
    # Fully vocalized opener — partial diacritics confuse Edge TTS
    g_say = "صَحِيح" if grade == "صحيح" else ("حَسَن" if grade == "حسن" else grade)
    spoken = f"خَبَرٌ مِنْ سَنَد. دَرَجَةُ الإِسْنَادِ: {g_say}. {head}"
    if len(spoken) > 220:
        spoken = spoken[:217] + "…"
    return {
        "caption_ar": caption_ar,
        "caption_en": caption_en,
        "story_text": story_text,
        "spoken": spoken,
        "pid": pid,
        "post_url": url,
    }


def synthesize_voice(text: str, dest: Path) -> bool:
    """Kuwaiti Fahed neural — short viral voiceover."""
    try:
        import edge_tts
        import ssl as _ssl

        _ssl._create_default_https_context = _ssl._create_unverified_context
    except Exception as e:
        print("voice: edge_tts missing " + str(e)[:60])
        return False

    async def _run():
        comm = edge_tts.Communicate(text, VOICE, rate=VOICE_RATE)
        await comm.save(str(dest))

    try:
        asyncio.run(_run())
        ok = dest.exists() and dest.stat().st_size > 1000
        if ok:
            print(f"🎙️ social voice · {VOICE} · {dest.stat().st_size}b")
        return ok
    except Exception as e:
        print("voice failed: " + str(e)[:100])
        return False


def pack_dir(date: str) -> Path:
    return Path(OUT) / "social" / date


def write_index():
    root = Path(OUT) / "social"
    root.mkdir(parents=True, exist_ok=True)
    cols = []
    for p in sorted(root.glob("20*/meta.json"), reverse=True):
        try:
            m = json.loads(p.read_text())
        except Exception:
            continue
        cols.append(
            {
                "date": m.get("date"),
                "head": m.get("head"),
                "grade": m.get("grade"),
                "status": m.get("status"),
                "viral_score": m.get("viral_score"),
                "post_url": m.get("post_url"),
                "updated": m.get("updated"),
            }
        )
    idx = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "n": len(cols),
        "packs": cols[:60],
    }
    (root / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    return idx


def render_social_pack(story: dict | None = None, date: str | None = None, force: bool = False) -> dict:
    if Image is None:
        raise RuntimeError(f"Pillow/arabic deps missing: {_IMPORT_ERR}")
    date = date or kw_today()
    dest = pack_dir(date)
    meta_path = dest / "meta.json"
    if meta_path.exists() and not force and not os.environ.get("FORCE_SOCIAL"):
        return json.loads(meta_path.read_text())

    story = story or select_social_story(viral_only=True)
    if not story:
        dest.mkdir(parents=True, exist_ok=True)
        meta = {
            "date": date,
            "status": "skipped",
            "reason": "no viral authenticated story",
            "viral_min": VIRAL_MIN,
            "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        write_index()
        return meta

    texts = build_texts(story, date)
    dest.mkdir(parents=True, exist_ok=True)
    feed = _draw_card((1080, 1080), story, "feed")
    story_img = _draw_card((1080, 1920), story, "story")
    feed.save(dest / "feed.png", optimize=True)
    story_img.save(dest / "story.png", optimize=True)
    (dest / "caption_ar.txt").write_text(texts["caption_ar"], encoding="utf-8")
    if texts["caption_en"]:
        (dest / "caption_en.txt").write_text(texts["caption_en"], encoding="utf-8")
    (dest / "story_text.txt").write_text(texts["story_text"], encoding="utf-8")
    (dest / "spoken.txt").write_text(texts["spoken"], encoding="utf-8")
    voice_ok = synthesize_voice(texts["spoken"], dest / "voice.mp3")

    meta = {
        "date": date,
        "status": "ready",
        "platform": ["instagram_feed", "instagram_story", "whatsapp", "telegram", "reel_audio"],
        "head": story.get("head") or "",
        "he": story.get("he") or "",
        "grade": story.get("grade") or "",
        "src": story.get("src") or "",
        "cat": story.get("cat") or "",
        "link": story.get("link") or "",
        "score": story.get("score"),
        "viral_score": story.get("_viral_score") or viral_score(story),
        "voice": VOICE if voice_ok else "",
        "raqm": _HAS_RAQM,
        "post_url": texts["post_url"],
        "pid": texts["pid"],
        "assets": {
            "feed": "feed.png",
            "story": "story.png",
            "caption_ar": "caption_ar.txt",
            "caption_en": "caption_en.txt" if texts["caption_en"] else "",
            "story_text": "story_text.txt",
            "spoken": "spoken.txt",
            "voice": "voice.mp3" if voice_ok else "",
        },
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    write_index()
    print(
        f"🖼️ social pack {date}: {story.get('grade')} · viral={meta['viral_score']} · raqm={_HAS_RAQM} · "
        f"{(story.get('head') or '')[:50]}"
    )
    return meta


def _tg_token_chat():
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TG_TOKEN") or ""
    chat = (
        os.environ.get("TELEGRAM_EDITOR_CHAT")
        or os.environ.get("TELEGRAM_CHANNEL")
        or os.environ.get("TG_CHAT")
        or ""
    )
    return token, chat


def tg_send_photo(path: str, caption: str = "") -> bool:
    token, chat = _tg_token_chat()
    if not (token and chat and path and os.path.exists(path)):
        return False
    try:
        import uuid as _u

        bnd = "----sanad" + _u.uuid4().hex
        parts = []

        def fld(n, v):
            parts.append(
                f"--{bnd}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n".encode()
            )

        fld("chat_id", chat)
        if caption:
            fld("caption", caption[:1024])
            fld("parse_mode", "HTML")
        fname = os.path.basename(path)
        parts.append(
            f"--{bnd}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{fname}\"\r\nContent-Type: image/png\r\n\r\n".encode()
        )
        parts.append(open(path, "rb").read())
        parts.append(f"\r\n--{bnd}--\r\n".encode())
        body = b"".join(parts)
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={bnd}"},
        )
        r = json.load(urllib.request.urlopen(req, timeout=90))
        return bool(r.get("ok"))
    except Exception as e:
        print(f"تلغرام صورة تعذّر: {str(e)[:100]}")
        return False


def tg_send_audio(path: str, caption: str = "") -> bool:
    token, chat = _tg_token_chat()
    if not (token and chat and path and os.path.exists(path)):
        return False
    try:
        import uuid as _u

        bnd = "----sanad" + _u.uuid4().hex
        parts = []

        def fld(n, v):
            parts.append(
                f"--{bnd}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n".encode()
            )

        fld("chat_id", chat)
        if caption:
            fld("caption", caption[:1024])
        fname = os.path.basename(path)
        parts.append(
            f"--{bnd}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"{fname}\"\r\nContent-Type: audio/mpeg\r\n\r\n".encode()
        )
        parts.append(open(path, "rb").read())
        parts.append(f"\r\n--{bnd}--\r\n".encode())
        body = b"".join(parts)
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendAudio",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={bnd}"},
        )
        r = json.load(urllib.request.urlopen(req, timeout=90))
        return bool(r.get("ok"))
    except Exception as e:
        print(f"تلغرام صوت تعذّر: {str(e)[:100]}")
        return False


def tg_send_message(text: str) -> bool:
    token, chat = _tg_token_chat()
    if not (token and chat):
        return False
    try:
        d = json.dumps(
            {
                "chat_id": chat,
                "text": text[:4000],
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }
        ).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=d,
            headers={"Content-Type": "application/json"},
        )
        r = json.load(urllib.request.urlopen(req, timeout=60))
        return bool(r.get("ok"))
    except Exception as e:
        print(f"تلغرام نص تعذّر: {str(e)[:100]}")
        return False


def _tg_state():
    p = Path(OUT) / "tg.json"
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _tg_save(st):
    Path(OUT).mkdir(parents=True, exist_ok=True)
    (Path(OUT) / "tg.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def broadcast_social_pack(meta: dict | None = None, force: bool = False) -> bool:
    """Send today's pack to the configured Telegram chat (channel or editor)."""
    date = (meta or {}).get("date") or kw_today()
    dest = pack_dir(date)
    if meta is None:
        mp = dest / "meta.json"
        if not mp.exists():
            return False
        meta = json.loads(mp.read_text())
    if meta.get("status") != "ready":
        return False
    st = _tg_state()
    if st.get("social_pack") == date and not force and not os.environ.get("FORCE_SOCIAL"):
        print("⏱️ social pack already sent today")
        return True

    feed = dest / "feed.png"
    story = dest / "story.png"
    voice = dest / "voice.mp3"
    cap = (dest / "caption_ar.txt").read_text(encoding="utf-8") if (dest / "caption_ar.txt").exists() else ""
    head = meta.get("head") or ""
    grade = meta.get("grade") or ""
    url = meta.get("post_url") or SITE
    vs = meta.get("viral_score")
    intro = (
        f"🖼️ <b>بطاقة سَنَد اليومية</b> — {date}\n"
        f"⚖️ {grade}" + (f" · viral {vs}" if vs is not None else "") + "\n"
        f"{head}\n\n"
        f"<a href=\"{url}\">افتح على سَنَد ↗</a>"
    )
    ok1 = tg_send_photo(str(feed), intro)
    ok2 = tg_send_photo(str(story), "نسخة الستوري · 1080×1920 · عربي صحيح")
    okv = tg_send_audio(str(voice), f"🎙️ صوت كويتي · {meta.get('voice') or VOICE}") if voice.exists() else False
    ok3 = tg_send_message(f"<b>كابشن إنستغرام (انسخ):</b>\n\n{cap[:3500]}")
    if ok1 or ok2 or ok3 or okv:
        st["social_pack"] = date
        _tg_save(st)
        print(f"📣 social pack sent · photo={ok1}/{ok2} voice={okv} text={ok3}")
        return True
    print("⚠️ social pack Telegram send failed (missing secrets or API error)")
    return False


def social_pack(force: bool = False) -> dict:
    meta = render_social_pack(force=force or bool(os.environ.get("FORCE_SOCIAL")))
    if meta.get("status") == "ready":
        broadcast_social_pack(meta, force=force or bool(os.environ.get("FORCE_SOCIAL")))
    return meta


if __name__ == "__main__":
    force = bool(os.environ.get("FORCE_SOCIAL"))
    m = social_pack(force=force)
    print(
        json.dumps(
            {k: m.get(k) for k in ("date", "status", "grade", "viral_score", "voice", "raqm", "head", "post_url")},
            ensure_ascii=False,
        )
    )
