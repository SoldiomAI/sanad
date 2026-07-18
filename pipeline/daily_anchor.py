#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سَنَد — خط الإنتاج الآلي: RSS → إسناد → نص → صوت فهد → فيديو مذيع مُجزّأ
LongCat 720p أساسي + EchoMimic احتياطي | افتتاحية/خاتمة مكاشة | يشتغل صفر تدخّل"""
import os, re, sys, json, time, asyncio, shutil, subprocess, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone

GROK_KEY = os.environ.get("GROK_API_KEY",""); HF_TOKEN = os.environ.get("HF_TOKEN",""); GEMINI_KEY = os.environ.get("GEMINI_API_KEY",""); OUT="daily"; os.makedirs(OUT, exist_ok=True)
TIER1=["centcom","kuna","كونا","mew_kwt","kff_kw","moi_bahrain","mofauae","mofaqatar","وكالة الأنباء الكويتية","reuters","رويترز","afp","فرانس برس","ap news","أسوشيتد","kuna","كونا","wam","وام","spa","واس","bna","qna","ona"]
TIER2=["aljazeera","الجزيرة","alarabiya","العربية","skynews","سكاي نيوز","bbc","france24","cnn","alqabas","القبس","aljarida","الجريدة","alrai","الراي","kuwaittimes","arabtimes","gulfnews","thenational","alkhaleej","الخليج","irna","ایرنا","إرنا","tasnim","تسنیم","تسنيم","mehr","مهر","fars","فارس","isna","ایسنا","العالم","press tv","khabaronline","خبرگزاری","iran international","ایران اینترنشنال","bbc persian","بی‌بی‌سی","همشهری","entekhab","اعتماد"]
FEEDS=[("الخليج","https://news.google.com/rss/search?q=%D8%A7%D9%84%D9%83%D9%88%D9%8A%D8%AA+OR+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D8%A9+OR+%D8%A7%D9%84%D8%A5%D9%85%D8%A7%D8%B1%D8%A7%D8%AA&hl=ar&gl=KW&ceid=KW:ar"),
       ("فلسطين","https://news.google.com/rss/search?q=%D8%BA%D8%B2%D8%A9+OR+%D9%81%D9%84%D8%B3%D8%B7%D9%8A%D9%86&hl=ar&gl=KW&ceid=KW:ar"),
       ("عالم","https://news.google.com/rss/headlines/section/topic/WORLD?hl=ar&gl=KW&ceid=KW:ar"),
       ("تقنية","https://news.google.com/rss/search?q=%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1+%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A&hl=ar&gl=KW&ceid=KW:ar"),
       ("اقتصاد","https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ar&gl=KW&ceid=KW:ar"),
       ("إيران","https://feeds.bbci.co.uk/persian/rss.xml"),
       ("إيران","https://www.iranintl.com/feed")]

# مصادر إيران: الاسم المعتمد وهوية الجهة — تُعرض للقارئ صراحةً
FA_SRC={
 "feeds.bbci.co.uk":("بي بي سي فارسي","هيئة بث بريطانية عامة"),
 "iranintl.com":("إيران إنترناشونال","قناة فارسية مقرّها لندن"),
}
def fa_meta(url):
    for k,v in FA_SRC.items():
        if k in url: return v
    return ("مصدر فارسي","غير محدد")

# ═══════════ طبقة الوكلاء — سجلٌّ ومراقبةٌ حيّة ═══════════
AGENTS_F=f"{OUT}/agents.json"
AGENTS=[
 ("rasid","الرَّاصِد","🛰️","يرصد المصادر الحيّة ويجمع الحصيلة والعاجل"),
 ("mutabiq","المُطابِق","🔍","يقابل أرقام الحصيلة بمصادر مستقلة"),
 ("manba","المَنبع","📡","ينقل البيانات الرسمية عن الجهات مباشرة"),
 ("turjuman","التَّرْجُمَان","🗣️","ينقل الخبر الفارسي إلى العربية ترجمةً أمينة"),
 ("mudaqqiq","المُدقِّق","⚖️","يراجع المواد ويستبعد ما لا يصلح للنشر"),
 ("musannif","المُصنِّف","🧬","يطوّر قواعد الفرز بعد كل جولة"),
 ("mustaqri","المُستقرِئ","🔮","يستقرئ ما قد يقع من السوابق والتصريحات"),
 ("murtajil","المُحلِّل","🎤","يصوغ قراءة الساعة ويؤدّيها صوتًا"),
 ("rawi","الرَّاوِي","🎙️","يؤدّي النشرة اليومية بصوت المذيع"),
]
_LOG={}
def _load_log():
    try: return {a["id"]:a for a in json.load(open(AGENTS_F)).get("agents",[])}
    except Exception: return {}
_PREV=_load_log()

def agent(aid):
    """يغلّف الوكيل: يقيس الزمن، يلتقط الأعطال، ويسجّل الحالة."""
    def deco(fn):
        def wrap(*a,**k):
            t0=time.time(); st="ok"; note=""
            try:
                r=fn(*a,**k)
                if isinstance(r,dict) and r.get("skipped"): st="skip"; note=r.get("why","")
                return r
            except Exception as e:
                st="fail"; note=str(e)[:110]; print(f"⚠️ {aid}: {note}"); return None
            finally:
                _LOG[aid]={"ms":int((time.time()-t0)*1000),"status":st,"note":note,
                    "at":datetime.now(timezone.utc).isoformat(timespec="minutes")}
        return wrap
    return deco

def mark(aid,status="ok",note=""):
    _LOG[aid]={"ms":_LOG.get(aid,{}).get("ms",0),"status":status,"note":note,
        "at":datetime.now(timezone.utc).isoformat(timespec="minutes")}


# ═══ الأرشيف: لقطة لكل جولة + فهرس ═══
def archive():
    try:
        os.makedirs(f"{OUT}/archive",exist_ok=True)
        stamp=datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
        snap={"at":datetime.now(timezone.utc).isoformat(timespec="minutes"),"cats":cats}
        for f in ("intel","forecast","council"):
            try: snap[f]=json.load(open(f"{OUT}/{f}.json"))
            except Exception: pass
        json.dump(snap,open(f"{OUT}/archive/{stamp}.json","w"),ensure_ascii=False,indent=1)
        try: idx=json.load(open(f"{OUT}/archive/index.json"))
        except Exception: idx={"snaps":[]}
        idx["snaps"]=(idx.get("snaps",[])+[{"id":stamp,
            "n":sum(len(v) for v in cats.values()),"cats":len(cats)}])[-120:]
        idx["updated"]=snap["at"]
        json.dump(idx,open(f"{OUT}/archive/index.json","w"),ensure_ascii=False,indent=1)
        print(f"🗄️ الأرشيف: {stamp} ({idx['snaps'][-1]['n']} خبرًا) · {len(idx['snaps'])} لقطة")
    except Exception as e: print("الأرشفة تعذّرت: "+str(e)[:70])

def save_agents():
    out=[]
    for aid,nm,ic,role in AGENTS:
        cur=_LOG.get(aid) or {}
        prev=_PREV.get(aid,{})
        out.append({"id":aid,"name":nm,"icon":ic,"role":role,
            "status":cur.get("status", prev.get("status","idle")),
            "ms":cur.get("ms", prev.get("ms",0)),
            "note":cur.get("note", prev.get("note","")),
            "at":cur.get("at", prev.get("at","")),
            "ran":aid in _LOG})
    ok=sum(1 for a in out if a["status"] in ("ok","skip"))
    json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "healthy":ok,"total":len(out),"agents":out},
        open(AGENTS_F,"w"),ensure_ascii=False,indent=1)
    print(f"🤖 طبقة الوكلاء: {ok}/{len(out)} بحالة سليمة")

OFFICIAL_HANDLES=set()
try:
    OFFICIAL_HANDLES={x.get("h","").lower().lstrip("@") for x in json.load(open(f"{OUT}/official.json")).get("src",[])}
except Exception: pass

RULES=f"{OUT}/rules.json"
PROTECT=["إيران","الكويت","السعودي","الإمارات","قطر","البحرين","عُمان","عمان","العراق","الخليج",
 "ترامب","أمريك","واشنطن","هرمز","نفط","غاز","صاروخ","مسيّر","مسير","ضرب","هجوم","قصف","هدنة","تهدئة",
 "غزة","فلسطين","إسرائيل","نووي","كهرباء","مياه","تحلية","العديد","قاعدة","إنذار","طهران","الحرس الثوري",
 "الذكاء الاصطناعي","الأمم المتحدة","مفاوضات","عقوبات","لاجئ","قتلى","جرحى","إخلاء","مجال جوي"]

def safe_pattern(b):
    """يرفض أي نمط قد يحجب أخبارًا جوهرية أو كان فضفاضًا."""
    if not b or len(b)<5 or len(b)>34: return False
    return not any(p in b for p in PROTECT)

def load_rules():
    try:
        r=json.load(open(RULES))
        raw=r.get("block",[]); blk=[b for b in raw if safe_pattern(b)]
        if len(blk)<len(raw): print(f"🛡️ رُفض {len(raw)-len(blk)} نمطًا لمساسه بموضوعات جوهرية")
        return {"v":r.get("v",0),"block":blk[:26],"route":r.get("route",{}),"notes":r.get("notes",[])}
    except Exception: return {"v":0,"block":[],"route":{},"notes":[]}
R=load_rules()
print(f"📚 قواعد مُكتسبة: إصدار {R['v']} · {len(R['block'])} نمط محظور · {len(R['route'])} قاعدة توجيه")

def blocked(head):
    return any(b and b in head for b in R["block"])

def reroute(head,cat):
    for c,keys in R["route"].items():
        if c!=cat and any(k and k in head for k in keys): return c
    return cat

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
            is_fa = label=="إيران"
            g="حسن" if is_fa else grade(src_ or clean(it.findtext("source","")))
            key=head[:40]
            if g in ("صحيح","حسن") and len(head)>15 and key not in seen and not blocked(head):
                seen.add(key)
                d={"head":head,"src":src_,"grade":g,"cat":label,
                   "link":clean(it.findtext("link","")),"fa":is_fa}
                if is_fa:
                    nm,who=fa_meta(url); d["src"]=nm; d["via"]=who
                items.append(d); n+=1
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
        out=gemini_json("ترجم هذه العناوين الإخبارية من الفارسية إلى العربية الصحفية الرصينة. "
            "ترجمة أمينة حرفية المعنى بلا إضافة ولا حذف ولا تهويل، واحتفظ بالأرقام والأسماء كما وردت. "
            "لا تترجم أسماء المصادر — سنضعها نحن.\n"
            "أخرج JSON فقط بصيغة: [{\"n\":الرقم,\"h\":\"العنوان العربي\"}]\n"+lst)
        for o in out:
            fa_items[o["n"]]["head"]=o["h"]
        print(f"🇮🇷 تُرجم {len(out)} عنوانًا عن الفارسية"); mark("turjuman","ok",f"{len(out)} عنوانًا")
    except Exception as e:
        print(f"ترجمة إيران عبر المسار الأول فشلت: {str(e)[:60]} — تحويل للاحتياطي")
        try:
            body={"model":"grok-4.5","input":[{"role":"user","content":
                "ترجم هذه العناوين من الفارسية إلى العربية الصحفية ترجمةً أمينة. "
                'أخرج JSON فقط: [{"n":الرقم,"h":"العنوان العربي"}]\n'+lst}],
                "max_output_tokens":2200}
            rq=urllib.request.Request("https://api.x.ai/v1/responses",data=json.dumps(body).encode(),
                headers={"Authorization":"Bearer "+GROK_KEY,"Content-Type":"application/json"})
            dd=json.load(urllib.request.urlopen(rq,timeout=180))
            tx="".join(c.get("text","") for o in dd.get("output",[]) if o.get("type")=="message"
                       for c in o.get("content",[]))
            tx=tx.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            for o in json.loads(tx[tx.find("["):tx.rfind("]")+1]):
                fa_items[o["n"]]["head"]=o["h"]
            print("🇮🇷 تُرجم عبر المسار الاحتياطي"); mark("turjuman","ok","المسار الاحتياطي")
        except Exception as e2:
            print(f"الاحتياطي فشل أيضًا: {str(e2)[:60]}"); mark("turjuman","fail",str(e2)[:60])
            items=[i for i in items if not i.get("fa")]

# ═══ خريطة الأخبار الكاملة للمنصة ═══
_rr=0
_would=[i for i in items if blocked(i["head"])]
if len(_would)>max(3,int(len(items)*0.35)):
    print(f"🛡️ الحجب كان سيزيل {len(_would)} من {len(items)} — عُطِّل هذه الجولة وتُراجَع القواعد")
    R["block"]=[]
for i in items:
    if blocked(i["head"]): i["cat"]="__drop__"; continue
    nc=reroute(i["head"],i["cat"])
    if nc!=i["cat"]: i["cat"]=nc; _rr+=1
items=[i for i in items if i["cat"]!="__drop__"]
if _rr: print(f"🧭 أعاد النظام توجيه {_rr} خبرًا وفق قواعده المكتسبة")

cats={}
for i in items:
    cats.setdefault(i["cat"],[]).append({k:i[k] for k in ("head","src","grade","link","fa") if k in i}
        | ({"via":i["via"]} if i.get("via") else {}))
json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),"cats":cats},
    open(f"{OUT}/news.json","w"),ensure_ascii=False,indent=1)
print(f"🗞️ news.json: {sum(len(v) for v in cats.values())} خبرًا في {len(cats)} أقسام")

# ═══ Grok: حصيلة الأزمة + عاجل من X (محسَّن بالكاش) ═══
INTEL=f"{OUT}/intel.json"

def intel_fresh(hours):
    try:
        p=json.load(open(INTEL))
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(p["updated"])).total_seconds()/3600
        return p, age<hours
    except Exception: return None, False

@agent("rasid")
def grok_intel():
    old, fresh = intel_fresh(6)
    if fresh and not os.environ.get("FORCE_INTEL"):
        print("♻️ intel.json حديث — تخطٍ (توفير)"); return {"skipped":1,"why":"كاش ٦ ساعات",**(old or {})}
    if not GROK_KEY:
        print("⚠️ لا مفتاح Grok"); return old
    P=("ابحث عن آخر المعطيات الموثقة عن الأزمة الإيرانية الأمريكية الحالية وأثرها على الخليج.\n"
       "أخرج JSON فقط:\n"
       '{"war":"اسم الأزمة","since":"YYYY-MM-DD","toll":[{"c":"البلد","f":"إيموجي العلم","d":"قتلى","w":"جرحى","dmg":"أبرز الأضرار جملة قصيرة","e":"الخسائر الاقتصادية"}],'
       '"brk":[{"h":"عنوان عاجل","s":"الحساب","u":"رابط"}]}\n'
       "أدرج هذه الدول جميعًا بهذا الترتيب إلزاميًا ولا تحذف أيًّا منها: إيران، الولايات المتحدة، "
       "الكويت، السعودية، الإمارات، قطر، البحرين، عُمان، العراق.\n"
       "إن لم تُوثَّق خسائر لدولة فاكتب d و w بقيمة «لا خسائر مؤكدة» واذكر في dmg أثرها غير المباشر "
       "(إنذارات، إغلاق مجال جوي، تعطل ملاحة، استضافة قواعد) — ولا تحذفها من القائمة.\n"
       "لكل رقم اذكر الجهة المعلِنة في src (مثل: وزارة الصحة الإيرانية، الدفاع المدني الكويتي، "
       "الأمم المتحدة) ورابطها في u وتاريخها في asof. إن كان الرقم تقديرًا صحفيًا لا إعلانًا رسميًا "
       "فاكتب في src: تقدير صحفي غير رسمي.\n"
       "٤ عناوين عاجلة كحد أقصى من حسابات موثقة خلال ٦ ساعات. أرقام موثقة فقط وإلا «غير مؤكد». "
       "لا تستخدم علامة تنصيص مزدوجة داخل النصوص. لا شيء خارج JSON.")
    body={"model":"grok-4.5","input":[{"role":"user","content":P}],
        "tools":[{"type":"web_search"},{"type":"x_search"}],
        "max_output_tokens":6000,"max_tool_calls":14}
    try:
        req=urllib.request.Request("https://api.x.ai/v1/responses",data=json.dumps(body).encode(),
            headers={"Authorization":"Bearer "+GROK_KEY,"Content-Type":"application/json"})
        d=json.load(urllib.request.urlopen(req,timeout=300))
        txt="".join(c.get("text","") for o in d.get("output",[]) if o.get("type")=="message"
                    for c in o.get("content",[]))
        txt=txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        if not txt:
            print(f"Grok رد فارغ (status={d.get('status')} {d.get('incomplete_details')})"); return old
        j=json.loads(txt[txt.find("{"):txt.rfind("}")+1]); j["updated"]=datetime.now(timezone.utc).isoformat(timespec="minutes")
        json.dump(j,open(INTEL,"w"),ensure_ascii=False,indent=1)
        print(f"🛰️ Grok: {len(j.get('toll',[]))} دول · {len(j.get('brk',[]))} عاجل · {d['usage']['total_tokens']} توكن")
        return j
    except Exception as e:
        print(f"Grok فشل: {str(e)[:100]}"); return old

INT=grok_intel()
if INT and INT.get("brk"):
    cats["عاجل"]=[{"head":b["h"],"src":b.get("s","X"),"grade":"حسن","link":b.get("u",""),"fa":False,"x":True,"official":str(b.get("s","")).lower().replace("@","") in OFFICIAL_HANDLES}
                  for b in INT["brk"]]
    json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),"cats":cats},
        open(f"{OUT}/news.json","w"),ensure_ascii=False,indent=1)
    print(f"⚡ أضيف قسم عاجل: {len(cats['عاجل'])}")


# ═══ حساب الإسناد الفعلي: خمسة معايير لكل خبر ═══
def isnad(it, heads_all):
    """يحسب المعايير الخمسة ويعيد (درجة, تفصيل) — لا شارة تُمنح بلا حساب."""
    h=it.get("head",""); src=(it.get("src") or "").lower()
    c={}
    # ١ الاتصال: مصدر أول بلا واسطة
    c["الاتصال"] = 2 if it.get("official") else (1 if it.get("link") else 0)
    # ٢ عدالة المصدر: طبقة الناشر
    c["عدالة المصدر"] = 2 if any(t in src for t in TIER1) else (1 if any(t in src for t in TIER2) else 0)
    # ٣ الضبط: تحديد زمني أو رقمي يقبل التحقق
    c["الضبط"] = 1 if re.search(r"\d", h) else 0
    # ٤ عدم الشذوذ: لا يتفرّد عن بقية ما جُمع
    toks=set(re.findall(r"[\u0600-\u06FF]{4,}", h))
    kin=sum(1 for o in heads_all if o is not h and len(toks & set(re.findall(r"[\u0600-\u06FF]{4,}", o)))>=2)
    c["عدم الشذوذ"] = 1 if kin>0 else 0
    # ٥ انتفاء العلة: لم يُخفّض في التدقيق
    c["انتفاء العلة"] = 0 if it.get("flag") else 1
    sc=sum(c.values())                      # من ٧
    g = "صحيح" if (sc>=6 and c["عدالة المصدر"]==2 and c["انتفاء العلة"]==1) else \
        ("حسن" if sc>=3 else "ضعيف الإسناد")
    return g, c, sc

def apply_isnad():
    allh=[i["head"] for l in cats.values() for i in l]
    tally={}
    for l in cats.values():
        for it in l:
            g,c,sc=isnad(it,allh)
            it["grade"]=g; it["isnad"]=c; it["score"]=sc
            tally[g]=tally.get(g,0)+1
    print("⚖️ الإسناد المحسوب: "+" · ".join(f"{k} {v}" for k,v in tally.items()))

# ═══ المُدقِّق: مراجعة وتمحيص + تطوير القواعد ═══
def safe_json(path):
    """يقرأ JSON ويصلح علامات التنصيص المتطفلة داخل النصوص العربية."""
    raw=open(path,encoding="utf-8").read()
    raw=raw[raw.find("{"):raw.rfind("}")+1]
    try: return json.loads(raw)
    except Exception: pass
    out=[]
    for ln in raw.split("\n"):
        m=re.match(r'^(\s*"[A-Za-z_]+"\s*:\s*")(.*)("\s*,?\s*)$', ln)
        if m and '"' in m.group(2):
            out.append(m.group(1)+m.group(2).replace('"','«')+m.group(3))
        else: out.append(ln)
    return json.loads("\n".join(out))

@agent("mudaqqiq")
def naqid():
    """يراجع ما جُمع، يستبعد غير الصالح ويخفّض المشكوك فيه، ثم يكتب قواعد تمنع تكرار الخطأ."""
    if os.environ.get("SKIP_COUNCIL") or not GEMINI_KEY: return
    P=("أنت «المُدقِّق» في منصة سَنَد — وظيفتك مراجعة المواد وتمحيصها قبل النشر.\n"
       "١) اقرأ daily/news.json و daily/intel.json و daily/rules.json.\n"
       "٢) راجع المواد واستبعد ما لا يصلح للنشر: عناوين خارج موضوع قسمها، تكرار، مبالغة أو إثارة، ادعاء بلا مصدر، تناقض مع الحصيلة.\n"
       "٣) اكتب daily/council.json:\n"
       '   {"checked":عدد,"flags":[{"h":"العنوان حرفيًا","issue":"سبب الجرح","action":"خُفّض|حُذف|أُقرّ"}],"verdict":"جملة واحدة"}\n'
       "٤) الأهم — طوّر النظام: اكتب daily/rules.json محدّثًا ليمنع تكرار ما جرحته اليوم:\n"
       '   {"v":رقم_الإصدار+1,"block":["كلمة تدل على خبر خارج نطاقنا"],'
       '"route":{"فلسطين":["غزة","الضفة"],"الخليج":["الكويت","السعودية"],"عالم":[]},'
       '"notes":["درس تعلّمناه بجملة قصيرة"]}\n'
       "قواعد صارمة لـ block: يُستخدم فقط لموضوعات خارج نطاق المنصة كليًا (رياضة، ترفيه، مشاهير، "
       "سياسة محلية أجنبية لا صلة لها بالخليج أو الأزمة). "
       "ممنوع منعًا باتًا إضافة أي كلمة تخص: الأزمة، الخليج، إيران، أمريكا، النفط، الطاقة، "
       "المفاوضات، الهدنة، الضربات، أو أسماء أماكن وردت في الأخبار الجارية — "
       "فإن كان الخبر في القسم الخطأ فقط، عالجه عبر route لا block.\n"
       "لا تتجاوز ٢٤ نمطًا في block ولا ١٢ ملاحظة — احذف الأقدم إن لزم.\n"
       "مهم: لا تستخدم علامة التنصيص المزدوجة داخل النصوص إطلاقًا — استعمل «» بدلًا منها.\n"
       "استخدم أداة الكتابة لإنشاء الملفين فعليًا. لا تطبع شيئًا آخر.")
    env={**os.environ,"GEMINI_CLI_TRUST_WORKSPACE":"true","NODE_TLS_REJECT_UNAUTHORIZED":"0"}
    try:
        subprocess.run(["gemini","--skip-trust","-m","gemini-flash-latest","-y","-p",P],
            env=env,timeout=480,capture_output=True)
        c=safe_json(f"{OUT}/council.json")
    except Exception as e:
        print(f"النَّاقِد تخطّى: {str(e)[:80]}"); return

    drop={f["h"][:28] for f in c.get("flags",[]) if f.get("action")=="حُذف"}
    down={f["h"][:28] for f in c.get("flags",[]) if f.get("action")=="خُفّض"}
    nd=nw=0
    for cat,lst in list(cats.items()):
        keep=[]
        for it in lst:
            h=it["head"]
            if any(d and (d in h or h[:28]==d) for d in drop): nd+=1; continue
            if any(w and (w in h or h[:28]==w) for w in down):
                it["grade"]="حسن"; it["flag"]="روجعت درجته"; nw+=1
            keep.append(it)
        if keep: cats[cat]=keep
        else: del cats[cat]

    # ── تشذيب القواعد المُكتسبة ──
    try:
        nr=safe_json(RULES)
        nr["block"]=[b for b in dict.fromkeys(nr.get("block",[])) if safe_pattern(b)][:24]
        nr["notes"]=list(dict.fromkeys(nr.get("notes",[])))[-12:]
        nr["v"]=max(int(nr.get("v",0)),R["v"]+1)
        nr["updated"]=datetime.now(timezone.utc).isoformat(timespec="minutes")
        json.dump(nr,open(RULES,"w"),ensure_ascii=False,indent=1)
        grew=len(nr["block"])-len(R["block"])
        print(f"🧬 تطوّر ذاتي: إصدار {nr['v']} · {len(nr['block'])} نمط (+{grew}) · {len(nr['notes'])} درس")
        mark("musannif","ok",f"إصدار {nr['v']} · {len(nr['block'])} نمط")
    except Exception as e:
        nr=R; print(f"القواعد لم تُحدَّث: {str(e)[:60]}")

    # ── سجل التطوّر ──
    try: ev=json.load(open(f"{OUT}/evolution.json"))
    except Exception: ev={"runs":[]}
    ev["runs"]=(ev.get("runs",[])+[{"t":datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "checked":c.get("checked",0),"removed":nd,"downgraded":nw,
        "rules":len(nr.get("block",[])),"v":nr.get("v",0)}])[-40:]
    rec=ev["runs"][-6:]
    ev["trend"]=round(sum(r["removed"] for r in rec)/max(len(rec),1),1)
    ev["lessons"]=nr.get("notes",[])[-4:]
    json.dump(ev,open(f"{OUT}/evolution.json","w"),ensure_ascii=False,indent=1)

    for k in [k for k,v in cats.items() if len(v)<3 and k not in ("عاجل",)]:
        print(f"🔇 أُخفي قسم «{k}» ({len(cats[k])} خبرًا فقط)"); del cats[k]
    apply_isnad()
    c["applied"]={"removed":nd,"downgraded":nw}
    c["rules_v"]=nr.get("v",0)
    c["updated"]=datetime.now(timezone.utc).isoformat(timespec="minutes")
    json.dump(c,open(f"{OUT}/council.json","w"),ensure_ascii=False,indent=1)
    json.dump({"updated":c["updated"],"cats":cats},open(f"{OUT}/news.json","w"),ensure_ascii=False,indent=1)
    print(f"⚖️ المُدقِّق: استُبعد {nd} · خُفِّض {nw} · المتبقي {sum(len(v) for v in cats.values())}")

# ═══ المُستقرِئ: استقراء الساعات القادمة + محاسبة ذاتية ═══
FCAST=f"{OUT}/forecast.json"

@agent("mustaqri")
def mustaqri():
    """يستقرئ ما قد يقع، ويحاسب نفسه على استقرائه السابق."""
    try:
        prev=json.load(open(FCAST))
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(prev["updated"])).total_seconds()/3600
    except Exception: prev,age=None,999
    if age<3:
        print("♻️ الاستقراء حديث — تخطٍ (توفير)"); return {"skipped":1,"why":"كاش ٣ ساعات"}
    if not GROK_KEY: return

    heads=[i["head"] for l in cats.values() for i in l][:14]
    toll=", ".join(t.get("c","")+": "+str(t.get("d","")) for t in (INT or {}).get("toll",[]))
    review=""
    if prev and prev.get("scenarios"):
        review=("\n\nاستقراؤك السابق قبل %.1f ساعة كان:\n"%age + "\n".join(
            "- (%s%%) %s"%(x.get("p"),x.get("s","")) for x in prev["scenarios"]) +
            "\nقيّم بصدق ما وقع منه فعلًا وأضف الحقل review.")
    P=("أنت «المُستقرِئ» في منصة سَنَد. استقرئ ما قد يقع في الساعات القادمة بناءً على "
       "تصريحات ترامب والمسؤولين، والوقائع الجارية، والسوابق التاريخية المشابهة.\n\n"
       "الأخبار الحالية:\n- "+"\n- ".join(heads)+"\n\nالحصيلة: "+toll+review+"\n\n"
       "ابحث عن آخر تصريحات ترامب والبيت الأبيض وإيران خلال ١٢ ساعة، ثم أخرج JSON فقط:\n"
       '{"horizon":"النافذة الزمنية",'
       '"signals":[{"q":"التصريح أو الواقعة","who":"القائل","w":"عالٍ|متوسط|منخفض"}],'
       '"scenarios":[{"s":"السيناريو","p":نسبة_رقم,"why":"المبرر مع السابقة التاريخية","watch":"المؤشر المؤكد أو النافي"}],'
       '"review":[{"s":"السيناريو السابق","r":"وقع|جزئيًا|لم يقع","note":"بجملة"}],'
       '"caveat":"تحذير صريح بأن هذا استقراء احتمالي لا يقين"}\n'
       "٣ سيناريوهات كحد أقصى ومجموع نسبها ١٠٠. لا تستخدم علامة تنصيص مزدوجة داخل النصوص. "
       "لا تذكر أسماء نماذج أو شركات. لا شيء خارج JSON.")
    body={"model":"grok-4.5","input":[{"role":"user","content":P}],
        "tools":[{"type":"web_search"},{"type":"x_search"}],
        "max_output_tokens":3200,"max_tool_calls":7}
    try:
        req=urllib.request.Request("https://api.x.ai/v1/responses",data=json.dumps(body).encode(),
            headers={"Authorization":"Bearer "+GROK_KEY,"Content-Type":"application/json"})
        d=json.load(urllib.request.urlopen(req,timeout=300))
        txt="".join(c.get("text","") for o in d.get("output",[]) if o.get("type")=="message"
                    for c in o.get("content",[]))
        txt=txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        j=json.loads(txt[txt.find("{"):txt.rfind("}")+1])
    except Exception as e:
        print("المُستقرِئ تخطّى: "+str(e)[:90]); return

    # ── سجل الإصابة ──
    hist=(prev or {}).get("history",[])
    if prev and prev.get("scenarios"):
        prevs=[x.get("s","")[:40] for x in prev["scenarios"]]
        for r in j.get("review",[]):
            sc=r.get("s","")
            if r.get("r") in ("وقع","جزئيًا","لم يقع") and any(p[:20] in sc or sc[:20] in p for p in prevs):
                hist.append({"t":prev.get("updated",""),"s":sc[:70],"r":r["r"]})
    else: j["review"]=[]
    hist=hist[-24:]
    hit=sum(1 for h in hist if h["r"]=="وقع"); part=sum(1 for h in hist if h["r"]=="جزئيًا")
    j["history"]=hist
    j["score"]={"n":len(hist),"hit":hit,"partial":part,
        "acc":round((hit+part*0.5)/max(len(hist),1)*100)}
    j["updated"]=datetime.now(timezone.utc).isoformat(timespec="minutes")
    json.dump(j,open(FCAST,"w"),ensure_ascii=False,indent=1)
    print("🔮 الاستقراء: %d سيناريو · %d إشارة · دقة تراكمية %d%% (%d سابقة)"%(
        len(j.get("scenarios",[])),len(j.get("signals",[])),j["score"]["acc"],len(hist)))

# ═══ المَنبع: بيانات رسمية من الجهات مباشرة (أعلى درجات الاتصال) ═══
OFFI=f"{OUT}/official.json"

@agent("manba")
def manba():
    """يجلب آخر بيان رسمي من كل جهة — مصدر أول بلا واسطة."""
    try:
        old=json.load(open(OFFI))
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(old["updated"])).total_seconds()/3600
    except Exception: old,age=None,999
    old=old or {}
    if age<4 and not os.environ.get("FORCE_OFFICIAL"):
        print("♻️ المَنبع حديث — تخطٍ (توفير)"); return {"skipped":1,"why":"كاش ٣ ساعات"}
    if not GROK_KEY: return
    B=[("القيادة المركزية الأمريكية CENTCOM، وزارة الكهرباء والماء الكويتية، "
        "قوة الإطفاء العام الكويتية، وكالة الأنباء الكويتية كونا، وزارة الداخلية الكويتية"),
       ("وزارة الصحة الكويتية، الداخلية أو الدفاع المدني السعودي، وزارة الخارجية الإماراتية، "
        "وزارة الخارجية القطرية، وزارة الداخلية البحرينية، وزارة الخارجية العُمانية")]
    BATCH=B[(datetime.now(timezone.utc).hour//4)%2]
    P=("ابحث في منصة إكس والمواقع الرسمية عن آخر بيان أو منشور رسمي من كل جهة أدناه "
       "خلال ١٢ ساعة الماضية بشأن الأزمة الجارية.\n"
       "الجهات: "+BATCH+".\n"
       "لكل جهة أعطني الحساب الرسمي الموثّق الفعلي كما هو على إكس — لا تخترع حسابًا — "
       "وآخر منشور ذي صلة مترجمًا للعربية إن لزم، ترجمةً أمينة بلا تهويل.\n"
       'أخرج JSON فقط: [{"c":"البلد","f":"إيموجي العلم","e":"اسم الجهة بالعربية",'
       '"h":"@الحساب","p":"نص البيان بإيجاز","t":"الوقت التقريبي","u":"رابط المنشور"}]\n'
       "إن لم تجد منشورًا حديثًا لجهة فاحذفها من القائمة. "
       "لا تستخدم علامة تنصيص مزدوجة داخل النصوص. لا شيء خارج JSON.")
    body={"model":"grok-4.5","input":[{"role":"user","content":P}],
        "tools":[{"type":"x_search"},{"type":"web_search"}],
        "max_output_tokens":2600,"max_tool_calls":6}
    try:
        req=urllib.request.Request("https://api.x.ai/v1/responses",data=json.dumps(body).encode(),
            headers={"Authorization":"Bearer "+GROK_KEY,"Content-Type":"application/json"})
        d=json.load(urllib.request.urlopen(req,timeout=420))
        txt="".join(c.get("text","") for o in d.get("output",[]) if o.get("type")=="message"
                    for c in o.get("content",[]))
        txt=txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        lst=json.loads(txt[txt.find("["):txt.rfind("]")+1])
        lst=[x for x in lst if x.get("h","").startswith("@") and x.get("p")]
        if not lst: raise ValueError("قائمة فارغة")
        keep={x["h"].lower():x for x in (old or {}).get("src",[])}
        for x in lst: keep[x["h"].lower()]=x
        merged=list(keep.values())[-14:]
        json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),"src":merged},
            open(OFFI,"w"),ensure_ascii=False,indent=1)
        print("📡 المَنبع: +%d جهة (المجموع %d) · %d توكن"%(len(lst),len(merged),d["usage"]["total_tokens"]))
    except Exception as e:
        print("المَنبع تخطّى: "+str(e)[:90])

manba()

# ═══ المُطابِق: يقابل أرقام الحصيلة بمصدر مستقل ═══
@agent("mutabiq")
def mutabiq():
    """يتحقق من أرقام الحصيلة عبر بحث مستقل ويصنّفها: مطابق / متباين / غير موثّق."""
    try: t=json.load(open(INTEL))
    except Exception: return
    try:
        v=json.load(open(f"{OUT}/verify.json"))
        if v.get("src_updated")==t.get("updated"):
            print("♻️ المُطابَقة مطابقة للحصيلة — تخطٍ"); return {"skipped":1,"why":"لا جديد في الحصيلة"}
    except Exception: pass
    if not GROK_KEY: return
    rows="\n".join("- %s: قتلى %s، جرحى %s (المُعلن: %s)"%(x.get("c"),x.get("d"),x.get("w"),x.get("src","غير مذكور"))
                    for x in t.get("toll",[]))
    P=("تحقّق من هذه الأرقام عبر مصادر مستقلة (وكالات دولية، أمم متحدة، جهات رسمية) "
       "وقُل لكلٍّ منها هل تطابق ما هو منشور أم تتباين.\n"+rows+"\n\n"
       'أخرج JSON فقط: [{"c":"البلد","r":"مطابق|متباين|غير موثّق","alt":"الرقم البديل إن وُجد",'
       '"by":"الجهة المستقلة","note":"سطر واحد"}]\n'
       "كن صارمًا: إن لم تجد مصدرًا مستقلًا فاكتب غير موثّق. "
       "لا تستخدم علامة تنصيص مزدوجة داخل النصوص. لا شيء خارج JSON.")
    try:
        body={"model":"grok-4.5","input":[{"role":"user","content":P}],
            "tools":[{"type":"web_search"}],"max_output_tokens":2200,"max_tool_calls":6}
        req=urllib.request.Request("https://api.x.ai/v1/responses",data=json.dumps(body).encode(),
            headers={"Authorization":"Bearer "+GROK_KEY,"Content-Type":"application/json"})
        d=json.load(urllib.request.urlopen(req,timeout=300))
        txt="".join(c.get("text","") for o in d.get("output",[]) if o.get("type")=="message"
                    for c in o.get("content",[]))
        txt=txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        lst=json.loads(txt[txt.find("["):txt.rfind("]")+1])
        ok=sum(1 for x in lst if x.get("r")=="مطابق")
        json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "src_updated":t.get("updated"),"matched":ok,"total":len(lst),"rows":lst},
            open(f"{OUT}/verify.json","w"),ensure_ascii=False,indent=1)
        print("🔍 المُطابِق: %d/%d رقمًا مطابقًا لمصدر مستقل"%(ok,len(lst)))
    except Exception as e:
        print("المُطابِق تخطّى: "+str(e)[:80])

mutabiq()

mustaqri()

# ═══ فقرة المحلل الاستراتيجي (وكيل — يُصرَّح بذلك) ═══
@agent("murtajil")
def analyst_segment():
    """يحوّل الاستقراء إلى تحليل منطوق بأسلوب ضيف النشرات، بصوت مغاير للمذيع."""
    try: f=json.load(open(FCAST))
    except Exception: return
    try:
        a_old=json.load(open(f"{OUT}/analyst.json"))
        if a_old.get("src")==f.get("updated"):
            print("♻️ قراءة المحلل مطابقة — تخطٍ"); return {"skipped":1,"why":"مطابقة للاستقراء"}
    except Exception: pass
    if not GEMINI_KEY: return

    scn="\n".join("- (%s%%) %s | السابقة: %s"%(x.get("p"),x.get("s",""),x.get("why","")[:150])
                   for x in f.get("scenarios",[]))
    sig="\n".join("- %s: %s"%(x.get("who",""),x.get("q","")[:120]) for x in f.get("signals",[])[:4])
    P=("اكتب فقرة تحليل استراتيجي منطوقة، بأسلوب الضيف الخبير في النشرات الإخبارية العربية.\n\n"
       "الإشارات:\n"+sig+"\n\nالسيناريوهات:\n"+scn+"\n\n"
       "القواعد: ابدأ بـ«شكرًا لك. المشهد اليوم يُقرأ من ثلاث زوايا:». "
       "٩٠ إلى ١٢٠ كلمة. عربية فصيحة رصينة بلا مبالغة. اذكر النسبة الأعلى صراحةً بالأرقام العربية. "
       "استشهد بسابقة تاريخية واحدة. اختم بـ«وتبقى هذه قراءةً احتمالية، والمؤشر الحاسم هو» ثم اذكر المؤشر. "
       "أخرج النص فقط بلا عناوين ولا رموز ولا أسماء نماذج أو شركات.")
    try:
        body={"contents":[{"parts":[{"text":P}]}],
            "generationConfig":{"maxOutputTokens":700,"temperature":0.55,
                "thinkingConfig":{"thinkingBudget":0}}}
        req=urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key="+GEMINI_KEY,
            data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
        d=json.load(urllib.request.urlopen(req,timeout=90))
        txt=d["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print("فقرة المحلل تخطّت: "+str(e)[:80]); return

    mp3=f"{OUT}/analyst.mp3"
    try:
        import edge_tts, ssl as _s, asyncio as _a
        import edge_tts.communicate as _c
        _ctx=_s.create_default_context(); _ctx.check_hostname=False; _ctx.verify_mode=_s.CERT_NONE
        try: _c._SSL_CTX=_ctx
        except Exception: pass
        async def _go():
            await edge_tts.Communicate(txt,"ar-SA-HamedNeural",rate="-4%").save(mp3)
        _a.run(_go())
        ok=os.path.getsize(mp3)>4000
    except Exception as e:
        print("صوت المحلل تعذّر: "+str(e)[:70]); ok=False

    json.dump({"name":"المُستقرِئ","title":"محلل استراتيجي · وكيل ذكاء اصطناعي",
        "text":txt,"audio":"analyst.mp3" if ok else "",
        "src":f.get("updated",""),"avatar":"analyst.jpg",
        "updated":datetime.now(timezone.utc).isoformat(timespec="minutes")},
        open(f"{OUT}/analyst.json","w"),ensure_ascii=False,indent=1)
    print("🎤 فقرة المحلل: %d كلمة%s"%(len(txt.split())," + صوت" if ok else ""))

analyst_segment()

naqid()

if os.environ.get("NEWS_ONLY"):
    try:
        _m=json.load(open(f"{OUT}/latest.json")); _t=datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if _m.get("video_date")==_t: mark("rawi","ok","فيديو اليوم جاهز")
        elif _m.get("date")==_t:     mark("rawi","ok","نشرة اليوم صوتيًا")
        else:                        mark("rawi","skip","بانتظار ٦ مساءً")
    except Exception: mark("rawi","skip","بانتظار أول نشرة")
    archive()
    save_agents()
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

try: mark("rawi", _LOG.get("rawi",{}).get("status","ok"), _LOG.get("rawi",{}).get("note","نشرة اليوم")); save_agents()
except Exception: pass
