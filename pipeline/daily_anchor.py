#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سَنَد — خط الإنتاج الآلي: RSS → إسناد → نص → صوت فهد → فيديو مذيع مُجزّأ
LongCat 720p أساسي + EchoMimic احتياطي | افتتاحية/خاتمة مكاشة | يشتغل صفر تدخّل"""
import os, re, sys, json, asyncio, shutil, subprocess, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone

HF_TOKEN = os.environ.get("HF_TOKEN",""); GEMINI_KEY = os.environ.get("GEMINI_API_KEY",""); OUT="daily"; os.makedirs(OUT, exist_ok=True)
TIER1=["reuters","رويترز","afp","فرانس برس","ap news","أسوشيتد","kuna","كونا","wam","وام","spa","واس","bna","qna","ona"]
TIER2=["aljazeera","الجزيرة","alarabiya","العربية","skynews","سكاي نيوز","bbc","france24","cnn","alqabas","القبس","aljarida","الجريدة","alrai","الراي","kuwaittimes","arabtimes","gulfnews","thenational","alkhaleej","الخليج","irna","ایرنا","إرنا","tasnim","تسنیم","تسنيم","mehr","مهر","fars","فارس","isna","ایسنا","العالم","press tv","khabaronline","خبرگزاری","همشهری","entekhab","اعتماد"]
FEEDS=[("الخليج","https://news.google.com/rss/search?q=%D8%A7%D9%84%D9%83%D9%88%D9%8A%D8%AA+OR+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D8%A9+OR+%D8%A7%D9%84%D8%A5%D9%85%D8%A7%D8%B1%D8%A7%D8%AA&hl=ar&gl=KW&ceid=KW:ar"),
       ("فلسطين","https://news.google.com/rss/search?q=%D8%BA%D8%B2%D8%A9+OR+%D9%81%D9%84%D8%B3%D8%B7%D9%8A%D9%86&hl=ar&gl=KW&ceid=KW:ar"),
       ("عالم","https://news.google.com/rss/headlines/section/topic/WORLD?hl=ar&gl=KW&ceid=KW:ar"),
       ("تقنية","https://news.google.com/rss/search?q=%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1+%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A&hl=ar&gl=KW&ceid=KW:ar"),
       ("اقتصاد","https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ar&gl=KW&ceid=KW:ar"),
       ("إيران","https://news.google.com/rss?hl=fa&gl=IR&ceid=IR:fa")]
def grade(s):
    s=s.lower()
    return "صحيح" if any(t in s for t in TIER1) else ("حسن" if any(t in s for t in TIER2) else "غير مُسند")
def clean(t): return re.sub(r"\s+"," ",re.sub(r"<[^>]+>","",t or "")).strip()

items=[]; seen=set()
for label,url in FEEDS:
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        root=ET.fromstring(urllib.request.urlopen(req,timeout=30).read())
        n=0
        for it in root.iter("item"):
            title=clean(it.findtext("title","")); src_=title.rsplit(" - ",1)[-1] if " - " in title else ""
            head=title.rsplit(" - ",1)[0] if " - " in title else title
            g=grade(src_ or clean(it.findtext("source","")))
            key=head[:40]
            if g in ("صحيح","حسن") and len(head)>15 and key not in seen:
                seen.add(key)
                items.append({"head":head,"src":src_,"grade":g,"cat":label,
                    "link":clean(it.findtext("link","")),"fa":label=="إيران"}); n+=1
                if n>=6: break
    except Exception as e: print(f"feed {label}: {e}",file=sys.stderr)
print(f"جُمع {len(items)} خبرًا مُسندًا")

def gemini_json(prompt, max_tok=1500):
    body={"contents":[{"parts":[{"text":prompt}]}],
        "generationConfig":{"maxOutputTokens":max_tok,"temperature":0.2,
            "thinkingConfig":{"thinkingBudget":0},"responseMimeType":"application/json"}}
    req=urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_KEY}",
        data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    d=json.load(urllib.request.urlopen(req,timeout=60))
    return json.loads(d["candidates"][0]["content"]["parts"][0]["text"])

fa_items=[i for i in items if i.get("fa")]
if fa_items and GEMINI_KEY:
    try:
        lst="\n".join(f"{n}| {i['head']} :: {i['src']}" for n,i in enumerate(fa_items))
        out=gemini_json("ترجم هذه العناوين الإخبارية من الفارسية إلى العربية الصحفية الرصينة، "
            "وترجم اسم المصدر أيضًا (مثال: خبرگزاری فارس → وكالة فارس). "
            "أخرج JSON فقط بصيغة: [{\"n\":الرقم,\"h\":\"العنوان العربي\",\"s\":\"المصدر بالعربية\"}]\n"+lst)
        for o in out:
            fa_items[o["n"]]["head"]=o["h"]; fa_items[o["n"]]["src"]=o["s"]
        print(f"🇮🇷 تُرجم {len(out)} عنوانًا عن الفارسية")
    except Exception as e:
        print(f"ترجمة إيران فشلت: {str(e)[:80]}")
        items=[i for i in items if not i.get("fa")]

# ═══ خريطة الأخبار الكاملة للمنصة ═══
cats={}
for i in items: cats.setdefault(i["cat"],[]).append({k:i[k] for k in ("head","src","grade","link","fa")})
json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),"cats":cats},
    open(f"{OUT}/news.json","w"),ensure_ascii=False,indent=1)
print(f"🗞️ news.json: {sum(len(v) for v in cats.values())} خبرًا في {len(cats)} أقسام")

# ═══ Grok: حصيلة الأزمة + عاجل من X (محسَّن بالكاش) ═══
GROK_KEY=os.environ.get("GROK_API_KEY","")
INTEL=f"{OUT}/intel.json"

def intel_fresh(hours):
    try:
        p=json.load(open(INTEL))
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(p["updated"])).total_seconds()/3600
        return p, age<hours
    except Exception: return None, False

def grok_intel():
    old, fresh = intel_fresh(6)
    if fresh:
        print(f"♻️ intel.json حديث — تخطي Grok (توفير)"); return old
    if not GROK_KEY:
        print("⚠️ لا مفتاح Grok"); return old
    P=("ابحث عن آخر المعطيات الموثقة عن الأزمة الإيرانية الأمريكية الحالية وأثرها على الخليج.\n"
       "أخرج JSON فقط:\n"
       '{"war":"اسم الأزمة","since":"YYYY-MM-DD","toll":[{"c":"البلد","f":"إيموجي العلم","d":"قتلى","w":"جرحى","dmg":"أبرز الأضرار جملة قصيرة","e":"الخسائر الاقتصادية"}],'
       '"brk":[{"h":"عنوان عاجل","s":"الحساب","u":"رابط"}]}\n'
       "البلدان: إيران، الولايات المتحدة، الكويت، وأي دولة خليجية متضررة. ٤ عناوين عاجلة كحد أقصى "
       "من حسابات موثقة خلال ٦ ساعات. أرقام موثقة فقط وإلا اكتب «غير مؤكد». لا شيء خارج JSON.")
    body={"model":"grok-4.5","input":[{"role":"user","content":P}],
        "tools":[{"type":"web_search"},{"type":"x_search"}],
        "max_output_tokens":2200,"max_tool_calls":8}
    try:
        req=urllib.request.Request("https://api.x.ai/v1/responses",data=json.dumps(body).encode(),
            headers={"Authorization":"Bearer "+GROK_KEY,"Content-Type":"application/json"})
        d=json.load(urllib.request.urlopen(req,timeout=300))
        txt="".join(c.get("text","") for o in d.get("output",[]) if o.get("type")=="message"
                    for c in o.get("content",[]))
        txt=txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        j=json.loads(txt); j["updated"]=datetime.now(timezone.utc).isoformat(timespec="minutes")
        json.dump(j,open(INTEL,"w"),ensure_ascii=False,indent=1)
        print(f"🛰️ Grok: {len(j.get('toll',[]))} دول · {len(j.get('brk',[]))} عاجل · {d['usage']['total_tokens']} توكن")
        return j
    except Exception as e:
        print(f"Grok فشل: {str(e)[:100]}"); return old

INT=grok_intel()
if INT and INT.get("brk"):
    cats["عاجل"]=[{"head":b["h"],"src":b.get("s","X"),"grade":"حسن","link":b.get("u",""),"fa":False,"x":True}
                  for b in INT["brk"]]
    json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),"cats":cats},
        open(f"{OUT}/news.json","w"),ensure_ascii=False,indent=1)
    print(f"⚡ أضيف قسم عاجل: {len(cats['عاجل'])}")

if os.environ.get("NEWS_ONLY"):
    print("⚡ وضع تحديث الأخبار فقط — تم"); sys.exit(0)

today=datetime.now(timezone.utc).strftime("%Y-%m-%d")

OPEN_L="السلامُ عليكم. معكم نشرةُ سَنَد."
CLOSE_L="تحقَّقْ قبلَ أن تنشُر، فالكلمةُ أمانة."
def template_script():
    news=[]
    for it in items[:3]:
        tag="خبرٌ صحيحٌ مؤكَّد" if it["grade"]=="صحيح" else "خبرٌ حسنٌ من مصدرٍ معتبَر"
        news.append(f"{tag}: {it['head']}."+(f" نقلًا عن {it['src']}." if it["src"] else ""))
    return " ".join([OPEN_L]+news+[CLOSE_L])

def gemini_script():
    if not GEMINI_KEY or not items: return None
    heads="\n".join(f"- [{it['grade']}] ({it['cat']}) {it['head']} — المصدر: {it['src'] or 'غير مذكور'}" for it in items[:10])
    prompt=(f"أنت رئيس تحرير نشرة «سَنَد» الإخبارية العربية. من العناوين التالية اختر أهم ثلاثة أخبار متنوعة، "
        f"واكتب نشرة إذاعية قصيرة بالفصحى الرصينة.\n\nالقواعد الصارمة:\n"
        f"1) ابدأ حرفيًا بـ: {OPEN_L}\n2) اختم حرفيًا بـ: {CLOSE_L}\n"
        f"3) صدّر كل خبر بدرجته حرفيًا: «خبرٌ صحيحٌ مؤكَّد:» للصحيح و«خبرٌ حسنٌ من مصدرٍ معتبَر:» للحسن.\n"
        f"4) اذكر المصدر بصيغة «نقلًا عن …».\n5) جمل قصيرة (يُفضَّل ≤ ٦٥ حرفًا للجملة) تناسب القراءة الصوتية.\n"
        f"6) لا تُضِف أي معلومة غير موجودة في العناوين. لا رموز، لا نجوم، لا إنجليزي.\n"
        f"7) النشرة كاملة ٦٠–١٠٠ كلمة.\n\nالعناوين:\n{heads}\n\nأخرج نص النشرة فقط.")
    body={"contents":[{"parts":[{"text":prompt}]}],
          "generationConfig":{"maxOutputTokens":900,"temperature":0.4,"thinkingConfig":{"thinkingBudget":0}}}
    try:
        req=urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_KEY}",
            data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
        d=json.load(urllib.request.urlopen(req,timeout=60))
        txt=d["candidates"][0]["content"]["parts"][0]["text"].strip()
        txt=re.sub(r"[\*#`]","",txt)
        if OPEN_L.split(".")[0] in txt and len(txt)>80:
            print("🧠 النشرة بقلم Gemini"); return txt
    except Exception as e: print(f"Gemini↘ القالب: {str(e)[:100]}")
    return None

full = gemini_script() or template_script()
open(f"{OUT}/script-{today}.txt","w").write(full); print("SCRIPT:",full)
json.dump({"date":today,"script":full,
    "audio":f"bulletin-{today}.mp3","video":"latest.mp4",
    "items":[{"head":i["head"],"src":i["src"],"grade":i["grade"]} for i in items[:3]]},
    open(f"{OUT}/latest.json","w"),ensure_ascii=False,indent=1)

# جُمل ≤٦٥ حرفًا (≈ ≤٤.٧ ثانية = تحت سقف الـ٥ث)
def split65(s):
    out=[]
    while len(s)>65:
        cut=max(s.rfind("،",0,65), s.rfind(" ",0,65)); cut=cut if cut>20 else 65
        out.append(s[:cut].strip()); s=s[cut:].strip()
    if s: out.append(s)
    return out
body = full.replace(OPEN_L,"").replace(CLOSE_L,"").strip()
chunks=[c for c in split65(body)][:3]  # سقف ٣ مقاطع/يوم = ضمن حصة PRO
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
meta=json.load(open(f"{OUT}/latest.json")); meta["video_date"]=today
json.dump(meta,open(f"{OUT}/latest.json","w"),ensure_ascii=False,indent=1)
print(f"🎬 VIDEO OK: {OUT}/bulletin-{today}.mp4")
