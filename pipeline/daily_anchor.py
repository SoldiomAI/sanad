#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سَنَد — خط الإنتاج الآلي اليومي
RSS → تصنيف إسنادي → نص عربي → صوت فهد الكويتي → فيديو مذيع (EchoMimic)
يشتغل تلقائيًا عبر GitHub Actions. صفر تدخّل بشري.
"""
import os, re, sys, json, asyncio, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone

HF_TOKEN = os.environ.get("HF_TOKEN", "")
OUT = "daily"
os.makedirs(OUT, exist_ok=True)

# ── ١) المصادر (نفس منطق التطبيق) ─────────────────────────
TIER1 = ["reuters","رويترز","afp","فرانس برس","ap news","أسوشيتد","kuna","كونا","wam","وام","spa","واس","bna","qna","ona"]
TIER2 = ["aljazeera","الجزيرة","alarabiya","العربية","skynews","سكاي نيوز","bbc","france24","cnn","alqabas","القبس","aljarida","الجريدة","alrai","الراي","kuwaittimes","arabtimes","gulfnews","thenational","alkhaleej","الخليج"]

FEEDS = [
    ("الخليج",  "https://news.google.com/rss/search?q=%D8%A7%D9%84%D9%83%D9%88%D9%8A%D8%AA+OR+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D8%A9+OR+%D8%A7%D9%84%D8%A5%D9%85%D8%A7%D8%B1%D8%A7%D8%AA+OR+%D9%82%D8%B7%D8%B1&hl=ar&gl=KW&ceid=KW:ar"),
    ("فلسطين",  "https://news.google.com/rss/search?q=%D8%BA%D8%B2%D8%A9+OR+%D9%81%D9%84%D8%B3%D8%B7%D9%8A%D9%86&hl=ar&gl=KW&ceid=KW:ar"),
    ("إيران",   "https://news.google.com/rss/search?q=Iran+Gulf+strikes&hl=en-US&gl=US&ceid=US:en"),
]

def grade(src):
    s = src.lower()
    if any(t in s for t in TIER1): return "صحيح"
    if any(t in s for t in TIER2): return "حسن"
    return "غير مُسند"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return ET.fromstring(r.read())

def clean(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    return re.sub(r"\s+", " ", t).strip()

items = []
for label, url in FEEDS:
    try:
        root = fetch(url)
        for it in root.iter("item"):
            title = clean(it.findtext("title",""))
            src = title.rsplit(" - ",1)[-1] if " - " in title else ""
            head = title.rsplit(" - ",1)[0] if " - " in title else title
            g = grade(src or clean(it.findtext("source","")))
            if g in ("صحيح","حسن") and len(head) > 20:
                items.append({"cat":label,"head":head,"src":src,"grade":g})
                break  # أهم خبر لكل قسم
    except Exception as e:
        print(f"feed {label}: {e}", file=sys.stderr)

# ── ٢) بناء النص ──────────────────────────────────────────
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
lines = ["السلامُ عليكم ورحمةُ الله. معكم نشرةُ سَنَد، حيثُ يُروى الخبرُ بإسنادِه."]
for it in items[:2]:  # خبران = صوت ~٢٠ ثانية (حدود GPU المجاني)
    tag = "خبرٌ صحيحٌ مؤكَّد" if it["grade"]=="صحيح" else "خبرٌ حسنٌ من مصدرٍ معتبَر"
    lines.append(f"{tag}: {it['head']}. نقلًا عن {it['src']}." if it["src"] else f"{tag}: {it['head']}.")
lines.append("تحقَّقْ قبلَ أن تنشُر، فالكلمةُ أمانة.")
script = " ".join(lines)
open(f"{OUT}/script-{today}.txt","w").write(script)
print("SCRIPT:", script)

# ── ٣) الصوت — فهد الكويتي ────────────────────────────────
import edge_tts
async def tts():
    await edge_tts.Communicate(script, "ar-KW-FahedNeural", rate="-4%").save(f"{OUT}/bulletin-{today}.mp3")
asyncio.run(tts())
import subprocess
dur = float(subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration","-of","csv=p=0",f"{OUT}/bulletin-{today}.mp3"],capture_output=True,text=True).stdout.strip() or 15)
print(f"AUDIO: {dur:.1f}s")

# ── ٤) الفيديو — EchoMimic عبر حساب HF ────────────────────
if not HF_TOKEN:
    print("⚠️ HF_TOKEN غير موجود — تخطّي الفيديو (الصوت والنص جاهزان)"); sys.exit(0)

from gradio_client import Client, handle_file
frames = min(int(dur*24)+12, 600)
c = Client("fffiloni/EchoMimic", hf_token=HF_TOKEN)
r = c.predict(
    uploaded_img=handle_file("pipeline/anchor_face.jpg"),
    uploaded_audio=handle_file(f"{OUT}/bulletin-{today}.mp3"),
    width=512, height=512, length=frames, seed=77,
    facemask_dilation_ratio=0.1, facecrop_dilation_ratio=0.5,
    context_frames=12, context_overlap=3,
    cfg=1.0, steps=6, sample_rate=16000, fps=24, device="cuda",
    api_name="/generate_video")
vid = r if isinstance(r,str) else (r.get("video") if isinstance(r,dict) else r[0])
if isinstance(vid,dict): vid = vid.get("video") or vid.get("path")
import shutil
shutil.copy(vid, f"{OUT}/bulletin-{today}.mp4")
shutil.copy(vid, f"{OUT}/latest.mp4")
print(f"✅ VIDEO: {OUT}/bulletin-{today}.mp4")
