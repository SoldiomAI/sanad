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
  python3 - <<'PY' || { rm -f latest.mp4; echo "🧹 حُذف latest.mp4 البائت (ليس فيديو نشرةِ اليوم)"; }
import json,sys
m=json.load(open("latest.json",encoding="utf-8"))
sys.exit(0 if (m.get("video") and m.get("video_date")==m.get("date")) else 1)
PY
fi

# الملفّاتُ المحذوفةُ محلّيًّا تُحذَفُ من المستودعِ عبر git add -A في خطوةِ النشر
exit 0
