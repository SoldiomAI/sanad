# -*- coding: utf-8 -*-
"""Daily viral social pack: feed + story PNGs, captions, Telegram delivery."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception as e:  # pragma: no cover
    Image = None  # type: ignore
    _IMPORT_ERR = e
else:
    _IMPORT_ERR = None

OUT = os.environ.get("SANAD_DAILY", "daily")
SITE = "https://isnad.news"
_KW = timezone(timedelta(hours=3))
FONTS = Path(__file__).resolve().parent / "assets" / "fonts"
HOOKS = [
    "خبرٌ وُزِن قبل النشر.",
    "درجة إسناد ظاهرة — لا ضباب.",
    "من غرفة سَنَد: حكمٌ واضح على الخبر.",
    "صحيح أو حسن فقط على البطاقة.",
    "المصدر ظاهر · الدرجة ظاهرة.",
]


def _ar(text: str) -> str:
    text = str(text or "")
    if not text.strip():
        return ""
    return get_display(arabic_reshaper.reshape(text))


def _font(name: str, size: int):
    path = FONTS / name
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words = str(text or "").split()
    if not words:
        return []
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = cur + " " + w
        if draw.textlength(_ar(trial), font=font) <= max_w:
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


def select_social_story(news: dict | None = None):
    news = news if news is not None else load_news()
    items = all_items(news)
    auth = [i for i in items if i.get("isnad") and i.get("grade") in ("صحيح", "حسن")]
    if not auth:
        auth = [i for i in items if i.get("grade") in ("صحيح", "حسن")]
    if not auth:
        return None

    def key(i):
        g = 3 if i.get("grade") == "صحيح" else 2
        try:
            t = datetime.fromisoformat(i.get("at") or "1970-01-01").timestamp()
        except Exception:
            t = 0
        return (g, t, i.get("score") or 0)

    return sorted(auth, key=key, reverse=True)[0]


def _draw_card(size, story: dict, variant: str) -> Image.Image:
    W, H = size
    # cream atmosphere + ink text (Sanad look)
    img = Image.new("RGB", (W, H), "#F4EFE4")
    d = ImageDraw.Draw(img)
    for y in range(0, int(H * 0.18)):
        mix = y / max(1, H * 0.18)
        r = int(232 + (244 - 232) * mix)
        g = int(220 + (239 - 220) * mix)
        b = int(196 + (228 - 196) * mix)
        d.line([(0, y), (W, y)], fill=(r, g, b))
    d.rectangle([0, 0, 14 if variant == "feed" else 18, H], fill="#C9A227")

    brand = _font("NotoNaskhArabic-Bold.ttf", 64 if variant == "feed" else 72)
    head_f = _font("NotoNaskhArabic-Bold.ttf", 54 if variant == "feed" else 58)
    meta_f = _font("NotoNaskhArabic-Regular.ttf", 32 if variant == "feed" else 34)
    small = _font("NotoNaskhArabic-Regular.ttf", 28)

    pad = 64 if variant == "feed" else 72
    # brand
    d.text((W - pad, pad), _ar("سَنَد"), font=brand, fill="#1A1206", anchor="ra")
    d.text((W - pad, pad + 78), _ar("يزن الخبر قبل النشر"), font=small, fill="#7A6A4A", anchor="ra")

    grade = story.get("grade") or ""
    badge = "صحيح ✓" if grade == "صحيح" else ("حسن" if grade == "حسن" else grade)
    badge_col = "#2F6B4F" if grade == "صحيح" else "#8A6A1F"
    bw = int(d.textlength(_ar(badge), font=meta_f)) + 36
    bx = W - pad - bw
    by = pad + 130
    d.rounded_rectangle([bx, by, bx + bw, by + 52], radius=12, fill=badge_col)
    d.text((bx + bw / 2, by + 26), _ar(badge), font=meta_f, fill="#F7F1E4", anchor="mm")

    head = story.get("head") or ""
    max_w = W - pad * 2
    lines = _wrap(d, head, head_f, max_w)[:7]
    y = int(H * 0.38) if variant == "feed" else int(H * 0.34)
    for line in lines:
        d.text((W - pad, y), _ar(line), font=head_f, fill="#1A1206", anchor="ra")
        y += int(head_f.size * 1.45)

    src = story.get("src") or "مصدر"
    d.text((W - pad, H - pad - 90), _ar(f"المصدر · {src}"), font=meta_f, fill="#5C4E38", anchor="ra")
    d.text((W - pad, H - pad - 40), "isnad.news", font=meta_f, fill="#C9A227", anchor="ra")
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
    story_text = f"سَنَد · {grade}\n{head[:90]}{'…' if len(head) > 90 else ''}\n{url}"
    return {
        "caption_ar": caption_ar,
        "caption_en": caption_en,
        "story_text": story_text,
        "pid": pid,
        "post_url": url,
    }


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

    story = story or select_social_story()
    if not story:
        dest.mkdir(parents=True, exist_ok=True)
        meta = {
            "date": date,
            "status": "skipped",
            "reason": "no authenticated stories",
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

    meta = {
        "date": date,
        "status": "ready",
        "platform": ["instagram_feed", "instagram_story", "whatsapp", "telegram"],
        "head": story.get("head") or "",
        "he": story.get("he") or "",
        "grade": story.get("grade") or "",
        "src": story.get("src") or "",
        "link": story.get("link") or "",
        "score": story.get("score"),
        "post_url": texts["post_url"],
        "pid": texts["pid"],
        "assets": {
            "feed": "feed.png",
            "story": "story.png",
            "caption_ar": "caption_ar.txt",
            "caption_en": "caption_en.txt" if texts["caption_en"] else "",
            "story_text": "story_text.txt",
        },
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    write_index()
    print(f"🖼️ social pack {date}: {story.get('grade')} · {(story.get('head') or '')[:50]}")
    return meta


def _tg_token_chat():
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TG_TOKEN") or ""
    # Prefer channel they already use; editor chat optional override
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
    cap = (dest / "caption_ar.txt").read_text(encoding="utf-8") if (dest / "caption_ar.txt").exists() else ""
    head = meta.get("head") or ""
    grade = meta.get("grade") or ""
    url = meta.get("post_url") or SITE
    intro = (
        f"🖼️ <b>بطاقة سَنَد اليومية</b> — {date}\n"
        f"⚖️ {grade}\n"
        f"{head}\n\n"
        f"<a href=\"{url}\">افتح على سَنَد ↗</a>"
    )
    ok1 = tg_send_photo(str(feed), intro)
    ok2 = tg_send_photo(str(story), "نسخة الستوري · 1080×1920")
    ok3 = tg_send_message(f"<b>كابشن إنستغرام (انسخ):</b>\n\n{cap[:3500]}")
    if ok1 or ok2 or ok3:
        st["social_pack"] = date
        _tg_save(st)
        print(f"📣 social pack sent · photo={ok1}/{ok2} text={ok3}")
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
    print(json.dumps({k: m.get(k) for k in ("date", "status", "grade", "head", "post_url")}, ensure_ascii=False))
