#!/usr/bin/env bash
# نظافةُ النشرِ للمستودعِ العامّ (sanad-data) — يُشغَّلُ على نسخةِ /tmp/pub/daily
# قبلَ الالتزام. المبدأ: يُنشَرُ ما تقرؤُه الواجهةُ والمستهلِكون، لا مخلّفاتُ التشغيل.
#
#  ١) ملفّاتُ التشغيلِ الداخليّة لا تُنشَر: مقاطعُ الاستئناف seg/ وقوائمُ ffmpeg
#     وملفّاتُ TTS المؤقّتة وعلاماتُ الأنبوب — لا تقرؤها الواجهةُ إطلاقًا.
#  ٢) احتفاظٌ محدود بالوسائط: نشراتُ mp3/mp4 الأقدمُ من RETAIN_DAYS تُحذَفُ من
#     المستودعِ العامّ (تبقى في مستودعِ التشغيل) — كان النموُّ بلا سقفٍ إطلاقًا.
#  ٣) لا فيديو بائتًا باسمِ «الأحدث»: إن لم يكن latest.mp4 فيديو نشرةِ اليومِ
#     المذكورةِ في latest.json حُذفَ من النشرِ — كان فيديو ١٩ يوليو يُنشَرُ شهرًا.
set -u
PUB="${1:-/tmp/pub/daily}"
RETAIN_DAYS="${RETAIN_DAYS:-30}"
[ -d "$PUB" ] || exit 0
cd "$PUB"

pick_python() {
  for py in python3 python; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import json, os, sys' >/dev/null 2>&1; then
      printf '%s\n' "$py"
      return 0
    fi
  done
  return 1
}
PYTHON_BIN="${PYTHON_BIN:-$(pick_python)}"
[ -n "$PYTHON_BIN" ] || { echo "❌ Python is required for publish hygiene"; exit 1; }

# ١ — مخلّفاتُ التشغيل
rm -rf seg
rm -f list.txt rp_budget.json rumors_backfill.done
rm -f n[0-9]*.mp3 n[0-9]*.mp3.p.mp3 2>/dev/null || true

# ٢ — احتفاظُ الوسائطِ المؤرّخة (bulletin-YYYY-MM-DD.*)
CUTOFF="$(date -u -d "-${RETAIN_DAYS} days" +%F 2>/dev/null || date -u +%F)"
removed=0
for f in bulletin-????-??-??.mp3 bulletin-????-??-??.mp4; do
  [ -e "$f" ] || continue
  d="${f#bulletin-}"; d="${d%.*}"
  if [[ "$d" < "$CUTOFF" ]]; then rm -f "$f"; removed=$((removed+1)); fi
done
[ "$removed" -gt 0 ] && echo "🧹 حُذفت $removed نشرةً أقدمَ من ${RETAIN_DAYS} يومًا من النشرِ العامّ"

# ٣ — لا فيديو بائتًا
if [ -f latest.mp4 ] && [ -f latest.json ]; then
  "$PYTHON_BIN" - <<'PY' || { rm -f latest.mp4; echo "🧹 حُذف latest.mp4 البائت (ليس فيديو نشرةِ اليوم)"; }
import json,sys
m=json.load(open("latest.json",encoding="utf-8"))
sys.exit(0 if (m.get("video") and m.get("video_date")==m.get("date")) else 1)
PY
fi

"$PYTHON_BIN" - <<'PY'
import json, os

def clean(meta):
    if not isinstance(meta, dict):
        return meta, False
    video = meta.get("video")
    ok = bool(video and meta.get("video_date") == meta.get("date") and os.path.exists(str(video)))
    if ok:
        return meta, False
    out = dict(meta)
    changed = ("video" in out) or ("video_date" in out)
    out.pop("video", None)
    out.pop("video_date", None)
    return out, changed

changed = False
if os.path.exists("latest.json"):
    doc = json.load(open("latest.json", encoding="utf-8"))
    doc, did = clean(doc)
    if did:
        json.dump(doc, open("latest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        changed = True

if os.path.exists("bundle.json"):
    doc = json.load(open("bundle.json", encoding="utf-8"))
    latest = doc.get("latest")
    latest, did = clean(latest)
    if did:
        doc["latest"] = latest
        json.dump(doc, open("bundle.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        changed = True

if changed:
    print("cleaned invalid latest video metadata")
PY

# الملفّاتُ المحذوفةُ محلّيًّا تُحذَفُ من المستودعِ عبر git add -A في خطوةِ النشر
exit 0
