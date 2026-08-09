# -*- coding: utf-8 -*-
"""«المُنادي» 📣 — إشعارُ التحذيراتِ الرسميّةِ إلى تطبيقِ سَنَد.

القاعدةُ الحاكمة: **الإشعارُ مقاطعةٌ للقارئ**، فلا يُنفَقُ إلّا على ما يستحقُّ
المقاطعة. لا أخبارَ عامّة، ولا «عُدْ إلينا»، ولا ترويج — التحذيرُ الرسميُّ
المُسنَدُ وحدَه. هذا ليس تحفّظًا زائدًا: الإذنُ المسحوبُ لا يُستعاد، وقناةٌ
تُساءُ فتُكتَمُ تُفقِدُ المنصّةَ أثمنَ ما تملكُه — أن يُصدَّقَ نداؤها وقتَ الجدّ.

الاشتراكُ بـ«موضوعٍ» (topic) لا بجهاز: لا يُخزَّنُ رمزُ جهازٍ في أيِّ مكان،
ولا يملكُ الأنبوبُ قائمةَ أجهزةٍ أصلًا — وهو أنبوبٌ ساكنٌ يكتبُ في مستودع،
فلا ينبغي أن يملكَها.

بلا سرِّ Firebase: تخطٍّ صامتٌ تامّ — نفسُ نمطِ بقيّةِ المصادرِ المِفتاحيّة.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = os.environ.get("SANAD_DAILY", "daily")
ALERTS_F = Path(OUT, "alerts.json")
SENT_F = Path(OUT, "push_sent.json")          # سِجلُّ ما أُرسِلَ — يمنعُ التكرار

TOPIC = os.environ.get("FCM_TOPIC", "alerts")
# الأنبوبُ يدورُ كلَّ ٣٠ دقيقة؛ بلا هذا السقفِ يكفي خللٌ واحدٌ ليقصفَ القرّاء
DAILY_CAP = int(os.environ.get("PUSH_DAILY_CAP", "6"))
# التحذيرُ الملتقَطُ قبلَ أكثرَ من هذا لا يُوقَظُ له أحد — فاتَ أوانُ المقاطعة
MAX_AGE_H = float(os.environ.get("PUSH_MAX_AGE_H", "6"))
SENT_KEEP = 400

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


def _now():
    return datetime.now(timezone.utc)


def _load(p, default):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _age_h(iso):
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (_now() - t).total_seconds() / 3600.0
    except Exception:
        return None


def alert_id(item) -> str:
    """بصمةٌ ثابتةٌ للتحذير — من نصِّه وحدَه.

    النصُّ لا الرابط: الرابطُ نفسُه قد يُفَكُّ لاحقًا إلى رابطِ الناشرِ المباشر،
    فلو كانت البصمةُ منه لعُدَّ التحذيرُ جديدًا وأُرسِلَ مرّتين.
    """
    txt = re.sub(r"\s+", "", str((item or {}).get("txt") or ""))
    return hashlib.md5(txt.encode("utf-8")).hexdigest()[:12]


def _sa():
    """يقرأُ حسابَ الخدمةِ من البيئة. غيابُه ⇒ لا إشعارات، بلا ضجيج."""
    raw = os.environ.get("FCM_SA_JSON", "").strip()
    if not raw:
        return None
    try:
        sa = json.loads(raw)
    except Exception:
        return None
    if not (sa.get("client_email") and sa.get("private_key") and sa.get("project_id")):
        return None
    return sa


def _access_token(sa) -> str | None:
    """JWT موقَّعٌ بـRS256 ثمّ يُبادَلُ برمزِ وصول (FCM HTTP v1).

    المفتاحُ الخادميُّ القديمُ (legacy server key) أُوقِفَ، فلا بديلَ عن التوقيع.
    """
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except Exception:
        return None
    now = int(time.time())
    hdr = {"alg": "RS256", "typ": "JWT"}
    claim = {
        "iss": sa["client_email"],
        "scope": _SCOPE,
        "aud": _TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = (
        _b64(json.dumps(hdr, separators=(",", ":")).encode())
        + "."
        + _b64(json.dumps(claim, separators=(",", ":")).encode())
    ).encode()
    try:
        key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
        sig = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        assertion = signing_input.decode() + "." + _b64(sig)
        body = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }).encode()
        req = urllib.request.Request(
            _TOKEN_URL, data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return (json.load(r) or {}).get("access_token")
    except Exception:
        return None


def _send(project_id, token, title, body, data) -> bool:
    msg = {
        "message": {
            "topic": TOPIC,
            "notification": {"title": title[:120], "body": body[:300]},
            "data": {k: str(v) for k, v in (data or {}).items()},
            "android": {
                "priority": "high",
                "notification": {"channel_id": "sanad_alerts"},
            },
            "apns": {"payload": {"aps": {"sound": "default"}}},
        }
    }
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    req = urllib.request.Request(
        url, data=json.dumps(msg, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json; charset=UTF-8"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return 200 <= r.status < 300
    except Exception as e:
        print(f"📣 المُنادي: تعذّرَ الإرسال — {str(e)[:70]}")
        return False


def _eligible(item, sent_ids):
    """بوّاباتُ الإرسال — كلُّها يجبُ أن تُفتَح.

    يُلاحَظُ أنّ حرّاسَ الطزاجةِ والدرجةِ طُبِّقتْ سلفًا في `alerts_wire`، فما
    يصلُ هنا مُسنَدٌ حديثٌ أصلًا. هذه الطبقةُ تحرسُ ما يخصُّ **الإشعارَ** وحدَه:
    ألّا يتكرّر، وألّا يوقظَ أحدًا لخبرٍ فاتَ أوانُه.
    """
    if not isinstance(item, dict):
        return False, "ليس عنصرًا"
    # ‼️ `alerts.json` يحملُ صنفَين: «تحذير» رسميّ و«تنبيه من شائعة». الإشعارُ
    # يخرجُ بعنوانِ «تحذيرٌ رسميّ»، فبثُّ تنبيهِ شائعةٍ تحتَه يجعلُ سَنَد نفسَها
    # تخلطُ ما قامت لتفريقِه. الشائعةُ تُقرَأُ في «تحت المِجهر» ولا يُوقَظُ لها أحد.
    kind = str(item.get("kind") or "").strip()
    if "شائعة" in kind or "تحذير" not in kind:
        return False, f"ليس تحذيرًا رسميًّا ({kind[:24]})"
    if alert_id(item) in sent_ids:
        return False, "أُرسِلَ سابقًا"
    if not str(item.get("txt") or "").strip():
        return False, "بلا نصّ"
    if not str(item.get("u") or "").startswith("https://"):
        return False, "بلا رابطٍ آمن"      # لا نُنبّهُ إلى ما لا يمكنُ فتحُه ومراجعتُه
    age = _age_h(item.get("cap"))
    if age is None:
        return False, "بلا ختمِ التقاط"
    if age > MAX_AGE_H:
        return False, f"فاتَ أوانُه ({age:.0f}س)"
    return True, ""


def push_alerts() -> dict:
    """يُرسِلُ التحذيراتِ الرسميّةَ الجديدةَ وحدَها إلى موضوعِ التطبيق."""
    sa = _sa()
    if not sa:
        return {"skipped": 1, "why": "لا سرَّ Firebase — الإشعاراتُ معطّلة"}

    doc = _load(ALERTS_F, {})
    items = (doc or {}).get("list") or []
    if not items:
        return {"skipped": 1, "why": "لا تحذيراتٍ لإرسالها"}

    led = _load(SENT_F, {})
    if not isinstance(led, dict):
        led = {}
    sent = list(led.get("sent") or [])
    sent_ids = {s.get("id") for s in sent if isinstance(s, dict)}

    today = _now().strftime("%Y-%m-%d")
    today_n = sum(1 for s in sent if isinstance(s, dict) and str(s.get("at", ""))[:10] == today)

    fresh = []
    for it in items:
        ok, _why = _eligible(it, sent_ids)
        if ok:
            fresh.append(it)
    if not fresh:
        return {"skipped": 1, "why": "لا جديدَ يستحقُّ المقاطعة"}

    room = max(0, DAILY_CAP - today_n)
    if room <= 0:
        print(f"📣 المُنادي: بلغَ سقفَ اليوم ({DAILY_CAP}) — {len(fresh)} مؤجَّلًا")
        return {"skipped": 1, "why": f"سقفُ اليوم {DAILY_CAP}"}

    token = _access_token(sa)
    if not token:
        return {"failed": 1, "why": "تعذّرَ الحصولُ على رمزِ الوصول"}

    ok_n = 0
    for it in fresh[:room]:
        title = "⚠️ تحذيرٌ رسميّ"
        # المتنُ يحملُ المصدرَ صراحةً: الإشعارُ نفسُه مُسنَد، لا صوتٌ مجهول
        body = str(it.get("txt") or "")
        src = str(it.get("body") or "").strip()
        if src:
            body = f"{body} — {src}"
        if _send(sa["project_id"], token, title, body,
                 {"u": it.get("u") or "", "when": it.get("when") or "", "kind": "alert"}):
            ok_n += 1
            sent.append({"id": alert_id(it), "at": _now().isoformat(timespec="minutes"),
                         "txt": str(it.get("txt") or "")[:90]})

    if ok_n:
        led = {"updated": _now().isoformat(timespec="minutes"), "sent": sent[-SENT_KEEP:]}
        SENT_F.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")

    held = max(0, len(fresh) - room)
    print(f"📣 المُنادي: أُرسِلَ {ok_n} تحذيرًا"
          + (f" · {held} مؤجَّلًا للسقف" if held else "")
          + f" (اليومَ {today_n + ok_n}/{DAILY_CAP})")
    return {"why": f"{ok_n} تحذيرًا"} if ok_n else {"failed": 1, "why": "فشلَ الإرسال"}


if __name__ == "__main__":
    print(json.dumps(push_alerts(), ensure_ascii=False))
