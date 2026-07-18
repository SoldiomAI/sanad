#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سَنَد — خط الإنتاج الآلي: RSS → إسناد → نص → صوت فهد → فيديو مذيع مُجزّأ
LongCat 720p أساسي + EchoMimic احتياطي | افتتاحية/خاتمة مكاشة | يشتغل صفر تدخّل"""
import os, re, sys, json, asyncio, shutil, subprocess, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone

HF_TOKEN = os.environ.get("HF_TOKEN",""); OUT="daily"; os.makedirs(OUT, exist_ok=True)
TIER1=["reuters","رويترز","afp","فرانس برس","ap news","أسوشيتد","kuna","كونا","wam","وام","spa","واس","bna","qna","ona"]
TIER2=["aljazeera","الجزيرة","alarabiya","العربية","skynews","سكاي نيوز","bbc","france24","cnn","alqabas","القبس","aljarida","الجريدة","alrai","الراي","kuwaittimes","arabtimes","gulfnews","thenational","alkhaleej","الخليج"]
FEEDS=[("الخليج","https://news.google.com/rss/search?q=%D8%A7%D9%84%D9%83%D9%88%D9%8A%D8%AA+OR+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D8%A9+OR+%D8%A7%D9%84%D8%A5%D9%85%D8%A7%D8%B1%D8%A7%D8%AA&hl=ar&gl=KW&ceid=KW:ar"),
       ("فلسطين","https://news.google.com/rss/search?q=%D8%BA%D8%B2%D8%A9+OR+%D9%81%D9%84%D8%B3%D8%B7%D9%8A%D9%86&hl=ar&gl=KW&ceid=KW:ar")]
def grade(s):
    s=s.lower()
    return "صحيح" if any(t in s for t in TIER1) else ("حسن" if any(t in s for t in TIER2) else "غير مُسند")
def clean(t): return re.sub(r"\s+"," ",re.sub(r"<[^>]+>","",t or "")).strip()

items=[]
for label,url in FEEDS:
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        root=ET.fromstring(urllib.request.urlopen(req,timeout=30).read())
        for it in root.iter("item"):
            title=clean(it.findtext("title","")); src=title.rsplit(" - ",1)[-1] if " - " in title else ""
            head=title.rsplit(" - ",1)[0] if " - " in title else title
            g=grade(src or clean(it.findtext("source","")))
            if g in ("صحيح","حسن") and len(head)>20:
                items.append({"head":head,"src":src,"grade":g}); break
    except Exception as e: print(f"feed {label}: {e}",file=sys.stderr)

today=datetime.now(timezone.utc).strftime("%Y-%m-%d")
news=[]
for it in items[:2]:
    tag="خبرٌ صحيحٌ مؤكَّد" if it["grade"]=="صحيح" else "خبرٌ حسنٌ من مصدرٍ معتبَر"
    news.append(f"{tag}: {it['head']}."+(f" نقلًا عن {it['src']}." if it["src"] else ""))
full=" ".join(["السلامُ عليكم. معكم نشرةُ سَنَد."]+news+["تحقَّقْ قبلَ أن تنشُر، فالكلمةُ أمانة."])
open(f"{OUT}/script-{today}.txt","w").write(full); print("SCRIPT:",full)

# جُمل ≤٦٥ حرفًا (≈ ≤٤.٧ ثانية = تحت سقف الـ٥ث)
def split65(s):
    out=[]
    while len(s)>65:
        cut=max(s.rfind("،",0,65), s.rfind(" ",0,65)); cut=cut if cut>20 else 65
        out.append(s[:cut].strip()); s=s[cut:].strip()
    if s: out.append(s)
    return out
chunks=[c for n in news for c in split65(n)][:3]  # سقف ٣ مقاطع/يوم = ضمن حصة PRO
print(f"chunks: {len(chunks)}")

import edge_tts
async def tts(t,p): await edge_tts.Communicate(t,"ar-KW-FahedNeural",rate="-2%").save(p)

def dur(p): return float(subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration","-of","csv=p=0",p],capture_output=True,text=True).stdout.strip() or 0)

asyncio.run(tts(full,f"{OUT}/bulletin-{today}.mp3"))  # النشرة الصوتية الكاملة — تُحفظ دائمًا
if not HF_TOKEN: print("⚠️ HF_TOKEN مفقود — نص+صوت فقط"); sys.exit(0)

from gradio_client import Client, handle_file
class QuotaOut(Exception): pass
def _mk(space):
    try: return Client(space, token=HF_TOKEN)
    except TypeError: return Client(space, hf_token=HF_TOKEN)
PROMPT="A professional Gulf Arab news anchor in white ghutra and black agal speaking to camera, news studio"
_lc=_ec=None
def gen(ap,vp):
    global _lc,_ec
    try:
        _lc=_lc or _mk("victor/LongCat-Video-Avatar-1.5")
        r=_lc.predict(image_path=handle_file("pipeline/anchor_face.jpg"),audio_path=handle_file(ap),
            prompt=PROMPT,resolution="720p",seed=77,vocal_mode="Clean speech (fast)",
            acceleration="DBCache faster",api_name="/generate")
    except Exception as e:
        print(f"LongCat↘ EchoMimic: {str(e)[:120]}")
        try:
            _ec=_ec or _mk("fffiloni/EchoMimic")
            r=_ec.predict(uploaded_img=handle_file("pipeline/anchor_face.jpg"),uploaded_audio=handle_file(ap),
                width=512,height=512,length=120,seed=77,facemask_dilation_ratio=0.1,facecrop_dilation_ratio=0.5,
                context_frames=12,context_overlap=3,cfg=2.5,steps=30,sample_rate=16000,fps=24,device="cuda",
                api_name="/generate_video")
        except Exception as e2:
            if "quota" in (str(e)+str(e2)).lower(): raise QuotaOut(str(e2)[:150])
            raise
    v=r[0] if isinstance(r,(list,tuple)) else r
    if isinstance(v,dict): v=v.get("video") or v.get("path")
    shutil.copy(v,vp)

parts=["daily/opening.mp4"] if os.path.exists("daily/opening.mp4") else []
try:
    for i,s in enumerate(chunks,1):
        ap=f"{OUT}/n{i}.mp3"; asyncio.run(tts(s,ap))
        subprocess.run(["ffmpeg","-v","quiet","-y","-i",ap,"-af","apad=pad_dur=0.3",ap+".p.mp3"])
        vp=f"{OUT}/n{i}.mp4"; gen(ap+".p.mp3",vp); parts.append(vp); print(f"✅ chunk {i}")
except QuotaOut as q:
    print(f"⏳ حصة GPU مستهلكة ({q}) — النص والصوت الكامل محفوظان، الفيديو بالتشغيلة الجاية")
    for f in os.listdir(OUT):
        if f.startswith("n") and (f.endswith(".mp3") or f.endswith(".mp4") or f.endswith(".p.mp3")):
            os.remove(f"{OUT}/{f}")
    sys.exit(0)
if os.path.exists("daily/outro.mp4"): parts.append("daily/outro.mp4")

lst=f"{OUT}/list.txt"
with open(lst,"w") as f:
    for p in parts: f.write(f"file '{os.path.abspath(p)}'\n")
subprocess.run(["ffmpeg","-v","quiet","-y","-f","concat","-safe","0","-i",lst,"-c:v","libx264","-crf","18",
    "-pix_fmt","yuv420p","-c:a","aac","-movflags","+faststart",f"{OUT}/bulletin-{today}.mp4"])
shutil.copy(f"{OUT}/bulletin-{today}.mp4",f"{OUT}/latest.mp4")
print(f"🎬 VIDEO OK: {OUT}/bulletin-{today}.mp4")
