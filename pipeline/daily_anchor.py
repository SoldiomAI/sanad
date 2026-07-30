#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سَنَد — خط الإنتاج الآلي: RSS → إسناد → نص → صوت فهد → فيديو مذيع مُجزّأ
LongCat 720p أساسي + EchoMimic احتياطي | افتتاحية/خاتمة مكاشة | يشتغل صفر تدخّل"""
import os, re, sys, json, time, asyncio, shutil, subprocess, hashlib, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

GROK_KEY = os.environ.get("GROK_API_KEY",""); HF_TOKEN = os.environ.get("HF_TOKEN",""); GEMINI_KEY = os.environ.get("GEMINI_API_KEY",""); OUT="daily"; os.makedirs(OUT, exist_ok=True)
TIER1=["centcom","kuna","كونا","mew_kwt","kff_kw","moi_bahrain","mofauae","mofaqatar","وكالة الأنباء الكويتية","reuters","رويترز","afp","فرانس برس","ap news","أسوشيتد","kuna","كونا","wam","وام","spa","واس","bna","qna","ona"]
TIER2=["aljazeera","الجزيرة","alarabiya","العربية","skynews","سكاي نيوز","bbc","france24","cnn","alqabas","القبس","aljarida","الجريدة","alrai","الراي","kuwaittimes","arabtimes","gulfnews","thenational","alkhaleej","الخليج","aawsat","الشرق الأوسط","independentarabia","اندبندنت","إندبندنت","irna","ایرنا","إرنا","tasnim","تسنیم","تسنيم","mehr","مهر","fars","فارس","isna","ایسنا","العالم","press tv","khabaronline","خبرگزاری","iran international","ایران اینترنشنال","bbc persian","بی‌بی‌سی","همشهری","entekhab","اعتماد"]
FEEDS=[("الخليج","https://news.google.com/rss/search?q=%D8%A7%D9%84%D9%83%D9%88%D9%8A%D8%AA+OR+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D8%A9+OR+%D8%A7%D9%84%D8%A5%D9%85%D8%A7%D8%B1%D8%A7%D8%AA&hl=ar&gl=KW&ceid=KW:ar"),
       ("فلسطين","https://news.google.com/rss/search?q=%D8%BA%D8%B2%D8%A9+OR+%D9%81%D9%84%D8%B3%D8%B7%D9%8A%D9%86&hl=ar&gl=KW&ceid=KW:ar"),
       ("عالم","https://news.google.com/rss/headlines/section/topic/WORLD?hl=ar&gl=KW&ceid=KW:ar"),
       ("تقنية","https://news.google.com/rss/search?q=%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1+%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A&hl=ar&gl=KW&ceid=KW:ar"),
       ("تقنية","https://news.google.com/rss/search?q=%22%D9%86%D9%85%D9%88%D8%B0%D8%AC+%D9%85%D9%81%D8%AA%D9%88%D8%AD+%D8%A7%D9%84%D9%85%D8%B5%D8%AF%D8%B1%22+OR+%22%D8%A5%D8%B5%D8%AF%D8%A7%D8%B1+%D9%86%D9%85%D9%88%D8%B0%D8%AC%22&hl=ar&ceid=KW:ar"),
       ("تقنية","https://huggingface.co/blog/feed.xml"),
       ("تقنية","https://openai.com/blog/rss.xml"),
       ("تقنية","https://deepmind.google/blog/rss.xml"),
       ("تقنية","https://blog.google/technology/ai/rss/"),
       ("اقتصاد","https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ar&gl=KW&ceid=KW:ar"),
       ("إيران","https://feeds.bbci.co.uk/persian/rss.xml"),
       ("إيران","https://www.iranintl.com/feed"),
       # مصادرُ مباشرةٌ موثوقة بخدمةٍ عربيّة — تنويعٌ يعزّزُ المصداقية دون عناوينَ أجنبية
       ("عالم","https://feeds.bbci.co.uk/arabic/rss.xml"),
       ("عالم","https://www.france24.com/ar/rss"),
       # منافذُ عربيّةٌ كبرى مباشرة — رواببُ مقالاتٍ حقيقيّةٌ بصورِها (لا وسيطَ غوغل)
       ("عالم","https://www.aljazeera.net/aljazeerarss"),
       ("الخليج","https://www.skynewsarabia.com/web/rss"),
       ("عالم","https://arabic.cnn.com/rss"),
       ("الخليج","https://aawsat.com/feed"),
       ("عالم","https://www.independentarabia.com/rss.xml"),
       # تعميقُ تغطيةِ الخليجِ عبر «أخبار غوغل» (تُصنَّف بدرجةِ المنفذِ الراوي نفسِه)
       ("الخليج","https://news.google.com/rss/search?q=%D9%82%D8%B7%D8%B1%20OR%20%D8%A7%D9%84%D8%A8%D8%AD%D8%B1%D9%8A%D9%86%20OR%20%D8%B3%D9%84%D8%B7%D9%86%D8%A9%20%D8%B9%D9%85%D8%A7%D9%86&hl=ar&gl=KW&ceid=KW:ar"),
       ("الخليج","https://news.google.com/rss/search?q=%D8%A7%D9%84%D9%83%D9%88%D9%8A%D8%AA%20%28%D9%85%D8%AC%D9%84%D8%B3%20%D8%A7%D9%84%D9%88%D8%B2%D8%B1%D8%A7%D8%A1%20OR%20%D9%88%D8%B2%D8%A7%D8%B1%D8%A9%20OR%20%D8%A7%D9%84%D8%AF%D9%8A%D9%88%D8%A7%D9%86%20%D8%A7%D9%84%D8%A3%D9%85%D9%8A%D8%B1%D9%8A%20OR%20%D8%A5%D8%B9%D8%B5%D8%A7%D8%B1%20OR%20%D8%B7%D9%88%D8%A7%D8%B1%D8%A6%29&hl=ar&gl=KW&ceid=KW:ar")]

# مصادر إيران: الاسم المعتمد وهوية الجهة — تُعرض للقارئ صراحةً
EN_SRC={
 "huggingface.co":("هَغِنغ فيس","منصّة النماذج المفتوحة"),
 "openai.com":("أوبن إيه آي","مختبر أبحاث"),
 "deepmind.google":("ديب مايند","مختبر أبحاث — غوغل"),
 "blog.google":("مدونة غوغل","شركة"),
}
def en_meta(url):
    for k,v in EN_SRC.items():
        if k in url: return v
    return (None,None)

FA_SRC={
 "feeds.bbci.co.uk":("بي بي سي فارسي","هيئة بث بريطانية عامة"),
 "iranintl.com":("إيران إنترناشونال","قناة فارسية مقرّها لندن"),
}
def fa_meta(url):
    for k,v in FA_SRC.items():
        if k in url: return v
    return ("مصدر فارسي","غير محدد")

# مصادرُ مباشرةٌ موثوقة (عربيّةٌ ودوليّة) — تنويعٌ يعزّزُ المصداقيّة، بهويّةٍ معروضةٍ للقارئ.
# مفاتيحُها أكثرُ تخصيصًا من مفاتيحِ بي بي سي الفارسيّة فلا تتعارض.
DIRECT_SRC={
 "bbci.co.uk/arabic":("بي بي سي عربي","هيئة بث بريطانية عامة","حسن"),
 "france24.com/ar":("فرانس ٢٤ عربي","قناة دولية فرنسية عامة","حسن"),
 "aljazeera.net":("الجزيرة نت","شبكة إخبارية قطرية","حسن"),
 "skynewsarabia.com":("سكاي نيوز عربية","قناة إخبارية إماراتية بريطانية","حسن"),
 "arabic.cnn.com":("CNN بالعربية","شبكة إخبارية أمريكية","حسن"),
 "aawsat.com":("الشرق الأوسط","صحيفة عربية دولية","حسن"),
 "independentarabia.com":("اندبندنت عربية","نسخة عربية من الإندبندنت البريطانية","حسن"),
}
def direct_meta(url):
    for k,v in DIRECT_SRC.items():
        if k in url: return v
    return (None,None,None)

# ═══════════ طبقة الوكلاء — سجلٌّ ومراقبةٌ حيّة ═══════════
AGENTS_F=f"{OUT}/agents.json"
AGENTS=[
 ("hurr","الوكيلُ الحرّ","🆓","يجلبُ من مصادرَ مجّانيّةٍ بلا مفاتيح — RSS رسميّ عبر أخبار غوغل"),
 ("rasid","الرَّاصِد","🛰️","يرصد المصادر الحيّة ويجمع الحصيلة والعاجل"),
 ("mutabiq","المُطابِق","🔍","يقابل أرقام الحصيلة بمصادر مستقلة"),
 ("manba","المَنبع","📡","ينقل البيانات الرسمية عن الجهات مباشرة"),
 ("munabbih","المُنبِّه","⚠️","يجمع تحذيرات الجهات وتوجيهاتها للمواطن"),
 ("multaqit","المُلتَقِط","🔍","يلتقط الادعاءات المنتشرة قبل أن تُنشر — سند تحت المجهر"),
 ("fahis","الفاحِص","🔗","يفتح الرابط بنفسه ويتأكّد أنه حيّ ويحتوي الادعاء"),
 ("mukharrij","المُخرِّج","📑","يبحث ويراجع المواقع ويُثبت المصدر ويحكم على الشائعة"),
 ("munaqqih","المُنقِّح","🔁","يراجعُ الشائعاتِ كلَّ دورة: يطوي القديمَ ويعيدُ الفحصَ ويُثبتُ قائلَها"),
 ("miqyas","المِقياس","🌡️","يحسبُ مؤشّرَ عدم الاستقرار الإقليميّ حسابًا شفّافًا من كثافة المواد المُسنَدة"),
 ("mustaqsi","المُستَقصي","🎯","ينقل أعداد الذخائر عن وزارات الدفاع مباشرة"),
 ("turjuman","التَّرْجُمَان","🗣️","ينقل الخبر الفارسي إلى العربية ترجمةً أمينة"),
 ("mudaqqiq","المُدقِّق","⚖️","يراجع المواد ويستبعد ما لا يصلح للنشر"),
 ("musannif","المُصنِّف","🧬","يطوّر قواعد الفرز بعد كل جولة"),
 ("mustaqri","المُستقرِئ","🔮","يستقرئ ما قد يقع من السوابق والتصريحات"),
 ("murtajil","المُحلِّل","🎤","يصوغ قراءة الساعة ويؤدّيها صوتًا"),
 ("mudawwin","المُدوِّن","🖋️","يكتبُ عمودَ الجريدة اليوميّ من أخبار اليوم المُسنَدة"),
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

# ═══ حزمة واحدة: طلبٌ واحدٌ بدل اثني عشر ═══

# ═══ النشرة الآلية: بثٌّ ذاتيٌّ لقناة تلغرام ═══
TG_TOKEN=os.environ.get("TELEGRAM_BOT_TOKEN","")
TG_CHAT=os.environ.get("TELEGRAM_CHANNEL","")

def tg_send(text,audio=None,silent=False):
    if not (TG_TOKEN and TG_CHAT): return False
    try:
        if audio and os.path.exists(audio):
            import mimetypes,uuid as _u
            bnd="----sanad"+_u.uuid4().hex
            parts=[]
            def fld(n,v):
                parts.append(f"--{bnd}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n".encode())
            fld("chat_id",TG_CHAT); fld("caption",text[:1000]); fld("parse_mode","HTML")
            fld("title","نشرة سَنَد"); fld("performer","سَنَد")
            parts.append(f"--{bnd}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"{os.path.basename(audio)}\"\r\nContent-Type: audio/mpeg\r\n\r\n".encode())
            parts.append(open(audio,"rb").read()); parts.append(f"\r\n--{bnd}--\r\n".encode())
            body=b"".join(parts)
            req=urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/sendAudio",
                data=body,headers={"Content-Type":f"multipart/form-data; boundary={bnd}"})
        else:
            d=json.dumps({"chat_id":TG_CHAT,"text":text[:4000],"parse_mode":"HTML",
                "disable_web_page_preview":True,"disable_notification":silent}).encode()
            req=urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                data=d,headers={"Content-Type":"application/json"})
        r=json.load(urllib.request.urlopen(req,timeout=90))
        return bool(r.get("ok"))
    except Exception as e:
        print(f"تلغرام تعذّر: {str(e)[:80]}"); return False

def broadcast_bulletin():
    """يبثّ نشرة اليوم صوتًا ونصًّا فور جاهزيتها."""
    try: m=json.load(open(f"{OUT}/latest.json"))
    except Exception: return
    try:
        st=json.load(open(f"{OUT}/tg.json"))
        if st.get("bulletin")==m.get("date"): return
    except Exception: st={}
    site="https://isnad.news"
    txt=(f"<b>🎙️ نشرة سَنَد — {m['date']}</b>\n\n"+m["script"][:2600]+
         f"\n\n<a href=\"{site}\">افتح المنصة ↗</a>")
    ap=f"{OUT}/{m.get('audio','')}" if m.get("audio") else None
    if tg_send(txt,audio=ap):
        st["bulletin"]=m["date"]
        json.dump(st,open(f"{OUT}/tg.json","w"),ensure_ascii=False)
        print("📣 بُثّت النشرة على القناة")

def _tg_state():
    try: return json.load(open(f"{OUT}/tg.json"))
    except Exception: return {}

def _tg_save(st):
    for k in ("news","alerts","official"):
        if isinstance(st.get(k),list): st[k]=st[k][-200:]
    json.dump(st,open(f"{OUT}/tg.json","w"),ensure_ascii=False,indent=1)

def _fp(s):
    """بصمة مستقرّة تمنع التكرار حتى لو تغيّرت الصياغة قليلًا."""
    import hashlib,re as _re
    t=_re.sub(r"[^\w\u0600-\u06FF]+"," ",str(s or "")).strip()[:120]
    return hashlib.md5(t.encode()).hexdigest()[:14]

SITE="https://isnad.news"

# طزاجةُ القناة: لا يُبثُّ على تلغرام إلا خبرُ *يومِ اليوم* بتوقيت الكويت (UTC+3).
# سببُ التشديد: طلبٌ صريح ألّا يُرسَل خبرُ الأمس (١٨) في اليوم التالي (١٩).
_KW=timezone(timedelta(hours=3))
_TG_GRACE_H=6   # سماحُ منتصفِ الليل: نسمحُ بخبرٍ طازجٍ جدًّا وإن حملَ تاريخَ أمسِ الكويت
def _today_kw(at):
    """صحيحٌ إن كان الخبرُ من يومِ الكويتِ نفسِه، أو طازجًا جدًّا (≤٦ س) عبرَ منتصفِ الليل —
    كي لا تصمتَ القناةُ بعد منتصفِ الليل ولا يُحجَبَ عاجلٌ عمرُه دقائقُ عبرَ حدِّ اليوم."""
    if not at: return False                      # بلا ختمٍ زمنيّ ⇒ لا نضمنُ حداثتَه
    try:
        t=datetime.fromisoformat(str(at).replace("Z","+00:00"))
        if t.tzinfo is None: t=t.replace(tzinfo=timezone.utc)
        now=datetime.now(timezone.utc)
        if t.astimezone(_KW).date()==now.astimezone(_KW).date(): return True   # خبرُ اليوم
        return 0 <= (now-t).total_seconds() <= _TG_GRACE_H*3600                 # أو طازجٌ جدًّا
    except Exception: return False

_AR_MON={"يناير":1,"فبراير":2,"مارس":3,"أبريل":4,"إبريل":4,"مايو":5,"يونيو":6,
         "يوليو":7,"أغسطس":8,"اغسطس":8,"سبتمبر":9,"أكتوبر":10,"اكتوبر":10,
         "نوفمبر":11,"ديسمبر":12}
def _stmt_stale(t):
    """صحيحٌ إن ذكرَ البيانُ تاريخًا صريحًا سابقًا لليومِ (بتوقيت الكويت) — فلا نبثُّه اليوم."""
    import re as _re
    m=_re.search(r"(\d{1,2})\s+([^\s0-9]+)\s+(\d{4})", str(t or ""))
    if not m: return False                       # بلا تاريخٍ صريح ⇒ لا نحكمُ بقِدَمِه
    mon=_AR_MON.get(m.group(2))
    if not mon: return False
    try:
        d=datetime(int(m.group(3)),mon,int(m.group(1)),tzinfo=_KW).date()
        return d < datetime.now(_KW).date()      # أيُّ تاريخٍ قبلَ اليوم = قديم
    except Exception: return False

def _ok_url(u):
    """رابطٌ صالحٌ للتحقّق: http/https فعليّ لا نصٌّ مخترَع."""
    u=str(u or "").strip()
    return u.startswith("http://") or u.startswith("https://")

# ألفاظُ الأحداثِ الصلبة: ادّعاؤها منسوبًا لجهةٍ يتطلّبُ مصدرًا يُتحقَّق منه، وإلّا أُسقط.
_HARD_EVENT=("ضرب","استهد","قصف","اعترض","اعتراض","إطلاق","أطلق","قتلى","قتيل","جرحى",
             "اقتحام","سقوط","أسقط","دمّر","دمر","تفجير","انفجار","غارة","صافرة")

def _stmt_old_days(t, days):
    """صحيحٌ إن حملَ البيانُ تاريخًا صريحًا (بسنةٍ أو دونها) أقدمَ من (days) يومًا — نُسقطُه
    من «من المَنبع» كي لا يبقى بيانٌ عمرُه أيامٌ ظاهرًا كأنّه رسميٌّ راهن. «اليوم/أمس» يبقى."""
    import re as _re
    today=datetime.now(_KW).date()
    # نمسحُ كلَّ «رقم + كلمة [+ سنة]» ولا نحكمُ إلا على ما كلمتُه شهرٌ فعليّ،
    # كي لا يخدعَنا وقتٌ مثل «١٣:٠٠ غرينتش» فيحجبَ التاريخَ الحقيقيَّ «١٨ يوليو».
    for m in _re.finditer(r"(\d{1,2})\s+([^\s0-9]+)(?:\s+(\d{4}))?", str(t or "")):
        mon=_AR_MON.get(m.group(2))
        if not mon: continue
        try:
            yr=int(m.group(3)) if m.group(3) else today.year
            d=datetime(yr,mon,int(m.group(1)),tzinfo=_KW).date()
            if d>today: d=d.replace(year=d.year-1)   # لا تاريخَ مستقبليّ
            if (today-d).days > days: return True
        except Exception: continue
    return False

def broadcast_news():
    """يبثّ الأخبارَ الحصريّة فقط: عاجلٌ أو صحيحُ الإسناد — أخبارَ اليومِ ومرّةً واحدة أبدًا."""
    try: d=json.load(open(f"{OUT}/news.json"))
    except Exception: return
    st=_tg_state(); seen=set(st.get("news",[]))
    pool=[]
    for cat,lst in (d.get("cats") or {}).items():
        for it in lst:
            if not _today_kw(it.get("at")): continue    # خبرُ *يومِ اليوم* فقط (توقيت الكويت) — لا خبرَ أمس
            urgent = cat=="عاجل"
            strong = it.get("grade")=="صحيح"
            official= (it.get("score") or 0)>=6
            if urgent or strong or official:
                it=dict(it); it["_cat"]=cat
                it["_pri"]= 0 if urgent else (1 if strong else 2)
                pool.append(it)
    pool.sort(key=lambda x:(x["_pri"], -(x.get("score") or 0)))
    sent=0
    for it in pool:
        f=_fp(it.get("head"))
        if f in seen: continue
        if sent>=3: break                       # سقف يمنع الإغراق
        g=it.get("grade","")
        head = "🔴 عاجل" if it["_cat"]=="عاجل" else ("✅ خبرٌ صحيحُ الإسناد" if g=="صحيح" else "📌 خبرٌ قويُّ الإسناد")
        t=(f"{head}\n\n<b>{it.get('head','')}</b>\n\n"
           f"📡 {it.get('src','')}"+(f" · {it.get('via')}" if it.get('via') else "")+"\n"
           f"⚖️ الإسناد: {g} · {it.get('score','—')}/7")
        if it.get("at"):
            try: t+=f"\n🕐 {datetime.fromisoformat(it['at']).strftime('%H:%M')}"
            except Exception: pass
        if it.get("link"): t+=f"\n\n<a href=\"{it['link']}\">المصدر ↗</a>"
        t+=f" · <a href=\"{SITE}\">سَنَد</a>"
        if tg_send(t): seen.add(f); sent+=1
    if sent:
        st["news"]=list(seen); _tg_save(st)
        print(f"📣 بُثّ {sent} خبرًا حصريًا")

def broadcast_official():
    """يبثّ بياناتِ الجهاتِ الرسميّة والعسكريّة فورَ وصولها — CENTCOM ووزاراتِ الدفاع."""
    try: o=json.load(open(f"{OUT}/official.json"))
    except Exception: return
    st=_tg_state(); seen=set(st.get("official",[]))
    MIL=("CENTCOM","المركزية","الدفاع","الأركان","القوات المسلحة","الجيش",
         "الداخلية","الدفاع المدني","خلية الإعلام","البنتاغون")
    sent=0
    for x in (o.get("src") or []):
        ent=str(x.get("e","")); post=str(x.get("p",""))
        if not post: continue
        if not any(m in ent for m in MIL): continue     # عسكريٌّ أو أمنيٌّ فقط
        if _stmt_stale(x.get("t")): continue             # لا نبثُّ بيانًا قديمًا كأنّه فوريّ
        f=_fp(ent+post)
        if f in seen: continue
        if sent>=4: break
        t=(f"🎖️ <b>بيانٌ رسميّ — فورَ صدوره</b>\n\n"
           f"{x.get('f','')} <b>{ent}</b>"+(f" {x.get('h')}" if x.get("h") else "")+"\n\n"
           f"{post}\n")
        if x.get("t"): t+=f"\n🕐 {x['t']}"
        if x.get("u"): t+=f"\n<a href=\"{x['u']}\">البيان ↗</a>"
        t+=f" · <a href=\"{SITE}\">سَنَد</a>"
        if tg_send(t): seen.add(f); sent+=1
    if sent:
        st["official"]=list(seen); _tg_save(st)
        print(f"📣 بُثّ {sent} بيانًا رسميًا")

def broadcast_alerts():
    """يبثّ التحذيراتِ الرسميّةَ الجديدةَ فقط — بلا تكرار."""
    try: al=json.load(open(ALERTS))
    except Exception: return
    st=_tg_state(); seen=set(st.get("alerts",[]))
    sent=0
    for x in (al.get("list") or []):
        f=_fp(str(x.get("body",""))+str(x.get("txt","")))
        if f in seen: continue
        if sent>=2: break
        rumor="شائعة" in (x.get("kind") or "")
        t=(f"{'🟡 تنبيهٌ من الشائعات' if rumor else '🔴 تحذيرٌ رسميّ'}\n\n"
           f"<b>{x.get('body','')}</b>\n\n{x.get('txt','')}\n")
        if x.get("act"): t+=f"\n<b>افعل:</b> {x['act']}\n"
        if x.get("u"):   t+=f"\n<a href=\"{x['u']}\">البيان ↗</a>"
        t+=f"\n\n<a href=\"{SITE}\">سَنَد</a>"
        if tg_send(t): seen.add(f); sent+=1
    if sent:
        st["alerts"]=list(seen); _tg_save(st)
        print(f"📣 بُثّ {sent} تحذيرًا جديدًا")

def bundle():
    """يدمج كل ملفات العرض في ملف واحد — يقضي على خنق الطلبات المتوازية."""
    # 🛡️ حارسٌ أحاديّ الاتجاه لنشرة اليوم: لا نُعيدها إلى تاريخٍ أقدم من المنشور.
    # سبب العطل: تشغيلٌ يحمل latest.json قديمة كان يدهس النشرة الأحدث عند النشر.
    try:
        _lp=f"{OUT}/latest.json"
        _loc=json.load(open(_lp)) if os.path.exists(_lp) else {}
        _pub=json.load(urllib.request.urlopen(
            "https://raw.githubusercontent.com/Soldiom/sanad-data/main/daily/latest.json",timeout=25))
        if str(_pub.get("date","")) > str(_loc.get("date","")):
            json.dump(_pub,open(_lp,"w"),ensure_ascii=False,indent=1)
            print(f"🛡️ نشرةُ اليوم: أُبقيت الأحدث ({_pub.get('date')}) بدل الأقدم ({_loc.get('date')})")
    except Exception as _e: print(f"guard_latest: {str(_e)[:80]}")
    keys=["news","intel","official","forecast","analyst","dua","verify",
          "alerts","corrections","latest","agents","cost","evolution","council","gpu","rumors","column","tension"]
    b={"built":datetime.now(timezone.utc).isoformat(timespec="minutes")}
    for k in keys:
        try: b[k]=json.load(open(f"{OUT}/{k}.json"))
        except Exception: pass
    try: b["archive_index"]=json.load(open(f"{OUT}/archive/index.json"))
    except Exception: pass
    json.dump(b,open(f"{OUT}/bundle.json","w"),ensure_ascii=False,separators=(",",":"))
    sz=os.path.getsize(f"{OUT}/bundle.json")
    print(f"📦 الحزمة: {len(b)-1} قسمًا · {sz//1024} ك.ب في طلبٍ واحد")

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
    ran=sum(1 for a in out if a["status"]=="ok")
    json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "healthy":ok,"total":len(out),"ran":ran,"slot":SLOT,"agents":out},
        open(AGENTS_F,"w"),ensure_ascii=False,indent=1)
    print(f"🤖 طبقة الوكلاء: {ran} عمل الآن · {ok}/{len(out)} سليم · النوبة {SLOT}")

def bill(d,who):
    """يسجّل التكلفة الفعلية من رد الـAPI."""
    day=datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        usd=d.get("usage",{}).get("cost_in_usd_ticks",0)/1e10
        if not usd: return 0
        try: c=json.load(open(f"{OUT}/cost.json"))
        except Exception: c={"day":day,"usd":0,"calls":0,"by":{}}
        if c.get("day")!=day: c={"day":day,"usd":0,"calls":0,"by":{}}
        c["usd"]=round(c.get("usd",0)+usd,4); c["calls"]=c.get("calls",0)+1
        c["by"][who]=round(c["by"].get(who,0)+usd,4)
        c["month_est"]=round(c["usd"]*30,2)
        c["budget"]=float(os.environ.get("DAILY_BUDGET_USD","0.80"))
        json.dump(c,open(f"{OUT}/cost.json","w"),ensure_ascii=False,indent=1)
        print(f"💵 {who}: ${usd:.4f} · اليوم ${c['usd']:.3f} ({c['calls']} نداء) · الشهر ~${c['month_est']}")
        return usd
    except Exception as e:
        print(f"تسجيل التكلفة تعذّر: {str(e)[:60]}"); return 0

# ═══ سقفُ الإنفاقِ اليوميّ الصارم: الضمانةُ الرياضيّةُ للفاتورة ═══
# الخلاصةُ الإخباريّةُ نفسُها مجّانية (RSS + الوكيل الحرّ)؛ كلُّ النداءاتِ المدفوعةِ
# لأقسامٍ مساندة — فإذا بلغَ إنفاقُ اليومِ السقفَ تتوقّفُ حتى الغد وتستمرُّ المجّانية.
DAILY_BUDGET=float(os.environ.get("DAILY_BUDGET_USD","0.80"))
def spent_today():
    try:
        c=json.load(open(f"{OUT}/cost.json"))
        return c.get("usd",0) if c.get("day")==datetime.now(timezone.utc).strftime("%Y-%m-%d") else 0.0
    except Exception: return 0.0
def over_budget(who):
    s=spent_today()
    if s>=DAILY_BUDGET:
        print(f"💰 {who}: بلغ سقفَ الإنفاق اليوميّ (${s:.2f}/${DAILY_BUDGET:.2f}) — يتوقّف حتى الغد")
        return True
    return False

OFFICIAL_HANDLES=set()
try:
    OFFICIAL_HANDLES={x.get("h","").lower().lstrip("@") for x in json.load(open(f"{OUT}/official.json")).get("src",[])}
except Exception: pass


# ═══ الجدولة: توزيع الوكلاء الثقيلة على الجولات بالتناوب ═══
_H=datetime.now(timezone.utc).hour
SLOT=(_H//3)%2          # 0 أو 1 — يتبدّل كل ٣ ساعات
def due(aid, age, hard):
    """يقرر التشغيل: نوبة الوكيل، أو تجاوز المهلة القصوى."""
    if aid=="rasid":
        if os.environ.get("FORCE_INTEL"): return True, ""
        return (age>=11), (f"يعمل بعد ~{max(0,round(11-age,1))}س" if age<11 else "")
    turn = {"manba":1,"mutabiq":1}.get(aid,None)
    if os.environ.get("FORCE_"+aid.upper()): return True, ""
    if age>=hard: return True, "تجاوز المهلة"
    if turn is not None and SLOT!=turn:
        return False, f"نوبته الجولة القادمة (~{3-(_H%3)}س)"
    # مُهلةٌ أدنى لكلّ وكيل — المَنبعُ مرّتين يوميًّا يكفي: بياناتُه بتواريخَ مطلقةٍ
    # لا تتعفّن، والوكيلُ الحرُّ يغطّي أخبارَ الجهاتِ الرسميّةِ مجّانًا بين التشغيلين.
    mn={"manba":12}.get(aid,3)
    return (age>=mn), (f"يعمل بعد ~{max(0,round(mn-age,1))}س" if age<mn else "")

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

def witness(desc, own_src=""):
    """«الشاهدُ الثاني» مجّانًا: وصفُ خبرِ غوغل يسردُ المنافذَ الأخرى الراويةَ لنفس
    الخبر — نعدُّها ونسمّيها، فيصيرُ التقاطعُ مرئيًّا للقارئ (w=عدد المنافذ)."""
    if not desc or "<li>" not in desc: return 0,[]
    names=[clean(x) for x in re.findall(r'<font[^>]*>([^<]+)</font>', desc)]
    names=[n for n in dict.fromkeys(names) if n and n!=clean(own_src)][:5]
    w=desc.count("<li>")
    return (w if w>1 else 0), names

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
            _en_nm,_en_who = en_meta(url)
            is_en = bool(_en_nm)
            _dn,_dwho,_dg = direct_meta(url)
            if _dn: head=title; src_=_dn      # مصدرٌ مباشرٌ معروف — لا نقصُّ العنوان على «-»
            g=_dg if _dn else ("حسن" if (is_fa or is_en) else grade(src_ or clean(it.findtext("source",""))))
            key=head[:40]
            if g in ("صحيح","حسن") and len(head)>15 and key not in seen and not blocked(head):
                seen.add(key)
                _pd=clean(it.findtext("pubDate","")) or clean(it.findtext("{http://purl.org/dc/elements/1.1/}date",""))
                _iso=""
                if _pd:
                    for _f in ("%a, %d %b %Y %H:%M:%S %Z","%a, %d %b %Y %H:%M:%S %z","%Y-%m-%dT%H:%M:%S%z"):
                        try:
                            from email.utils import parsedate_to_datetime
                            _iso=parsedate_to_datetime(_pd).astimezone(timezone.utc).isoformat(timespec="minutes"); break
                        except Exception:
                            try: _iso=datetime.strptime(_pd,_f).astimezone(timezone.utc).isoformat(timespec="minutes"); break
                            except Exception: pass
                d={"head":head,"src":src_,"grade":g,"cat":label,"at":_iso,
                   "link":clean(it.findtext("link","")),"fa":is_fa}
                _w,_wsrc=witness(it.findtext("description",""),src_)
                if _w: d["w"]=_w; d["wsrc"]=_wsrc
                for _e in it.iter():
                    _mu=str(_e.get("url","")); _mt=str(_e.get("type",""))+str(_e.get("medium",""))
                    if (_e.tag=="enclosure" or _e.tag.endswith("}content")) and _mu.startswith("https://") \
                       and ("image" in _mt or re.search(r'\.(?:jpe?g|png|webp|avif)(?:$|[?.])',_mu,re.I)):
                        d["img"]=_mu; break
                if is_fa:
                    nm,who=fa_meta(url); d["src"]=nm; d["via"]=who
                elif is_en:
                    d["src"]=_en_nm; d["via"]=_en_who; d["en"]=True
                elif _dn:
                    d["via"]=_dwho
                items.append(d); n+=1
                if n>=6: break
    except Exception as e: print(f"feed {label}: {e}",file=sys.stderr)
print(f"جُمع {len(items)} خبرًا مُسندًا")

# ═══ الوكيلُ الحرّ: بياناتٌ من مصادرَ مجّانيّةٍ بلا مفاتيح ولا كلفة ═══
# استعلاماتٌ مُوجّهةٌ لجهاتٍ رسميّةٍ عبر «أخبار غوغل RSS» (مجّانيٌّ بلا مفتاح). لا تلفيق:
# روابطُ مقالاتٍ حقيقيّةٍ من منافذَ معتبَرة (يُبقيها فلترُ الدرجات) تنقلُ بياناتِ المصدرِ الرسميّ.
import urllib.parse as _up
FREE_WIRE=[
 ("عالم", 'CENTCOM OR "القيادة المركزية الأمريكية" إيران'),
 ("عالم", '"الوكالة الدولية للطاقة الذرية" OR IAEA إيران نووي'),
 ("الخليج", 'الكويت (بيان رسمي OR طوارئ OR إنذار OR مجال جوي)'),
 ("الخليج", '(السعودية OR الإمارات OR قطر OR البحرين) وزارة الدفاع بيان'),
 ("عالم", 'الأمم المتحدة OR "مجلس الأمن" إيران الخليج'),
]
@agent("hurr")
def wire_hurr():
    """يجلبُ أخبارَ الجهاتِ الرسميّةِ من «أخبار غوغل RSS» — بلا مفتاحٍ ولا كلفة، وبإسنادِ المنافذِ نفسِه."""
    added=0
    for cat,q in FREE_WIRE:
        try:
            url="https://news.google.com/rss/search?q="+_up.quote(q)+"&hl=ar&gl=KW&ceid=KW:ar"
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            root=ET.fromstring(urllib.request.urlopen(req,timeout=30).read())
            n=0
            for it in root.iter("item"):
                title=clean(it.findtext("title",""))
                src_=title.rsplit(" - ",1)[-1] if " - " in title else ""
                head=title.rsplit(" - ",1)[0] if " - " in title else title
                g=grade(src_ or clean(it.findtext("source","")))     # الإسنادُ بدرجةِ المنفذِ نفسِها
                key=head[:40]
                if g in ("صحيح","حسن") and len(head)>15 and key not in seen and not blocked(head):
                    seen.add(key)
                    _iso=""; _pd=clean(it.findtext("pubDate",""))
                    if _pd:
                        try:
                            from email.utils import parsedate_to_datetime
                            _iso=parsedate_to_datetime(_pd).astimezone(timezone.utc).isoformat(timespec="minutes")
                        except Exception: pass
                    _d={"head":head,"src":src_,"grade":g,"cat":cat,"at":_iso,
                        "link":clean(it.findtext("link","")),"fa":False,"free":True}
                    _w,_wsrc=witness(it.findtext("description",""),src_)
                    if _w: _d["w"]=_w; _d["wsrc"]=_wsrc
                    items.append(_d)
                    n+=1; added+=1
                    if n>=4: break
        except Exception as e: print(f"الحرّ [{cat}]: {str(e)[:50]}",file=sys.stderr)
    print(f"🆓 الوكيلُ الحرّ: +{added} خبرًا من مصادرَ مجّانيّةٍ بلا مفاتيح")
    return {"added":added,"why":f"+{added} خبرًا مجّانيًّا"}
wire_hurr()

GEM_MODEL=os.environ.get("GEMINI_MODEL","gemini-flash-latest")
def gemini_post(body, timeout=60):
    """نداءُ Gemini متحمِّلًا تغيُّرَ الحقول: النماذجُ الأحدثُ ترفض thinkingBudget
    بـ400 (تعطّلت به الترجمةُ والعمود) — عند 400 نعيدُ المحاولةَ دون thinkingConfig."""
    import urllib.error as _ue
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{GEM_MODEL}:generateContent?key={GEMINI_KEY}"
    try:
        req=urllib.request.Request(url,data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"})
        return json.load(urllib.request.urlopen(req,timeout=timeout))
    except _ue.HTTPError as e:
        gc=body.get("generationConfig",{})
        if e.code!=400 or "thinkingConfig" not in gc: raise
        # بلا thinkingConfig يفكّرُ النموذجُ الأحدثُ افتراضيًّا فيأكلُ التفكيرُ ميزانيةَ
        # الإخراج ويصلُ الردُّ مبتورًا — نرفعُ السقفَ ليتّسعَ للتفكيرِ والجوابِ معًا.
        g2={k:v for k,v in gc.items() if k!="thinkingConfig"}
        g2["maxOutputTokens"]=max(int(gc.get("maxOutputTokens",1500))*4, 8000)
        b2=dict(body); b2["generationConfig"]=g2
        req=urllib.request.Request(url,data=json.dumps(b2).encode(),
            headers={"Content-Type":"application/json"})
        return json.load(urllib.request.urlopen(req,timeout=timeout))

def gemini_json(prompt, max_tok=1500, temp=0.2):
    body={"contents":[{"parts":[{"text":prompt}]}],
        "generationConfig":{"maxOutputTokens":max_tok,"temperature":temp,
            "thinkingConfig":{"thinkingBudget":0},"responseMimeType":"application/json"}}
    d=gemini_post(body, timeout=90)
    parts=((d.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    txt="".join(p.get("text","") for p in parts if isinstance(p,dict)).strip()
    txt=txt.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(txt)

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
            body={"model":os.environ.get("GROK_MODEL","grok-4.3"),"input":[{"role":"user","content":
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

# ═══ ترجمة العناوين التقنية الإنجليزية ═══
en_items=[i for i in items if i.get("en")]
if en_items and GEMINI_KEY:
    try:
        lst="\n".join(f"{n}| {i['head']}" for n,i in enumerate(en_items))
        out=gemini_json("ترجم عناوين أخبار الذكاء الاصطناعي هذه إلى العربية التقنية الدقيقة. "
            "احتفظ بأسماء النماذج والشركات كما هي بالإنجليزية داخل النص العربي "
            "(مثال: أطلقت Meta نموذج Llama 4 مفتوح المصدر). "
            "ترجمة أمينة بلا تهويل ولا اختصار.\n"
            'أخرج JSON فقط: [{"n":الرقم,"h":"العنوان العربي"}]\n'+lst)
        for o in out:
            en_items[o["n"]]["head"]=o["h"]
        print(f"🌐 تُرجم {len(out)} عنوانًا تقنيًا")
        mark("turjuman","ok",f"{len(out)} تقني")
    except Exception as e:
        print(f"ترجمة التقنية فشلت: {str(e)[:70]}")
        items=[i for i in items if not i.get("en")]

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

# ═══ صورُ المقالات مجّانًا: og:image من صفحةِ المقال نفسِها — للقصّة الرئيسيّة والشبكة ═══
IMGCACHE=f"{OUT}/imgcache.json"
def _gnews_b64(u):
    """الصيغةُ القديمةُ لروابط أخبار غوغل تحملُ رابطَ الناشرِ خامًا داخل base64 —
    فكٌّ رخيصٌ بلا شبكة؛ الصيغةُ الأحدث (AU_yqL…) لا تحمله فنكتفي بصورةِ غوغل."""
    try:
        seg=u.split("/articles/")[1].split("?")[0]
        import base64 as _b64
        raw=_b64.urlsafe_b64decode(seg+"="*(-len(seg)%4))
        m=re.search(rb'https?://[\x20-\x7e]+?(?=[\x00-\x1f\xd2\xd8]|$)',raw)
        if m:
            cand=m.group(0).decode("ascii","ignore").rstrip("\\'\"R")
            if cand.startswith("https://") and "google" not in cand.split("/")[2]:
                return cand
    except Exception: pass
    return ""


def fetch_og_images(items, cap=24):
    """يجلبُ og:image لأوّل العناصر بلا كلفةٍ (urllib متوازٍ + كاشٌ بالرابط) —
    فشلُ أيّ جلبٍ صامتٌ: البطاقةُ بلا صورةٍ لها بديلُها في الواجهة."""
    try: cache=json.load(open(IMGCACHE))
    except Exception: cache={}
    _rx=re.compile(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',re.I)
    _rx2=re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)',re.I)
    def one(it):
        L=str(it.get("link",""))
        k=hashlib.md5(L.encode()).hexdigest()[:12]
        if "news.google.com" in L:
            # صفحةُ غوغل الوسيطة لا تحملُ صورةَ المقال (صورتُها ترويجيّةٌ عامّة) —
            # فكٌّ رخيصٌ للرابط القديم فقط، وإن نجح تابعنا كمقالٍ مباشر
            rk="r:"+k
            if rk not in cache: cache[rk]=_gnews_b64(L)
            if not cache[rk]: return
            it["link"]=cache[rk]; L=cache[rk]
            k=hashlib.md5(L.encode()).hexdigest()[:12]
        if k in cache:
            if cache[k]: it["img"]=cache[k]
            return
        try:
            req=urllib.request.Request(it["link"],headers={"User-Agent":"Mozilla/5.0"})
            html=urllib.request.urlopen(req,timeout=8).read(60000).decode("utf-8","ignore")
            m=_rx.search(html) or _rx2.search(html)
            u=(m.group(1) if m else "").strip()
            cache[k]=u if u.startswith("https://") else ""
            if cache[k]: it["img"]=cache[k]
        except Exception: cache[k]=""
    todo=[i for i in items if i.get("link","").startswith("http") and not i.get("img")][:cap]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex: list(ex.map(one,todo))
    try: json.dump(dict(list(cache.items())[-500:]),open(IMGCACHE,"w"))
    except Exception: pass
    n=sum(1 for i in items if i.get("img"))
    print(f"🖼️ الصور: {n} خبرًا بصورةِ مقالِه الأصليّ (مجّانًا)")
fetch_og_images(items)

# ═══ النسخةُ العالميّة: ترجمةُ العناوين إلى الإنجليزيّة (Gemini مجّانًا) ═══
# حقل «he» على كلِّ عنصر — الواجهةُ تعرضه في وضع EN وتعود للعربيّة عند غيابه.
def translate_heads_en(items, cap=60):
    todo=[(n,i) for n,i in enumerate(items[:cap]) if not i.get("he")]
    if not todo or not GEMINI_KEY: return 0
    lst="\n".join("%d| %s"%(n,i["head"]) for n,i in todo)
    try:
        out=gemini_json("Translate these Arabic news headlines to concise, professional English "
            "news-wire style. Faithful translation — no additions, no exaggeration, keep numbers "
            "and proper names accurate.\n"
            'Return JSON only: [{"n":number,"e":"English headline"}]\n'+lst, max_tok=4000)
        ok=0
        by={o.get("n"):o.get("e","") for o in out if isinstance(o,dict)}
        for n,i in todo:
            e=clean(str(by.get(n,"")))
            if len(e)>8: i["he"]=e; ok+=1
        print(f"🌍 النسخة العالميّة: تُرجم {ok}/{len(todo)} عنوانًا إلى الإنجليزيّة")
        return ok
    except Exception as e:
        print("الترجمة العالميّة تخطّت: "+str(e)[:60]); return 0
translate_heads_en(items)

cats={}
for i in items:
    cats.setdefault(i["cat"],[]).append({k:i[k] for k in ("head","src","grade","link","fa","at","en","img","w","wsrc","he") if k in i}
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
    # ⛔ مُعطَّل عمدًا. كانت هذه الدالة تولّد أرقامَ حربٍ (قتلى/جرحى/صواريخ/مسيّرات)
    # عبر نموذجٍ لغويّ وتنسبها لجهاتٍ رسميّة لم تُعلنها (mil_u=«لم يُعلن»)، ثم تُسجّل
    # اختلافَ كلّ تشغيلٍ عن سابقه في سجلّ التصحيحات كأنّه تصحيحٌ رسميّ. تلفيقٌ يخالف
    # صميمَ منهج سَنَد: لا رقمَ بلا إسناد، والصمتُ أولى من رقمٍ غير مُسنَد.
    # لا حصيلةَ حربٍ حتى تتوفّر أرقامٌ من بياناتٍ رسميّة حقيقيّة قابلةٍ للتحقّق.
    j={"war":"","since":"","toll":[],"brk":[],"disabled":1,
       "updated":datetime.now(timezone.utc).isoformat(timespec="minutes")}
    try: json.dump(j,open(INTEL,"w"),ensure_ascii=False,indent=1)
    except Exception: pass
    return j
    # ── ما يلي مُعطَّل (لا يُنفَّذ) ──
    old, _ = intel_fresh(99)
    try: _age=(datetime.now(timezone.utc)-datetime.fromisoformat((old or {}).get("updated","2000-01-01T00:00+00:00"))).total_seconds()/3600
    except Exception: _age=999
    go,why = due("rasid",_age,9)
    if not go and not os.environ.get("FORCE_INTEL"):
        print(f"⏱️ الرَّاصِد: {why}"); return {"skipped":1,"why":why,**(old or {})}
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
       "mis وdrn وitc: أعداد ما أُطلق تجاه كل بلد وما اعترضته دفاعاته. إن لم يتوفر رقم فاكتب «غير معلن».\n"
       "لكل رقم اذكر الجهة المعلِنة في src (مثل: وزارة الصحة الإيرانية، الدفاع المدني الكويتي، "
       "الأمم المتحدة) ورابطها في u وتاريخها في asof. إن كان الرقم تقديرًا صحفيًا لا إعلانًا رسميًا "
       "فاكتب في src: تقدير صحفي غير رسمي.\n"
       "٤ عناوين عاجلة كحد أقصى من حسابات موثقة خلال ٦ ساعات. أرقام موثقة فقط وإلا «غير مؤكد». "
       "لا تستخدم علامة تنصيص مزدوجة داخل النصوص. لا شيء خارج JSON.")
    body={"model":os.environ.get("GROK_MODEL_HEAVY","grok-4.3"),"input":[{"role":"user","content":P}],
        "tools":[{"type":"web_search"},{"type":"x_search"}],
        "max_output_tokens":4200,"max_tool_calls":8}
    try:
        req=urllib.request.Request("https://api.x.ai/v1/responses",data=json.dumps(body).encode(),
            headers={"Authorization":"Bearer "+GROK_KEY,"Content-Type":"application/json"})
        d=json.load(urllib.request.urlopen(req,timeout=400))
        txt="".join(c.get("text","") for o in d.get("output",[]) if o.get("type")=="message"
                    for c in o.get("content",[]))
        txt=txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        if not txt:
            print(f"Grok رد فارغ (status={d.get('status')} {d.get('incomplete_details')})"); return old
        j=json.loads(txt[txt.find("{"):txt.rfind("}")+1])

        def _numc(tl):
            return sum(1 for x in tl if str(x.get("d","")).replace(",","").replace("-","").isdigit())

        # ① دمج أرقام الذخائر السابقة إن غابت الآن
        try:
            pm={t.get("c"):t for t in (locals().get("ref") or old or {}).get("toll",[])}
            for t in j.get("toll",[]):
                p=pm.get(t.get("c")) or {}
                for k in ("mis","drn","itc","src","u","asof"):
                    cur=str(t.get(k,"")).strip()
                    if (not cur or cur in ("غير معلن","—","لا خسائر مؤكدة","غير مؤكد")) and p.get(k):
                        if str(p[k]).strip() not in ("غير معلن","—",""): t[k]=p[k]
                # الأرقام نفسها: لا تُستبدل بقيمة نصية إن كانت السابقة رقمًا
                for k in ("d","w"):
                    if not str(t.get(k,"")).replace(",","").isdigit() and str(p.get(k,"")).replace(",","").isdigit():
                        t[k]=p[k]
        except Exception: pass

        # ② حارس: لا تُستبدل حصيلة فيها أرقام بأخرى فارغة
        # مرجع الجودة: الأفضل بين المحلي والمنشور
        ref=old
        try:
            pub=json.load(urllib.request.urlopen(
                "https://raw.githubusercontent.com/Soldiom/sanad-data/main/daily/intel.json",timeout=25))
            if _numc(pub.get("toll",[])) > _numc((old or {}).get("toll",[])): ref=pub
        except Exception: pass
        new_n=_numc(j.get("toll",[])); ref_n=_numc((ref or {}).get("toll",[]))
        if ref and ref.get("toll") and new_n < max(3,ref_n*0.7):
            print(f"🛡️ الحصيلة الجديدة أضعف ({new_n} مقابل {ref_n}) — أُبقيت الأقوى")
            json.dump(ref,open(INTEL,"w"),ensure_ascii=False,indent=1)
            return ref

        # ③ سجل التصحيحات
        try:
            prevmap={t.get("c"):t for t in (old or {}).get("toll",[])}
            chg=[]
            for t in j.get("toll",[]):
                p=prevmap.get(t.get("c"))
                if not p: continue
                for k,lbl in (("d","قتلى"),("w","جرحى"),("mis","صواريخ"),("drn","مسيّرات")):
                    a,b_=str(p.get(k,"")).strip(),str(t.get(k,"")).strip()
                    if a and b_ and a!=b_ and a.replace(",","").isdigit() and b_.replace(",","").isdigit():
                        chg.append({"c":t["c"],"f":t.get("f",""),"field":lbl,"from":a,"to":b_,
                            "src":t.get("src",""),"at":datetime.now(timezone.utc).isoformat(timespec="minutes")})
            if chg:
                try: cl=json.load(open(f"{OUT}/corrections.json"))
                except Exception: cl={"log":[]}
                cl["log"]=(cl.get("log",[])+chg)[-40:]
                cl["updated"]=datetime.now(timezone.utc).isoformat(timespec="minutes")
                json.dump(cl,open(f"{OUT}/corrections.json","w"),ensure_ascii=False,indent=1)
                print(f"📋 سجل التصحيحات: {len(chg)} رقمًا تغيّر")
        except Exception: pass

        j["updated"]=datetime.now(timezone.utc).isoformat(timespec="minutes")
        json.dump(j,open(INTEL,"w"),ensure_ascii=False,indent=1)
        bill(d,"الرَّاصِد")
        print(f"🛰️ الرَّاصِد: {len(j.get('toll',[]))} دول · {len(j.get('brk',[]))} عاجل")
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
    # ١ الاتصال: مصدر أول بلا واسطة — الجهات الرسمية والوكالات الأم
    _t1 = any(t in src for t in TIER1)
    c["الاتصال"] = 2 if (it.get("official") or _t1) else (1 if it.get("link") else 0)
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
    if age<6 and not os.environ.get("FORCE_FORECAST"):
        print(f"⏱️ المُستقرِئ: يعمل بعد ~{max(0,round(6-age,1))}س")
        return {"skipped":1,"why":f"يعمل بعد ~{max(0,round(6-age,1))}س"}
    if not GROK_KEY: return
    if over_budget("المُستقرِئ"): return {"skipped":1,"why":"بلغ سقفَ الإنفاق اليوميّ"}

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
       '"signals":[{"q":"التصريح أو الواقعة","who":"القائل","w":"عالٍ|متوسط|منخفض","u":"رابط المصدر"}],'
       '"scenarios":[{"s":"السيناريو","p":نسبة_رقم,"why":"المبرر مع السابقة التاريخية","watch":"المؤشر المؤكد أو النافي"}],'
       '"review":[{"s":"السيناريو السابق","r":"وقع|جزئيًا|لم يقع","note":"بجملة"}],'
       '"caveat":"تحذير صريح بأن هذا استقراء احتمالي لا يقين"}\n'
       "نوّعْ قائلي الإشارات قدرَ الإمكان (أطرافٌ متمايزة لا قائلٌ واحدٌ مكرّر) كي تتّضحَ زوايا المشهد. "
       "واجعل القائلين جهاتٍ مسمّاةً محدّدة (شخصٌ أو مؤسّسة) لا عباراتٍ عامّة كـ«تقارير إعلامية متعددة». "
       "قاعدةُ إسنادٍ صارمة: كلُّ إشارةٍ تُنسَبُ لقائلها مع رابطٍ من مصدره. "
       "لا تُقدّمْ حدثًا عسكريًّا غير مؤكّد (ضربٌ، اعتراضٌ، قتلى، صافرة) منسوبًا لجهةٍ رسميّةٍ "
       "كأنّه واقعٌ مثبت؛ إمّا برابطٍ من مصدرِه أو صياغةً كاحتمالٍ لا كخبرٍ مؤكّد.\n"
       "٣ سيناريوهات كحد أقصى ومجموع نسبها ١٠٠. لا تستخدم علامة تنصيص مزدوجة داخل النصوص. "
       "لا تذكر أسماء نماذج أو شركات. لا شيء خارج JSON.")
    body={"model":os.environ.get("GROK_MODEL","grok-4.3"),"input":[{"role":"user","content":P}],
        "tools":[{"type":"web_search"},{"type":"x_search"}],
        "max_output_tokens":3000,"max_tool_calls":3}
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
    # حارسُ الإسناد للمؤشرات: ادّعاءُ حدثٍ عسكريٍّ صلبٍ منسوبًا لجهةٍ بلا مصدرٍ يُتحقَّق منه يُسقَط،
    # كي لا نُقدّم «ضربَ أهدافٍ في الكويت» على عهدةِ نموذجٍ لغويّ كأنّه خبرٌ مؤكّد.
    _sig=j.get("signals",[]) or []
    _kept=[s for s in _sig if not (any(w in str(s.get("q","")) for w in _HARD_EVENT) and not _ok_url(s.get("u")))]
    if len(_kept)!=len(_sig): print(f"🛡️ المُستقرِئ: أُسقط {len(_sig)-len(_kept)} مؤشرَ حدثٍ بلا مصدر")
    j["signals"]=_kept
    j["updated"]=datetime.now(timezone.utc).isoformat(timespec="minutes")
    json.dump(j,open(FCAST,"w"),ensure_ascii=False,indent=1)
    bill(d,"المُستقرِئ")
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
    go,why = due("manba",age,14)
    if not go and not os.environ.get("FORCE_OFFICIAL"):
        print(f"⏱️ المَنبع: {why}"); return {"skipped":1,"why":why}
    if not GROK_KEY: return
    if over_budget("المَنبع"): return {"skipped":1,"why":"بلغ سقفَ الإنفاق اليوميّ"}
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
    body={"model":os.environ.get("GROK_MODEL","grok-4.3"),"input":[{"role":"user","content":P}],
        "tools":[{"type":"x_search"},{"type":"web_search"}],
        "max_output_tokens":2600,"max_tool_calls":3}
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
        # ختمُ الالتقاطِ الآليّ (cap): لا يُخدَعُ بتاريخٍ نصّيٍّ متيبّس مثل «اليوم» الذي يبقى
        # «اليوم» بعد يوم. ونُحوّلُ «اليوم/أمس» إلى تاريخٍ مطلقٍ عند الالتقاطِ فلا يتعفّن العرض.
        _now=datetime.now(timezone.utc); _now_iso=_now.isoformat(timespec="minutes")
        _kd=(_now+timedelta(hours=3)).date()
        _ARM=["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]
        _abs=lambda d:f"{d.day} {_ARM[d.month-1]} {d.year}"
        keep={((x.get("h") or "").lower() or "w:"+str(x.get("e",""))):x
              for x in (old or {}).get("src",[])}
        for x in lst:
            x["cap"]=_now_iso
            _t=str(x.get("t",""))
            if "اليوم" in _t: x["t"]=_t.replace("اليوم",_abs(_kd))
            elif "أمس" in _t: x["t"]=_t.replace("أمس",_abs(_kd-timedelta(days=1)))
            keep[x["h"].lower()]=x
        # الطزاجة: يبقى بيانُ آخرِ ٣٠ ساعة (بالختمِ الآليّ)، أو ما تاريخُه اليومَ/أمسِ إن لم
        # يكن له ختمٌ بعد — فلا يُفرَّغُ القسمُ عند الانتقال، ولا يبقى بيانٌ متعفّن. والأحدثُ أوّلًا.
        def _fresh_cap(x):
            c=x.get("cap")
            if c:
                try: return (_now-datetime.fromisoformat(c)).total_seconds()<=30*3600
                except Exception: pass
            return not _stmt_old_days(x.get("t"),1)   # بلا ختم: يُبقى إن كان تاريخُه اليومَ أو أمس
        merged=sorted([x for x in keep.values() if _fresh_cap(x)],
                      key=lambda x:x.get("cap",""),reverse=True)[:14]
        json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),"src":merged},
            open(OFFI,"w"),ensure_ascii=False,indent=1)
        bill(d,"المَنبع")
        print("📡 المَنبع: +%d جهة (المجموع %d)"%(len(lst),len(merged)))
    except Exception as e:
        print("المَنبع تخطّى: "+str(e)[:90])

manba()

# ═══ سلكُ المَنبع الحرّ: يُبقي «من المَنبع» محدَّثًا كلَّ دورةٍ بلا كلفة ═══
# بين تشغيلَي المَنبع المدفوعَين (كلّ ١٢ ساعة) نجلبُ آخرَ ما نشرته وكالاتُ الأنباء
# الرسميّةُ نفسُها عبر «أخبار غوغل RSS» — عناوينُ حقيقيّةٌ من موقع الوكالة الرسميّ،
# لا تأليفَ ولا مفتاح. لا يمسُّ ختمَ updated (مدارَ نوبةِ المَنبع) بل يضيفُ wired.
_WIRE_AG=[("الكويت","🇰🇼","وكالة الأنباء الكويتية (كونا)","site:kuna.net.kw"),
          ("السعودية","🇸🇦","وكالة الأنباء السعودية (واس)","site:spa.gov.sa"),
          ("الإمارات","🇦🇪","وكالة أنباء الإمارات (وام)","site:wam.ae"),
          ("قطر","🇶🇦","وكالة الأنباء القطرية (قنا)","site:qna.org.qa"),
          ("البحرين","🇧🇭","وكالة أنباء البحرين (بنا)","site:bna.bh")]

def _tok_sim(a,b):
    A=set(re.findall(r"[؀-ۿ]{3,}",str(a or ""))); B=set(re.findall(r"[؀-ۿ]{3,}",str(b or "")))
    return len(A&B)/max(1,min(len(A) or 1,len(B) or 1))

def manba_wire():
    from email.utils import parsedate_to_datetime
    try: j=json.load(open(OFFI))
    except Exception: j={"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),"src":[]}
    now=datetime.now(timezone.utc); now_iso=now.isoformat(timespec="minutes")
    _ARM=["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]
    keep={((x.get("h") or "").lower() or "w:"+str(x.get("e",""))):x for x in j.get("src",[])}
    added=0
    for c,f,e,q in _WIRE_AG:
        try:
            url="https://news.google.com/rss/search?q="+_up.quote(q)+"&hl=ar&gl=KW&ceid=KW:ar"
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            root=ET.fromstring(urllib.request.urlopen(req,timeout=25).read())
            best=None
            for it in root.iter("item"):
                title=clean(it.findtext("title","")); head=title.rsplit(" - ",1)[0]
                head=re.sub(r"^(?:Kuna|KUNA|كونا|واس|وام|قنا|بنا|عام|سياسي|اقتصادي|رياضي|ثقافي|أخبار)\s*[/:：\-]\s*","",head).strip()
                try: dt=parsedate_to_datetime(clean(it.findtext("pubDate",""))).astimezone(timezone.utc)
                except Exception: continue
                if (now-dt).total_seconds()>36*3600 or len(head)<15 or blocked(head): continue
                if best is None or dt>best[0]: best=(dt,head,clean(it.findtext("link","")))
            if not best: continue
            dt,head,link=best
            prev=keep.get("w:"+e)
            if prev and prev.get("p")==head: continue          # لا جديدَ لدى الجهة
            # لا نُكرّرُ بيانًا جلبه المَنبعُ المدفوعُ نفسُه لنفس المضمون
            if any(_tok_sim(head,x.get("p",""))>0.6 for x in keep.values()): continue
            kd=(dt+timedelta(hours=3))                         # عرضُ التاريخ بيوم الكويت
            keep["w:"+e]={"c":c,"f":f,"e":e,"h":"","p":head,
                "t":f"{kd.day} {_ARM[kd.month-1]} {kd.year}","u":link,"cap":now_iso,"wire":True}
            added+=1
        except Exception: continue
    def _fresh(x):
        try: return (now-datetime.fromisoformat(x.get("cap",""))).total_seconds()<=30*3600
        except Exception: return not _stmt_old_days(x.get("t"),1)
    merged=sorted([x for x in keep.values() if _fresh(x)],
                  key=lambda x:x.get("cap",""),reverse=True)[:14]
    if added or merged!=j.get("src"):
        json.dump({"updated":j.get("updated") or now_iso,"wired":now_iso,"src":merged},
            open(OFFI,"w"),ensure_ascii=False,indent=1)
    print(f"🧵 سلكُ المَنبع الحرّ: +{added} وكالة (المجموع {len(merged)})")

try: manba_wire()
except Exception as e: print("سلكُ المَنبع تخطّى: "+str(e)[:80])

# ═══ المُطابِق: يقابل أرقام الحصيلة بمصدر مستقل ═══
@agent("mutabiq")
def mutabiq():
    """يتحقق من أرقام الحصيلة عبر بحث مستقل ويصنّفها: مطابق / متباين / غير موثّق."""
    try: t=json.load(open(INTEL))
    except Exception: return
    # توفير: الحصيلة معطّلة (لا أرقام) — فلا داعيَ لإنفاقِ نداءِ Grok على مقابلةِ لا شيء.
    if not (t.get("toll") or []):
        return {"skipped":1,"why":"الحصيلةُ معطّلة — لا أرقامَ تُطابَق"}
    try:
        v=json.load(open(f"{OUT}/verify.json"))
        if v.get("src_updated")==t.get("updated"):
            print("⏱️ المُطابِق: لا أرقام جديدة تحتاج مقابلة")
            return {"skipped":1,"why":"لا أرقام جديدة"}
    except Exception: pass
    if not GROK_KEY: return
    if over_budget("المُطابِق"): return {"skipped":1,"why":"بلغ سقفَ الإنفاق اليوميّ"}
    rows="\n".join("- %s: قتلى %s، جرحى %s (المُعلن: %s)"%(x.get("c"),x.get("d"),x.get("w"),x.get("src","غير مذكور"))
                    for x in t.get("toll",[]))
    P=("تحقّق من هذه الأرقام عبر مصادر مستقلة (وكالات دولية، أمم متحدة، جهات رسمية) "
       "وقُل لكلٍّ منها هل تطابق ما هو منشور أم تتباين.\n"+rows+"\n\n"
       'أخرج JSON فقط: [{"c":"البلد","r":"مطابق|متباين|غير موثّق","alt":"الرقم البديل إن وُجد",'
       '"by":"الجهة المستقلة","note":"سطر واحد"}]\n'
       "كن صارمًا: إن لم تجد مصدرًا مستقلًا فاكتب غير موثّق. "
       "لا تستخدم علامة تنصيص مزدوجة داخل النصوص. لا شيء خارج JSON.")
    try:
        body={"model":os.environ.get("GROK_MODEL","grok-4.3"),"input":[{"role":"user","content":P}],
            "tools":[{"type":"web_search"}],"max_output_tokens":2000,"max_tool_calls":4}
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
        bill(d,"المُطابِق")
        print("🔍 المُطابِق: %d/%d رقمًا مطابقًا لمصدر مستقل"%(ok,len(lst)))
    except Exception as e:
        print("المُطابِق تخطّى: "+str(e)[:80])

mutabiq()

# ═══ التحذيرات الرسمية: ما يحتاجه المواطن الآن ═══
ALERTS=f"{OUT}/alerts.json"

def _vague_when(s):
    """تاريخٌ غامض: اسمُ شهرٍ عربيٍّ بلا يومٍ محدَّد («يوليو 2026») — علامةُ توجيهٍ
    قديمٍ قائمٍ يُعادُ بيعُه كأنّه اليوم، فلا يُقبَل في قسمٍ سياديّ."""
    s=str(s or "")
    if not any(m in s for m in _AR_MON): return False
    return not any(_AR_MON.get(m.group(2)) for m in re.finditer(r"(\d{1,2})\s+([^\s0-9]+)",s))

def _alert_stale(x, now=None):
    """يُسقِطُ التحذيرَ غيرَ الحديث: تاريخُه الصريحُ أقدمُ من يومين، أو تاريخُه غامضٌ
    شهريّ، أو ختمُ التقاطِه (cap) أقدمُ من ٤٨ ساعة."""
    w=x.get("when")
    if _vague_when(w) or _stmt_old_days(w,2): return True
    try:
        now=now or datetime.now(timezone.utc)
        if (now-datetime.fromisoformat(x["cap"])).total_seconds()>48*3600: return True
    except Exception: pass
    return False

@agent("munabbih")
def munabbih():
    """يجمع التحذيرات والتوجيهات الرسمية العملية + تنبيهات الجهات من الشائعات."""
    try:
        old=json.load(open(ALERTS))
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(old["updated"])).total_seconds()/3600
    except Exception: old,age=None,999
    if age<8 and not os.environ.get("FORCE_ALERTS"):
        print(f"⏱️ المُنبِّه: يعمل بعد ~{max(0,round(8-age,1))}س")
        return {"skipped":1,"why":f"يعمل بعد ~{max(0,round(8-age,1))}س"}
    if not GROK_KEY: return
    if over_budget("المُنبِّه"): return {"skipped":1,"why":"بلغ سقفَ الإنفاق اليوميّ"}
    P=("ابحث عن آخر التحذيرات والتوجيهات الرسمية الصادرة عن جهات الكويت والخليج بشأن الأزمة "
       "خلال ٢٤ ساعة فقط: الداخلية، الدفاع، الإطفاء، الصحة، الكهرباء والماء، الطيران المدني، الدفاع المدني.\n"
       "ادرج نوعين:\n"
       "أ) تحذير أو توجيه عملي للمواطنين (إخلاء، ملاجئ، مجال جوي، مياه، كهرباء، طوارئ).\n"
       "ب) تنبيه رسمي من تداول أخبار غير موثوقة أو شائعات أو حسابات مجهولة.\n"
       'أخرج JSON فقط: [{"kind":"تحذير|تنبيه من شائعة","body":"الجهة",'
       '"txt":"نص التوجيه بإيجاز","act":"ما يفعله المواطن بجملة","u":"رابط",'
       '"when":"تاريخ الصدور المحدد: يوم شهر سنة وساعة إن عُرفت، مثل 26 يوليو 2026 14:00"}]\n'
       "٦ عناصر كحد أقصى من جهات رسمية فقط. لا تُدرِجْ توجيهًا قائمًا منذ أيامٍ أو أسابيع "
       "وإن ظلّ ساريًا — الأحدثَ فقط، وما جهلتَ تاريخَ صدورِه المحدَّد فلا تُدرِجْه أصلًا. "
       "لا تنصيص مزدوج داخل النصوص. لا شيء خارج JSON.")
    # توفير: النموذج الأخفّ (grok-4.3) وبحثٌ أقلّ يكفيان لالتقاطِ التحذيراتِ الرسميّة —
    # كان «المُنبِّه» ٦٤٪ من الإنفاق على النموذجِ الثقيل. الجودةُ يحرسُها إسقاطُ التحذيرِ بلا مصدر.
    body={"model":os.environ.get("GROK_MODEL","grok-4.3"),"input":[{"role":"user","content":P}],
        "tools":[{"type":"x_search"},{"type":"web_search"}],
        "max_output_tokens":2000,"max_tool_calls":4}
    try:
        req=urllib.request.Request("https://api.x.ai/v1/responses",data=json.dumps(body).encode(),
            headers={"Authorization":"Bearer "+GROK_KEY,"Content-Type":"application/json"})
        d=json.load(urllib.request.urlopen(req,timeout=420))
        txt="".join(c.get("text","") for o in d.get("output",[]) if o.get("type")=="message"
                    for c in o.get("content",[]))
        txt=txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        lst=json.loads(txt[txt.find("["):txt.rfind("]")+1])
        lst=[x for x in lst if x.get("body") and x.get("txt")]
        # حارسُ الإسناد: تحذيرٌ رسميٌّ (إخلاء/صافرة/طوارئ) بلا رابطٍ يُتحقَّق منه لا يُنشَر —
        # لا نُطلقُ إنذارًا باسمِ جهةٍ سياديّةٍ على عهدةِ نموذجٍ لغويّ. تنبيهُ الشائعاتِ إرشاديٌّ فيبقى.
        _before=len(lst)
        lst=[x for x in lst if x.get("kind")!="تحذير" or _ok_url(x.get("u"))][:6]
        if _before!=len(lst): print(f"🛡️ المُنبِّه: أُسقط {_before-len(lst)} تحذيرًا بلا مصدرٍ موثّق")
        # 🛡️ حارسُ الطزاجة: توجيهٌ بتاريخٍ غامضٍ شهريٍّ أو أقدمَ من يومين لا يُنشَر —
        # ختمُ الملفِّ طازجٌ لكن لا نسمحُ للمضمونِ القديمِ أن يتخفّى وراءه.
        _now_iso=datetime.now(timezone.utc).isoformat(timespec="minutes")
        for x in lst: x["cap"]=_now_iso
        _b2=len(lst); lst=[x for x in lst if not _alert_stale(x)]
        if _b2!=len(lst): print(f"🛡️ المُنبِّه: أُسقط {_b2-len(lst)} توجيهًا قديمًا أو غامضَ التاريخ")
        if not lst: raise ValueError("فارغة")
        bill(d,"المُنبِّه")
        json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),"list":lst},
            open(ALERTS,"w"),ensure_ascii=False,indent=1)
        w=sum(1 for x in lst if x.get("kind")=="تحذير")
        print(f"⚠️ المُنبِّه: {w} تحذيرًا · {len(lst)-w} تنبيهًا من الشائعات")
    except Exception as e:
        print("المُنبِّه تخطّى: "+str(e)[:90])

munabbih()

# ═══ سلكُ التحذيرات الحرّ: «تحذيراتٌ رسمية» حديثةٌ كلَّ دورةٍ بلا كلفة ═══
# بين نوباتِ المُنبِّه المدفوعةِ (كلّ ٨ ساعات) يجلبُ عناوينَ تحذيراتِ الدفاعِ المدنيّ
# والداخليّةِ والطيرانِ المدنيِّ من «أخبار غوغل RSS» — من منافذَ بدرجةِ «صحيح/حسن»
# فقط، وبتاريخِ نشرٍ خلال ٤٨ ساعة — ويُطهِّرُ الملفَّ من القديمِ كلَّ دورةٍ أيضًا.
_ALERT_WIRE_Q=[
 '"الدفاع المدني" OR "وزارة الداخلية" (تحذير OR تنبيه OR إخلاء OR صافرات OR طوارئ) الكويت',
 '(الكويت OR السعودية OR البحرين) ("الدفاع المدني" OR "الطيران المدني") (تعليق OR تحذير OR إغلاق OR استئناف)',
]
def alerts_wire():
    from email.utils import parsedate_to_datetime
    try: j=json.load(open(ALERTS))
    except Exception: j=None
    now=datetime.now(timezone.utc); now_iso=now.isoformat(timespec="minutes")
    _ARM=["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]
    # بصمةٌ محليّة (_rid تُعرَّف لاحقًا في قسمِ الشائعات — السكربتُ تسلسليّ)
    _h=lambda c: hashlib.md5(re.sub(r"\s+","",str(c or "")).encode("utf-8")).hexdigest()[:10]
    cur=(j or {}).get("list",[])
    for x in cur: x.setdefault("cap",now_iso)          # ختمُ التقاطٍ لعناصرِ المُنبِّه عند أوّل مرور
    keep={_h(x.get("txt","")):x for x in cur}
    added=0
    for q in _ALERT_WIRE_Q:
        try:
            url="https://news.google.com/rss/search?q="+_up.quote(q)+"&hl=ar&gl=KW&ceid=KW:ar"
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            root=ET.fromstring(urllib.request.urlopen(req,timeout=25).read())
            n=0
            for it in root.iter("item"):
                title=clean(it.findtext("title","")); head=title.rsplit(" - ",1)[0]
                src_=title.rsplit(" - ",1)[-1] if " - " in title else ""
                if grade(src_) not in ("صحيح","حسن"): continue   # منافذُ معتبَرةٌ فقط في قسمٍ سياديّ
                try: dt=parsedate_to_datetime(clean(it.findtext("pubDate",""))).astimezone(timezone.utc)
                except Exception: continue
                if (now-dt).total_seconds()>48*3600 or len(head)<20 or blocked(head): continue
                rid=_h(head)
                if rid in keep: continue
                if any(_tok_sim(head,x.get("txt",""))>0.6 for x in keep.values()): continue
                kd=dt+timedelta(hours=3)
                keep[rid]={"kind":"تحذير","body":src_,"txt":head,"u":clean(it.findtext("link","")),
                    "when":f"{kd.day} {_ARM[kd.month-1]} {kd.year}","cap":now_iso,"wire":True}
                added+=1; n+=1
                if n>=3: break
        except Exception: continue
    merged=sorted([x for x in keep.values() if not _alert_stale(x,now)],
                  key=lambda x:x.get("cap",""),reverse=True)[:8]
    purged=len(keep)-len(merged)
    if added or purged or j is None or merged!=cur:
        json.dump({"updated":(j or {}).get("updated") or now_iso,"wired":now_iso,"list":merged},
            open(ALERTS,"w"),ensure_ascii=False,indent=1)
    print(f"🧵 سلكُ التحذيرات الحرّ: +{added} · طُهّر {purged} قديمًا (المجموع {len(merged)})")

try: alerts_wire()
except Exception as e: print("سلكُ التحذيرات تخطّى: "+str(e)[:80])

# ═══════════════ سَنَد تحت المجهر: رصدُ الشائعات بسلسلة إسنادٍ ثلاثيّة ═══════════════
# لا يُنشَر حكمٌ قاطعٌ إلا بما تتّفق عليه ثلاثةُ وكلاء: المُلتَقِط يجمع، والمُخرِّج يبحث
# ويُثبت المصدر، والفاحِص يفتح كلَّ رابطٍ بنفسه ويتأكّد أنه حيٌّ ويحتوي الادعاء. ما لم
# يُثبَتْ بمصدرٍ مفتوحٍ محقَّق يبقى «قيد التحقق» — الوفرةُ بلا هذه البوابة أسرعُ طريقٍ
# لنشر مصدرٍ مهلوس، وهو الفشلُ الوحيد الذي لا رجعةَ منه.
RUMORS_F=f"{OUT}/rumors.json"
RUMOR_BACKFILL_DONE=f"{OUT}/rumors_backfill.done"
_RUMOR_CAP=float(os.environ.get("RUMOR_DAILY_CAP_USD","0.15"))       # سقفٌ يوميٌّ صارمٌ للوكلاء المدفوعة
_RUMOR_BACKFILL_CAP=float(os.environ.get("RUMOR_BACKFILL_CAP_USD","1.50"))
_TIER2_ALERT=int(os.environ.get("RUMOR_TIER2_ALERT","3"))           # عتبةُ الحِمل: >٣ «قيد التحقق» باليوم = إشارةُ إجهاد
_RUMOR_BILLED=("المُلتَقِط","المُخرِّج","المُنقِّح")                  # الفاحِصُ مجّانيٌّ بالكامل

def _rumor_spent_today():
    try:
        c=json.load(open(f"{OUT}/cost.json"))
        if c.get("day")!=datetime.now(timezone.utc).strftime("%Y-%m-%d"): return 0.0
        return sum(c.get("by",{}).get(n,0) for n in _RUMOR_BILLED)
    except Exception: return 0.0

def _grok(P, max_tok=2500, max_calls=6, tools=True):
    """نداءٌ واحدٌ لـGrok مع أدوات البحث — يعيد (الردّ، النصّ) للفوترة والتحليل."""
    body={"model":os.environ.get("GROK_MODEL","grok-4.3"),
          "input":[{"role":"user","content":P}],"max_output_tokens":max_tok}
    if tools: body["tools"]=[{"type":"x_search"},{"type":"web_search"}]; body["max_tool_calls"]=max_calls
    req=urllib.request.Request("https://api.x.ai/v1/responses",data=json.dumps(body).encode(),
        headers={"Authorization":"Bearer "+GROK_KEY,"Content-Type":"application/json"})
    d=json.load(urllib.request.urlopen(req,timeout=420))
    txt="".join(c.get("text","") for o in d.get("output",[]) if o.get("type")=="message"
                for c in o.get("content",[]))
    txt=txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return d, txt

def _json_list(txt):
    try: return json.loads(txt[txt.find("["):txt.rfind("]")+1])
    except Exception: return []

def _rid(claim):
    return hashlib.md5(re.sub(r"\s+","",str(claim or "")).encode("utf-8")).hexdigest()[:10]

def _fetch_body(u, timeout=15):
    """يفتح الرابط ويقرأ جسمه نصًّا — مجّانًا عبر urllib، بلا أيّ مفتاح."""
    try:
        req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
        raw=urllib.request.urlopen(req,timeout=timeout).read()[:400000]
        return clean(raw.decode("utf-8","ignore"))
    except Exception: return ""

def _claim_in_body(claim, body):
    """مطابقةٌ تقريبيّة: هل تظهر كلماتُ الادعاء الدالّة في جسم الصفحة فعلًا؟"""
    words=re.findall(r"[؀-ۿ]{4,}", str(claim or ""))[:10]
    if not words: return False
    hit=sum(1 for w in words if w in body)
    return hit >= max(2, len(words)//2)

def _fahis_check(u, claim):
    """الفاحِص: يفتح الرابط، يتأكّد أنه حيّ، وأنه يحتوي الادعاء أو أنه من منفذٍ معتبَر."""
    u=str(u or "")
    if not _ok_url(u): return {"u":u,"ok":False,"live":False,"has":False,"t":"غير مُسند"}
    body=_fetch_body(u); live=bool(body)
    has=_claim_in_body(claim, body) if body else False
    t=grade(u)                                     # درجةُ النطاقِ نفسِه من قوائم TIER
    return {"u":u,"ok":bool(live and (has or t in ("صحيح","حسن"))),"live":live,"has":has,"t":t}

# ألفاظُ الحدثِ العسكريِّ الجسيم — لا نُثبّتُها «صحّ» عبر مسارِ الشائعات (للأخبارِ أنبوبُها بمصادره)
_WAR=("هجوم","هجمات","صاروخ","مسير","مسيّر","استهد","قصف","ضرب","اعتراض","غارة",
      "قتلى","قتيل","جرحى","انفجار","تفجير","قاعدة","عدوان","جاسوس","جواسيس","احتلال","سيطرة")
def _is_grave(claim): return any(w in str(claim or "") for w in _WAR)
def _looks_dateish(s): return any(m in str(s or "") for m in _AR_MON)   # فيه اسمُ شهرٍ = عنصرُ أرشيفٍ مؤرَّخ

@agent("multaqit")
def _rumor_collect(paid_ok):
    """المُلتَقِط: يجمع الادعاءات المنتشرة — مجّانًا من تنبيهات المُنبِّه، ثم بحثٌ مسقوف."""
    cands=[]; now_iso=datetime.now(timezone.utc).isoformat(timespec="minutes")
    # (أ) مجّانًا: إشاراتُ الشائعات التي رصدها المُنبِّه أصلًا
    try:
        for x in json.load(open(ALERTS)).get("list",[]):
            if "شائعة" in (x.get("kind") or ""):
                c=clean(x.get("txt") or x.get("body") or "")
                if len(c)>12: cands.append({"claim":c,"spread":"تنبيه رسميّ","u":x.get("u",""),"first_seen":now_iso})
    except Exception: pass
    # (ب) مدفوعٌ مسقوف: ما يُتداول على منصّة إكس والويب
    if paid_ok:
        P=("ارصد أبرز الادعاءات والشائعات المنتشرة حاليًا في التداول (منصّة إكس، واتساب، المنتديات) "
           "حول الكويت والخليج وإيران والمنطقة خلال ٢٤ ساعة — ما ينتشر بكثافةٍ ولم يُؤكَّد رسميًّا بعد، "
           "خاصّةً ما يمسّ الأمنَ والسلامةَ والاقتصاد.\n"
           'أخرج JSON فقط: [{"claim":"نصّ الادعاء كما يُتداول","spread":"أين ينتشر",'
           '"qail":"من أطلقَ الادعاءَ أو أبرزُ من تداوله — شخصٌ أو جهةٌ مسمّاةٌ كما وردت، وإلا فاتركه فارغًا",'
           '"u":"رابط المصدر المُدَّعى إن وُجد"}]\n'
           "٦ ادعاءات كحد أقصى. لا تُلفّقْ ادعاءً لم يُتداول فعلًا، ولا تُخمّنْ قائلًا لم يثبُت. "
           "لا تنصيص مزدوج داخل النصوص. لا شيء خارج JSON.")
        try:
            d,txt=_grok(P,max_tok=2200,max_calls=5); bill(d,"المُلتَقِط")
            for x in _json_list(txt):
                c=clean(x.get("claim",""))
                if len(c)>12: cands.append({"claim":c,"spread":clean(x.get("spread","التداول")),
                    "qail":clean(x.get("qail",""))[:60],"u":x.get("u",""),"first_seen":now_iso})
        except Exception as e: print("المُلتَقِط تخطّى البحث: "+str(e)[:80])
    # إزالةُ التكرار بالبصمة
    uniq={}
    for c in cands: uniq.setdefault(_rid(c["claim"]), c)
    out=list(uniq.values())
    print(f"🔍 المُلتَقِط: {len(out)} ادعاءً مرشَّحًا")
    return {"cands":out}

@agent("mukharrij")
def _rumor_takhrij(cands, paid_ok):
    """المُخرِّج: يبحث كلَّ ادعاءٍ ويُثبت مصدرَه ويحكم — تخريجُ الخبرِ إلى أصلِه الموثَّق."""
    now_iso=datetime.now(timezone.utc).isoformat(timespec="minutes")
    # بلا بحثٍ مدفوعٍ متاح: يبقى كلُّ ادعاءٍ «قيد التحقق» بأمانة (لم يُؤكَّد ولم يُنفَ)
    if not paid_ok:
        return {"judged":[{"claim":c["claim"],"spread":c.get("spread","التداول"),
            "qail":c.get("qail",""),
            "verdict":"قيد التحقق","why":"لا يزال قيد التحقّق — لم يُؤكَّد أو يُنفَ بمصدرٍ موثّق بعد.",
            "sources":([{"u":c["u"],"t":"المصدر المُدَّعى"}] if c.get("u") else []),
            "first_seen":c.get("first_seen",now_iso)} for c in cands]}
    numbered="\n".join("%d) %s"%(n,c["claim"]) for n,c in enumerate(cands))
    P=("لكلّ ادعاءٍ مرقَّمٍ أدناه، ابحث في المصادر الرسميّة والوكالات الموثوقة وتحقّق: هل صحّ، "
       "أم لم يصحّ، أم لا يزال مجهولًا؟ وأرفق روابط المصادر التي تؤكّد أو تنفي، "
       "وسمِّ من أطلقَ الادعاءَ أو أبرزَ من تداوله إن ثبتَ لديك — ولا تُخمّن.\n\n"
       "الادعاءات:\n"+numbered+"\n\n"
       'أخرج JSON فقط: [{"n":الرقم,"verdict":"صحّ|لم يصحّ|قيد التحقق","qail":"القائل أو فارغ",'
       '"why":"سببُ الحكم بجملة","sources":[{"u":"رابط","t":"اسم المصدر"}]}]\n'
       "احكم «صحّ» فقط بتأكيدٍ من مصدرٍ موثوقٍ برابط، و«لم يصحّ» فقط بنفيٍ موثّقٍ برابط، وإلا «قيد التحقق». "
       "لا تُصدِرْ حكمًا قاطعًا بلا رابطٍ يسنده. لا تنصيص مزدوج داخل النصوص. لا شيء خارج JSON.")
    judged=[]
    try:
        d,txt=_grok(P,max_tok=3000,max_calls=8); bill(d,"المُخرِّج")
        by_n={o.get("n"):o for o in _json_list(txt) if isinstance(o,dict)}
        for n,c in enumerate(cands):
            o=by_n.get(n) or {}
            v=o.get("verdict") if o.get("verdict") in ("صحّ","لم يصحّ","قيد التحقق") else "قيد التحقق"
            src=[s for s in (o.get("sources") or []) if isinstance(s,dict) and s.get("u")]
            if not src and c.get("u"): src=[{"u":c["u"],"t":"المصدر المُدَّعى"}]
            judged.append({"claim":c["claim"],"spread":c.get("spread","التداول"),"verdict":v,
                "qail":clean(o.get("qail",""))[:60] or c.get("qail",""),
                "why":clean(o.get("why","")) or "—","sources":src,"first_seen":c.get("first_seen",now_iso)})
    except Exception as e:
        print("المُخرِّج تخطّى: "+str(e)[:80])
        return {"judged":[{"claim":c["claim"],"spread":c.get("spread","التداول"),
            "qail":c.get("qail",""),
            "verdict":"قيد التحقق","why":"تعذّر البحثُ الآن — يبقى قيد التحقّق.",
            "sources":([{"u":c["u"],"t":"المصدر المُدَّعى"}] if c.get("u") else []),
            "first_seen":c.get("first_seen",now_iso)} for c in cands]}
    print(f"📑 المُخرِّج: حكم على {len(judged)} ادعاءً")
    return {"judged":judged}

@agent("fahis")
def _rumor_verify(judged):
    """الفاحِص (البوابة): يفتح كلَّ رابطٍ بنفسه؛ الحكمُ القاطعُ لا يمرّ بلا مصدرٍ حيٍّ محقَّق."""
    checked=0
    for it in judged:
        srcs=[]
        for s in it.get("sources",[]):
            r=_fahis_check(s.get("u"), it["claim"]); checked+=1
            srcs.append({"u":s.get("u"),"t":s.get("t") or r.get("t"),"ok":r["ok"]})
        it["sources"]=srcs
        passing=[s for s in srcs if s.get("ok")]
        it["_passing"]=len(passing)
        # 🛡️ البوابة: حكمٌ قاطعٌ (صحّ/لم يصحّ) بلا مصدرٍ حيٍّ محقَّق يُخفَّض إلى «قيد التحقق»
        if it["verdict"] in ("صحّ","لم يصحّ") and not passing:
            it["verdict"]="قيد التحقق"
            it["why"]=(it.get("why","")+" — لم يصمُدْ مصدرٌ حيٌّ عند الفحص، فأُبقيَ قيد التحقّق.").strip()
        # 🛡️ حارسُ النزاهة: لا نُثبّتُ حدثًا عسكريًّا جسيمًا كـ«صحّ» عبر مسارِ الشائعات —
        # المسارُ لتتبّعِ المتنازَعِ عليه (خاصّةً «لم يصحّ»)، لا لسردِ أحداثِ الحرب المؤكَّدة.
        if it["verdict"]=="صحّ" and _is_grave(it.get("claim","")):
            it["verdict"]="قيد التحقق"
            it["why"]=(it.get("why","")+" — حدثٌ عسكريٌّ جسيم لا يُثبَّت هنا كمؤكَّد؛ يبقى قيد التحقّق.").strip()
        it["gate"]={"multaqit":True,"mukharrij":True,"fahis":bool(passing)}
    print(f"🔗 الفاحِص: فحص {checked} رابطًا في {len(judged)} ادعاءً")
    return {"judged":judged}

@agent("munaqqih")
def _rumor_review(items, paid_ok):
    """المُنقِّح: مراجعٌ رابعٌ مستقلٌّ يمرُّ على المعروضِ كلَّ دورة — يطوي العالقَ القديمَ
    فيبقى القسمُ جاريًا، يعيدُ فحصَ مصادرِ الأحكامِ القاطعةِ مجّانًا، ويُثبتُ قائلَ
    الشائعةِ ويحاولُ حسمَ العالقِ ببحثٍ مسقوفٍ ضمن سقفِ المسار."""
    now=datetime.now(timezone.utc)
    out=[]; folded=0; rechecked=0
    for x in items:
        # (أ) طيُّ العالق: «قيد التحقق» بلا حسمٍ لأكثر من ٤٨ ساعة يُطوى من العرض
        if x.get("verdict")=="قيد التحقق" and not x.get("resolved_at"):
            try:
                if (now-datetime.fromisoformat(x["first_seen"])).total_seconds()>48*3600:
                    folded+=1; continue
            except Exception: pass
        out.append(x)
    # (ب) إعادةُ الفحصِ مجّانًا (سقف ٨ روابط بالدورة): حكمٌ قاطعٌ فقدَ كلَّ مصادرِه الحيّةِ
    # يعودُ «قيد التحقق» — فلا يبقى حكمٌ معلَّقًا على مصدرٍ ماتَ رابطُه.
    fuel=8
    for x in out:
        if fuel<=0: break
        if x.get("verdict") not in ("صحّ","لم يصحّ") or not x.get("sources"): continue
        srcs=[]; alive=0
        for s in x["sources"]:
            if fuel<=0: srcs.append(s); continue
            r=_fahis_check(s.get("u"), x.get("claim")); fuel-=1; rechecked+=1
            ok=bool(r["ok"]); alive+=ok
            srcs.append({"u":s.get("u"),"t":s.get("t"),"ok":ok})
        x["sources"]=srcs
        if not alive:
            x["verdict"]="قيد التحقق"; x["tier2"]=True; x["resolved_at"]=None
            x["why"]=(str(x.get("why",""))+" — أعادَ المُنقِّحُ الفحصَ فلم يصمُدْ مصدرٌ حيّ؛ أُعيدَ قيدَ التحقّق.").strip(" —")
    # (ج) قائلُ الشائعةِ ومحاولةُ حسمِ العالق — بحثٌ مدفوعٌ على نوبةِ المسارِ وسقفِه فقط
    need=[x for x in out if not x.get("qail") or x.get("verdict")=="قيد التحقق"][:5]
    if need and paid_ok and GROK_KEY and _rumor_spent_today()<_RUMOR_CAP and not over_budget("المُنقِّح"):
        numbered="\n".join("%d) %s"%(n,x["claim"]) for n,x in enumerate(need))
        P=("لكلّ ادعاءٍ مرقَّمٍ أدناه: (١) من أوّلُ من أطلقه أو أبرزُ من تداوله؟ سمِّ شخصًا أو "
           "جهةً محدّدةً كما وردت في التداول فعلًا — إن جُهل فاتركه فارغًا ولا تُخمّن. "
           "(٢) هل حُسم الآن بمصدرٍ موثوقٍ برابط؟\n\nالادعاءات:\n"+numbered+"\n\n"
           'أخرج JSON فقط: [{"n":الرقم,"qail":"القائل أو فارغ","verdict":"صحّ|لم يصحّ|قيد التحقق",'
           '"why":"سببُ الحكم بجملة","sources":[{"u":"رابط","t":"اسم المصدر"}]}]\n'
           "حكمٌ قاطعٌ يلزمه رابطٌ يسنده وإلا «قيد التحقق». لا تنصيص مزدوج داخل النصوص. لا شيء خارج JSON.")
        try:
            d,txt=_grok(P,max_tok=2200,max_calls=5); bill(d,"المُنقِّح")
            by_n={o.get("n"):o for o in _json_list(txt) if isinstance(o,dict)}
            for n,x in enumerate(need):
                o=by_n.get(n) or {}
                q=clean(o.get("qail",""))[:60]
                if q and not _looks_dateish(q): x["qail"]=q
                v=o.get("verdict")
                if v in ("صحّ","لم يصحّ") and x.get("verdict")=="قيد التحقق":
                    # بوّابةُ الفاحِص تسري على المُنقِّح أيضًا: لا حسمَ بلا مصدرٍ حيٍّ محقَّق،
                    # ولا «صحّ» لحدثٍ عسكريٍّ جسيمٍ عبر هذا المسار.
                    ns=[]
                    for s in (o.get("sources") or []):
                        if isinstance(s,dict) and s.get("u"):
                            r=_fahis_check(s["u"], x["claim"])
                            ns.append({"u":s["u"],"t":s.get("t") or r.get("t"),"ok":r["ok"]})
                    if any(s["ok"] for s in ns) and not (v=="صحّ" and _is_grave(x["claim"])):
                        x["verdict"]=v; x["tier2"]=False
                        x["why"]=clean(o.get("why","")) or x.get("why","—")
                        x["sources"]=(x.get("sources") or [])+ns
                        x["resolved_at"]=now.isoformat(timespec="minutes")
        except Exception as e: print("المُنقِّح تخطّى البحث: "+str(e)[:80])
    print(f"🔁 المُنقِّح: طوى {folded} عالقًا · أعاد فحص {rechecked} رابطًا · راجع {len(need)} قائلًا")
    return {"items":out,"folded":folded,"why":f"طوى {folded} · فحص {rechecked} رابطًا"}

def _rumor_backfill():
    """⛔ مُعطَّل عمدًا: كان يجلبُ «آخر ٣٠ يومًا» فيعيدُ نشرَ أحداثٍ عسكريّةٍ جسيمةٍ قديمةٍ
    كبطاقاتِ «صحّ» ويختمُها بتاريخِ اليوم — أخبارٌ قديمةٌ تظهرُ كأنها الآن، وبابٌ خلفيٌّ
    لصنفِ الادّعاءات التي عُطّلت سابقًا (grok_intel، mustaqsi). الأرشيفُ يتعمّقُ للأمام
    طبيعيًّا من الشائعاتِ الجاريةِ بدل دفعةٍ رجعيّةٍ خطِرة."""
    return []
    # ── ما يلي مُعطَّل (لا يُنفَّذ) ──
    if os.path.exists(RUMOR_BACKFILL_DONE) or not GROK_KEY: return []
    if _rumor_spent_today() >= _RUMOR_BACKFILL_CAP:
        print("🗄️ الأرشيف الرجعي: بلغ السقف — يُؤجَّل"); return []
    now_iso=datetime.now(timezone.utc).isoformat(timespec="minutes")
    got=[]
    P=("ابحث عن أبرز الشائعات والادعاءات التي انتشرت حول الكويت والخليج وإيران والمنطقة خلال آخر ٣٠ يومًا، "
       "وتبيّن لاحقًا مصيرُها بمصادرَ موثّقة: أيُّها صحّ وأيُّها لم يصحّ.\n"
       'أخرج JSON فقط: [{"claim":"نصّ الادعاء","when":"متى انتشر","verdict":"صحّ|لم يصحّ|قيد التحقق",'
       '"why":"سببُ الحكم بجملة","sources":[{"u":"رابط","t":"اسم المصدر"}]}]\n'
       "١٢ عنصرًا كحد أقصى. لكلّ حكمٍ قاطعٍ رابطٌ يسنده. لا تنصيص مزدوج. لا شيء خارج JSON.")
    try:
        d,txt=_grok(P,max_tok=4000,max_calls=12); bill(d,"المُخرِّج")
        for x in _json_list(txt):
            c=clean(x.get("claim",""))
            if len(c)<12: continue
            got.append({"claim":c,"spread":clean(x.get("when","")) or "التداول",
                "verdict":x.get("verdict") if x.get("verdict") in ("صحّ","لم يصحّ","قيد التحقق") else "قيد التحقق",
                "why":clean(x.get("why","")) or "—",
                "sources":[s for s in (x.get("sources") or []) if isinstance(s,dict) and s.get("u")],
                "first_seen":now_iso,"_backfill":True})
        open(RUMOR_BACKFILL_DONE,"w").write(now_iso)
        print(f"🗄️ الأرشيف الرجعي: التقط {len(got)} شائعةً من آخر ٣٠ يومًا")
    except Exception as e: print("الأرشيف الرجعي تعذّر: "+str(e)[:80])
    return got

def _rumor_audit(items):
    """مؤشّرُ الحِمل (>٣ قيد التحقق باليوم) وحارسُ الانجراف (ارتفاعُ «لم يصحّ» شذوذًا)."""
    today=datetime.now(_KW).date().isoformat()
    tier2_today=sum(1 for x in items if x.get("verdict")=="قيد التحقق"
                    and str(x.get("first_seen","")).startswith(today))
    dist={"صحّ":0,"لم يصحّ":0,"قيد التحقق":0}
    for x in items: dist[x.get("verdict","قيد التحقق")]=dist.get(x.get("verdict","قيد التحقق"),0)+1
    tot=sum(dist.values()) or 1
    last10=items[:10]
    recent_false=sum(1 for x in last10 if x.get("verdict")=="لم يصحّ")/(len(last10) or 1)
    base_false=dist["لم يصحّ"]/tot
    drift=bool(len(items)>=10 and recent_false>0.6 and recent_false>base_false*1.5)
    return {"tier2_today":tier2_today,"overload":tier2_today>_TIER2_ALERT,
            "dist":dist,"last10":[{"id":x["id"],"verdict":x["verdict"]} for x in last10],
            "drift_flag":drift,
            "note":("راجعْ آخر ١٠ أحكامٍ بحياد — ارتفعت نسبة «لم يصحّ»." if drift else
                    ("تجاوزتَ ٣ حالاتٍ قيد التحقق اليوم — إشارةُ إجهادٍ في الحكم." if tier2_today>_TIER2_ALERT else ""))}

def rumor_track():
    """المنسِّق: يجمع، يخرّج، يفحص، ثم يدمج وينشر ما اجتاز البوابة — مع تدقيقِ الحِمل والانجراف."""
    now=datetime.now(timezone.utc); now_iso=now.isoformat(timespec="minutes")
    try: old=json.load(open(RUMORS_F))
    except Exception: old=None
    age=(now-datetime.fromisoformat(old["updated"])).total_seconds()/3600 if old else 999
    paid_ok=bool(GROK_KEY) and (age>=8 or bool(os.environ.get("FORCE_RUMORS"))) and _rumor_spent_today()<_RUMOR_CAP and not over_budget("سند تحت المجهر")
    # ١) جمع  ٢) تخريج/حكم  ٣) فحص الروابط (البوابة)
    cands=(_rumor_collect(paid_ok) or {}).get("cands",[])
    seed=_rumor_backfill()
    judged=(_rumor_takhrij(cands, paid_ok) or {}).get("judged",[]) if cands else []
    judged+=seed
    judged=(_rumor_verify(judged) or {}).get("judged",[]) if judged else []
    # ٤) دمجٌ يحفظ «قال/صار»: أوّلُ ظهورٍ يبقى، ووقتُ الحسمِ يُثبَّت عند أوّل حكمٍ قاطع
    keep={x["id"]:x for x in (old or {}).get("items",[])}
    for it in judged:
        rid=_rid(it["claim"]); prev=keep.get(rid,{})
        # فصلُ التاريخِ عن مكانِ الانتشار: لا يُوضَعُ تاريخٌ في spread أبدًا
        sp=str(it.get("spread","التداول") or "التداول"); wn=str(it.get("when","") or prev.get("when",""))
        if _looks_dateish(sp): wn=wn or sp; sp="التداول"
        first_seen=prev.get("first_seen") or it.get("first_seen") or now_iso
        resolved_at=prev.get("resolved_at")
        if it["verdict"] in ("صحّ","لم يصحّ") and not resolved_at: resolved_at=now_iso
        q=clean(str(it.get("qail","")))[:60]
        if _looks_dateish(q): q=""
        keep[rid]={"id":rid,"claim":it["claim"],"verdict":it["verdict"],
            "qail":q or prev.get("qail",""),
            "spread":sp,"when":wn,"why":it.get("why","—"),
            "sources":it.get("sources",[]),"tier2":it["verdict"]=="قيد التحقق",
            "gate":it.get("gate",{"multaqit":True,"mukharrij":True,"fahis":bool(it.get("_passing"))}),
            "first_seen":first_seen,"resolved_at":resolved_at,"updated":now_iso}
    # 🛡️ حارسُ الطزاجةِ والنزاهة (يُطبَّقُ على الكلِّ فيُنظّفُ المتراكمَ القديمَ أيضًا):
    #   يُسقَطُ عنصرٌ مؤرَّخٌ (أرشيفٌ قديمٌ سرّب تاريخًا) أو حدثٌ عسكريٌّ جسيمٌ بحكمِ «صحّ».
    def _drop(x):
        if _looks_dateish(x.get("spread","")) or _looks_dateish(x.get("when","")): return True
        if x.get("verdict")=="صحّ" and _is_grave(x.get("claim","")): return True
        return False
    def _rank(x): return (x.get("resolved_at") or x.get("first_seen") or "")
    merged=sorted([x for x in keep.values() if not _drop(x)], key=_rank, reverse=True)[:12]
    # ٥) المُنقِّح (المراجعُ الرابع): يطوي العالقَ القديمَ ويعيدُ الفحصَ ويُثبتُ القائل
    merged=(_rumor_review(merged, paid_ok) or {}).get("items", merged)
    audit=_rumor_audit(merged)
    json.dump({"updated":now_iso,"items":merged,"audit":audit},
        open(RUMORS_F,"w"),ensure_ascii=False,indent=1)
    if audit["overload"] or audit["drift_flag"]: print("⚖️ سند تحت المجهر: "+audit["note"])
    print(f"🔬 سند تحت المجهر: {len(merged)} شائعةً · {audit['dist']} · قيد التحقق اليوم {audit['tier2_today']}")

rumor_track()

# ═══════════ المِقياس: مؤشّرُ عدم الاستقرار الإقليميّ — حسابٌ شفّافٌ صِرف ═══════════
# نظيرُ «Country Instability Index» بروحِ الإسناد: لا نموذجَ لغويًّا ولا تخمين —
# عدٌّ حتميٌّ لكثافةِ الموادِّ المُسنَدةِ التي جمعها الأنبوبُ في هذه الدورةِ نفسِها،
# والصيغةُ معلنةٌ والمكوّناتُ تُحفَظُ خامًا لكلّ دولة (إسنادُ المؤشّرِ نفسِه).
TENSION_F=f"{OUT}/tension.json"
_CTRY=[
 # (id, الاسم, EN, [مرادفات المطابقة], lat, lon)
 ("kw","الكويت","Kuwait",["الكويت","كويتي","الكويتية","الكويتي"],29.3,47.8),
 ("sa","السعودية","Saudi Arabia",["السعودية","سعودي","السعودي","الرياض","جازان","ينبع","جدة"],24.0,45.0),
 ("ae","الإمارات","UAE",["الإمارات","إماراتي","الإماراتية","أبوظبي","دبي"],24.2,54.3),
 ("qa","قطر","Qatar",["قطر","قطري","القطرية","الدوحة"],25.3,51.2),
 ("bh","البحرين","Bahrain",["البحرين","بحريني","البحرينية","المنامة"],26.0,50.5),
 ("om","عُمان","Oman",["عمان","عُمان","عماني","العمانية","مسقط"],21.0,57.0),
 ("iq","العراق","Iraq",["العراق","عراقي","العراقية","بغداد","أربيل","البصرة"],33.0,44.0),
 ("ir","إيران","Iran",["إيران","إيراني","الإيرانية","طهران","أصفهان","بوشهر","هرمز"],32.0,53.0),
 ("ye","اليمن","Yemen",["اليمن","يمني","اليمنية","صنعاء","الحوثي","الحوثيين","الحديدة"],15.5,47.5),
 ("ps","فلسطين","Palestine",["فلسطين","فلسطيني","الفلسطينية","غزة","القدس","الضفة","رفح","إسرائيل","الإسرائيلي","الاحتلال"],31.9,35.2),
]
def _tension_level(s):
    return "حرج" if s>=75 else ("متوتّر" if s>=50 else ("مترقّب" if s>=25 else "هادئ"))

@agent("miqyas")
def miqyas():
    def _load(p, key):
        try: return json.load(open(p)).get(key) or []
        except Exception: return []
    news=[]
    try:
        for _c,_l in (json.load(open(f"{OUT}/news.json")).get("cats") or {}).items():
            for it in _l: news.append({**it,"_cat":_c})
    except Exception: pass
    alerts=_load(ALERTS,"list"); rums=_load(RUMORS_F,"items"); offi=_load(OFFI,"src")
    try: prev={c["id"]:c.get("score",0) for c in json.load(open(TENSION_F)).get("countries",[])}
    except Exception: prev={}
    def _hit(txt, aliases): return any(a in str(txt or "") for a in aliases)
    out=[]
    for cid,nm,en,al,lat,lon in _CTRY:
        m=[x for x in news if _hit(x.get("head"),al)]
        n=len(m)
        u=sum(1 for x in m if x.get("_cat")=="عاجل")
        w=sum(1 for x in m if _is_grave(x.get("head")))
        a=sum(1 for x in alerts if _hit(str(x.get("txt",""))+" "+str(x.get("body","")),al))
        r=sum(1 for x in rums if x.get("verdict") in ("قيد التحقق","لم يصحّ") and _hit(x.get("claim"),al))
        o=sum(1 for x in offi if _hit(str(x.get("p",""))+" "+str(x.get("e","")),al))
        score=min(100, 4*u + 3*w + 8*a + 4*r + 2*max(0,n-u) + o)
        # عيّنةُ أحداثِ اليوم (وقودُ طبقاتِ الخريطة) — أحدثُ ٥ موادَّ مُسنَدةً بروابطها
        ev=sorted(m, key=lambda x:str(x.get("at","")), reverse=True)[:5]
        out.append({"id":cid,"name":nm,"en":en,"lat":lat,"lon":lon,
            "score":score,"level":_tension_level(score),
            "delta":score-prev.get(cid,score),
            "parts":{"n":n,"u":u,"w":w,"a":a,"r":r,"o":o},
            "events":[{"h":x.get("head",""),"g":x.get("grade",""),"u":x.get("link",""),
                       "at":x.get("at",""),"src":x.get("src","")} for x in ev]})
    out.sort(key=lambda c:-c["score"])
    json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "note":"مؤشرٌ حسابيٌّ شفّافٌ من كثافة المواد المُسنَدة وحدَها — ليس تقييمًا استخباراتيًّا رسميًّا",
        "formula":"score = min(100, 4·عاجل + 3·ألفاظ تصعيد + 8·تحذيرات + 4·شائعات + 2·أخبار أخرى + بيانات رسمية)",
        "countries":out}, open(TENSION_F,"w"),ensure_ascii=False,indent=1)
    top=out[0] if out else {}
    print(f"🌡️ المِقياس: {len(out)} دولةً · الأعلى {top.get('name','—')} {top.get('score',0)}/100 ({top.get('level','')})")
    return {"why":f"الأعلى {top.get('name','—')} {top.get('score',0)}/100"}

try: miqyas()
except Exception as e: print("المِقياس تخطّى: "+str(e)[:80])

# ═══ المُستَقصي: أعداد الذخائر نقلًا عن وزارات الدفاع مباشرة ═══
MODF=f"{OUT}/mod.json"

@agent("mustaqsi")
def mustaqsi():
    """⛔ مُعطَّل عمدًا: كان يُولّد أعدادَ صواريخَ ومسيّراتٍ عبرَ Grok وينسبُها إلى
    جهاتٍ عسكريّةٍ رسميّة (رئاسة الأركان الكويتية ووزاراتِ دفاعِ الخليج) دون تحقّقٍ
    ممكن — تلفيقٌ منسوبٌ زورًا لجهاتٍ سياديّة، كحصيلةِ الحرب التي عُطّلت سابقًا.
    نُبقيه صامتًا: لا نَنشُر رقمًا عسكريًّا ما لم يُعلِنْه مصدرُه الأوّلُ صراحةً ويُتحقَّق منه."""
    j={"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),"list":[],"disabled":1}
    try: json.dump(j,open(MODF,"w"),ensure_ascii=False,indent=1)
    except Exception: pass
    return {"skipped":1,"why":"مُعطَّل — لا تُنشَر أرقامٌ عسكريّةٌ غيرُ مُتحقَّقة"}
    # ── ما يلي مُعطَّل (لا يُنفَّذ) ──
    try:
        old=json.load(open(MODF))
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(old["updated"])).total_seconds()/3600
    except Exception: old,age=None,999
    if age<6 and not os.environ.get("FORCE_MOD"):
        print(f"⏱️ المُستَقصي: يعمل بعد ~{max(0,round(6-age,1))}س")
        return {"skipped":1,"why":f"يعمل بعد ~{max(0,round(6-age,1))}س"}
    if not GROK_KEY: return
    P=("ابحث في الحسابات والمواقع الرسمية لوزارات الدفاع والأركان في كل بلد أدناه، "
       "واستخرج ما أعلنته هي بنفسها عن الصواريخ والمسيّرات التي استُهدفت بها وما اعترضته دفاعاتها.\n\n"
       "الجهات الرسمية المستهدفة:\n"
       "- الكويت: رئاسة الأركان العامة للجيش الكويتي / وزارة الدفاع\n"
       "- السعودية: وزارة الدفاع السعودية / قوات الدفاع الجوي\n"
       "- الإمارات: وزارة الدفاع الإماراتية\n"
       "- قطر: وزارة الدفاع القطرية / القوات المسلحة\n"
       "- البحرين: قوة دفاع البحرين\n"
       "- عُمان: وزارة الدفاع العُمانية\n"
       "- العراق: وزارة الدفاع / خلية الإعلام الأمني\n"
       "- الولايات المتحدة: CENTCOM / البنتاغون\n"
       "- إيران: وزارة الدفاع الإيرانية / الحرس الثوري\n\n"
       'أخرج JSON فقط: [{"c":"البلد","f":"علم","mis":"عدد الصواريخ الباليستية","crz":"عدد الصواريخ الجوّالة",'
       '"drn":"عدد المسيّرات","itc":"عدد ما اعتُرض","body":"اسم الجهة الرسمية كما وردت",'
       '"h":"@حسابها الرسمي إن وُجد","u":"رابط البيان","asof":"تاريخ البيان","q":"اقتباس من البيان"}]\n\n'
       "خُذ الأرقام التراكمية منذ بداية الأزمة لا أرقام اليوم الواحد، "
       "وابحث عن البيانات المرقّمة (بيان رقم كذا) فهي التي تحمل الحصيلة التراكمية.\n"
       "قواعد صارمة: انقل الأرقام عن الجهة الرسمية نفسها فقط. "
       "إن لم تُعلن الجهة رقمًا فاكتب «لم تُعلن» ولا تنقل عن صحيفة أو ناشط. "
       "لا تنصيص مزدوج داخل النصوص. لا شيء خارج JSON.")
    body={"model":os.environ.get("GROK_MODEL_HEAVY","grok-4.3"),"input":[{"role":"user","content":P}],
        "tools":[{"type":"x_search"},{"type":"web_search"}],
        "max_output_tokens":4000,"max_tool_calls":10}
    try:
        req=urllib.request.Request("https://api.x.ai/v1/responses",data=json.dumps(body).encode(),
            headers={"Authorization":"Bearer "+GROK_KEY,"Content-Type":"application/json"})
        d=json.load(urllib.request.urlopen(req,timeout=520))
        txt="".join(c.get("text","") for o in d.get("output",[]) if o.get("type")=="message"
                    for c in o.get("content",[]))
        txt=txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        lst=json.loads(txt[txt.find("["):txt.rfind("]")+1])
        NA={"لم تُعلن","لم تعلن","غير معلن","—",""}
        # حارس: احتفظ بما أُعلن سابقًا إن غاب الآن
        pm={x.get("c"):x for x in (old or {}).get("list",[])}
        for x in lst:
            p=pm.get(x.get("c")) or {}
            for k in ("mis","crz","drn","itc","q","u","h","body","asof"):
                if str(x.get(k,"")).strip() in NA and str(p.get(k,"")).strip() not in NA:
                    x[k]=p[k]
        good=sum(1 for x in lst if str(x.get("mis","")) not in NA or str(x.get("drn","")) not in NA)
        if old and good < len([1 for x in old.get("list",[])
                   if str(x.get("mis","")) not in NA or str(x.get("drn","")) not in NA])*0.7:
            print("🛡️ بيانات المُستَقصي أضعف — أُبقيت السابقة"); return old
        bill(d,"المُستَقصي")
        json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),"list":lst},
            open(MODF,"w"),ensure_ascii=False,indent=1)
        print(f"🎯 المُستَقصي: {good}/{len(lst)} جهة أعلنت أرقامًا رسميًا")
        return {"list":lst}
    except Exception as e:
        print("المُستَقصي تخطّى: "+str(e)[:90])
        return old

mustaqsi()

# ═══ دمج الأرقام الرسمية في الحصيلة (تسبق المجمَّعة) ═══
def merge_mod():
    try:
        md={x["c"]:x for x in json.load(open(MODF)).get("list",[])}
        t=json.load(open(INTEL))
        NA={"لم تُعلن","لم تعلن","غير معلن","—",""}
        n=0
        for row in t.get("toll",[]):
            m=md.get(row.get("c"))
            if not m: continue
            official=[]
            for k in ("mis","crz","drn","itc"):
                v=str(m.get(k,"")).strip()
                if v and v not in NA:
                    row[k]=v; official.append(k)          # رسمي: من البيان
                else:
                    row.pop(k,None)                        # لم تُعلنه الجهة → لا يُعرض
            if official:
                row["mil_ok"]=official                     # أيُّ حقلٍ رسميٌّ بالضبط
                row["mil_src"]=m.get("body",""); row["mil_h"]=m.get("h","")
                if m.get("q"): row["mil_q"]=m["q"]; row["mil_u"]=m.get("u","")
                n+=1
            else:
                for k in ("mil_src","mil_h","mil_q","mil_u","mil_ok"): row.pop(k,None)
        json.dump(t,open(INTEL,"w"),ensure_ascii=False,indent=1)
        if n: print(f"🔗 دُمجت أرقام {n} جهة عسكرية رسمية في الحصيلة")
    except Exception as e: print("الدمج تعذّر: "+str(e)[:70])

merge_mod()

mustaqri()

# ═══ فقرة المحلل الاستراتيجي (وكيل — يُصرَّح بذلك) ═══
def _distinct_who(f,n=3):
    """قائلون متمايزون بلا تكرار، بترتيب ورودهم — كي لا تُهيمن جهةٌ واحدة على
    الزوايا (كان يظهر «ترامب، ترامب» حين يتكرّر القائل في أوّل الإشارات)."""
    seen=set(); out=[]
    for x in (f.get("signals") or []):
        w=str(x.get("who","")).strip()
        if w and w not in seen:
            seen.add(w); out.append(w)
        if len(out)>=n: break
    return out

def _analyst_fallback(f):
    """قراءةٌ محسوبةٌ من الاستقراء نفسِه — تُبنى من أرقامٍ حقيقيّةٍ لا من تلفيق،
    كي لا تجمُدَ قراءةُ المحلّل إن تعذّر التوليدُ اللغويّ."""
    scs=sorted((f.get("scenarios") or []),key=lambda x:-(x.get("p") or 0))
    if not scs: return ""
    top=scs[0]
    who=_distinct_who(f,3)
    if   len(who)>=3: lead="من ثلاث زوايا: "+"، ".join(who[:3])
    elif len(who)==2: lead="من زاويتين: "+" و".join(who)
    elif len(who)==1: lead="من زاويةٍ محوريّة: "+who[0]
    else:             lead="من المشهد الميدانيّ والسياسيّ والدبلوماسيّ"
    out=["شكرًا لك. المشهد اليوم يُقرأ "+lead+"."]
    out.append("السيناريو الأكثر ترجيحًا بنسبة %s%% هو %s."%(top.get("p"),str(top.get("s","")).strip()))
    if top.get("why"): out.append("وتدعمه السابقة: "+str(top["why"]).strip()+".")
    out.append("وتبقى هذه قراءةً احتمالية، والمؤشر الحاسم هو "
        +(str(top.get("watch")).strip() if top.get("watch") else "مدى تبدّل مواقف الأطراف في الجولات القادمة")+".")
    return " ".join(out)

@agent("murtajil")
def analyst_segment():
    """يحوّل الاستقراء إلى تحليل منطوق بأسلوب ضيف النشرات، بصوت مغاير للمذيع."""
    try: f=json.load(open(FCAST))
    except Exception: return
    try:
        a_old=json.load(open(f"{OUT}/analyst.json"))
        if a_old.get("src")==f.get("updated"):
            print("⏱️ المُحلِّل: القراءة مواكبة لآخر استقراء")
            return {"skipped":1,"why":"القراءة مواكبة"}
    except Exception: pass
    _scs=sorted((f.get("scenarios") or []),key=lambda x:-(x.get("p") or 0))
    _watch=str((_scs[0].get("watch") if _scs else "") or "").strip()
    scn="\n".join("- (%s%%) %s | السابقة: %s"%(x.get("p"),x.get("s",""),str(x.get("why",""))[:150])
                   for x in f.get("scenarios",[]))
    sig="\n".join("- %s: %s"%(x.get("who",""),str(x.get("q",""))[:120]) for x in f.get("signals",[])[:4])
    _ang=_distinct_who(f,3)
    _ang_line=("الزوايا المتمايزة (أطّر المشهد حولها ولا تكرّر أيّ قائل): "+"، ".join(_ang)) \
        if _ang else "أطّر المشهد من زواياه الميدانيّة والسياسيّة والدبلوماسيّة"
    _watch_line=("المؤشّر الحاسم المُسنَد: "+_watch) if _watch else \
        "اجعل المؤشّر الحاسم حدثًا واحدًا قابلًا للرصد ومنسوبًا لمصدرٍ رسميّ (بيانٌ أو تصريحٌ موثَّق)"
    P=("اكتب فقرة تحليل استراتيجي منطوقة، بأسلوب الضيف الخبير الرصين في النشرات الإخبارية العربية.\n\n"
       "الإشارات:\n"+sig+"\n\n"+_ang_line+"\n\nالسيناريوهات:\n"+scn+"\n"+_watch_line+"\n\n"
       "القواعد: ابدأ بـ«شكرًا لك. المشهد اليوم يُقرأ من» ثم أطّره حول الزوايا المتمايزة أعلاه "
       "بعددها الفعليّ دون تكرار أيّ قائل (زاويتان تُذكران زاويتين لا ثلاثًا). "
       "٩٠ إلى ١٢٠ كلمة. عربية فصيحة رصينة، دقيقةٌ لا تُبالغ ولا تحشو؛ انسُب كلَّ قولٍ لقائله. "
       "اذكر النسبة الأعلى صراحةً، واستشهد بسابقة تاريخية واحدة دقيقة ومتّصلة بالسيناريو. "
       "اختم بـ«وتبقى هذه قراءةً احتمالية، والمؤشر الحاسم هو» ثم اذكر مؤشّرًا واحدًا قابلًا للرصد "
       "ومُسنَدًا لمصدرٍ رسميّ لا عبارةً عامّة. "
       "أخرج النص فقط بلا عناوين ولا رموز ولا أسماء نماذج أو شركات.")
    txt=""
    if GEMINI_KEY:
        try:
            body={"contents":[{"parts":[{"text":P}]}],
                "generationConfig":{"maxOutputTokens":1400,"temperature":0.55,
                    "thinkingConfig":{"thinkingBudget":0}}}
            d=gemini_post(body, timeout=90)
            cand=(d.get("candidates") or [{}])[0]
            parts=((cand.get("content") or {}).get("parts") or [])
            txt="".join(p.get("text","") for p in parts if isinstance(p,dict)).strip()
            if not txt: print("فقرة المحلل: ردٌّ بلا نصّ (%s) — سنبني من الاستقراء"%cand.get("finishReason",""))
        except Exception as e:
            print("فقرة المحلل — تعذّر التوليد: "+str(e)[:70]+" — سنبني من الاستقراء")
    if not txt:
        txt=_analyst_fallback(f)          # لا تجمُدُ القراءةُ أبدًا: تُبنى من الاستقراء الحيّ
    if not txt: return

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

    json.dump({"name":"المُستقرِئ","title":"محلل استراتيجي · مساعد ذكاء اصطناعي",
        "text":txt,"audio":"analyst.mp3" if ok else "",
        "src":f.get("updated",""),"avatar":"analyst.jpg",
        "updated":datetime.now(timezone.utc).isoformat(timespec="minutes")},
        open(f"{OUT}/analyst.json","w"),ensure_ascii=False,indent=1)
    print("🎤 فقرة المحلل: %d كلمة%s"%(len(txt.split())," + صوت" if ok else ""))

analyst_segment()

# ═══ المُدوِّن: كاتبُ عمودِ الجريدة اليوميّ — Gemini فقط، صفرُ كلفةِ Grok ═══
COLF=f"{OUT}/column.json"

@agent("mudawwin")
def mudawwin():
    """يكتبُ عمودَ رأيٍ يوميًّا واحدًا من أخبارِ اليومِ المُسنَدةِ وحدَها — رأيٌ يُصاغُ
    كقراءةٍ لا كحقيقة، بإفصاحٍ صريحٍ أنّ الكاتبَ مساعدُ ذكاءٍ اصطناعيّ."""
    kw_today=datetime.now(_KW).date().isoformat()
    try:
        old=json.load(open(COLF))
        if old.get("date")==kw_today and not os.environ.get("FORCE_COLUMN"):
            print("⏱️ المُدوِّن: عمودُ اليوم منشور")
            return {"skipped":1,"why":"عمودُ اليوم منشور"}
    except Exception: old=None
    if not GEMINI_KEY: return {"skipped":1,"why":"لا مفتاح Gemini"}
    feed=[i for i in items if i.get("grade") in ("صحيح","حسن")][:12]
    if len(feed)<4:
        print("⏱️ المُدوِّن: عناوينُ اليوم أقلُّ من أن تُبنى عليها قراءة")
        return {"skipped":1,"why":"عناوينُ غيرُ كافية"}
    heads="\n".join("- [%s] %s — نقلًا عن %s"%(i["grade"],i["head"],i.get("src") or "المصدر") for i in feed)
    scn=""
    try:
        f=json.load(open(FCAST))
        top=sorted(f.get("scenarios") or [],key=lambda x:-(x.get("p") or 0))
        if top: scn="\n\nالسيناريو الأرجح لدى فريق الاستقراء (%s%%): %s"%(top[0].get("p"),top[0].get("s",""))
    except Exception: pass
    P=("اكتب عمودَ رأيٍ صحفيًّا واحدًا لجريدة «سَنَد» بالفصحى الرصينة، ٢٥٠ إلى ٣٥٠ كلمة، "
       "بأسلوب كاتبِ عمودٍ خليجيٍّ متمرّس: مدخلٌ آسر، فكرةٌ ناظمةٌ واحدة، وخاتمةٌ تترك أثرًا.\n\n"
       "أخبارُ اليوم المُسنَدة (مادّتُك الوحيدة):\n"+heads+scn+"\n\n"
       "قواعدُ نزاهةٍ صارمة:\n"
       "- لا تذكرْ أيَّ واقعةٍ غيرِ واردةٍ في العناوين أعلاه، وانسُبْ كلَّ واقعةٍ لمصدرها (نقلًا عن …).\n"
       "- صُغِ الرأيَ كقراءةٍ واستنتاجٍ لا كحقيقةٍ مقطوعٍ بها؛ ولا تُهوّلْ ولا تُهوِّن.\n"
       "- لا مقارنةَ بوسائلَ إعلامٍ أخرى، ولا أسماءَ نماذجَ أو شركاتِ تقنية.\n"
       "- لا أرقامَ عسكريّةً أو حصائلَ إلا ما ورد حرفيًّا في العناوين.\n"
       'أخرج JSON فقط: {"title":"عنوانُ العمود (٣-٧ كلمات)","text":"نصُّ العمود فقراتٍ يفصلُها سطرٌ فارغ"}')
    try:
        j=gemini_json(P, max_tok=2400, temp=0.6)
        title=clean(j.get("title","")); text=str(j.get("text","")).strip()
        if len(text.split())<120 or not title: raise ValueError("عمودٌ ناقص")
    except Exception as e:
        # لا قالبَ مُلفَّقًا: يبقى عمودُ الأمس حتى ينجحَ توليدُ اليوم
        print("المُدوِّن — تعذّر التوليد: "+str(e)[:70]+(" — يبقى عمودُ الأمس" if old else ""))
        if old: return {"skipped":1,"why":"تعذّر التوليد — بقي عمودُ الأمس"}
        raise            # بلا عمودٍ سابقٍ الفشلُ فشلٌ — لا يُعرَض «ok» زورًا في لوحة الإدارة
    # 🌍 نسخةُ العمود الإنجليزيّة — نداءٌ مجّانيّ واحد، وغيابُها لا يعطّل شيئًا
    he_t,he_x="",""
    try:
        jt=gemini_json("Translate this Arabic opinion column to elegant journalistic English. "
            "Faithful translation, keep attributions (according to ...) intact.\n"
            'Return JSON only: {"title":"...","text":"..."}\n'
            "TITLE: "+title+"\nTEXT:\n"+text, max_tok=4000, temp=0.3)
        he_t=clean(jt.get("title","")); he_x=str(jt.get("text","")).strip()
    except Exception as e: print("ترجمة العمود تخطّت: "+str(e)[:50])
    # 🎧 «اسمع العمود» — صوتٌ مجّانيّ بنمطِ فقرةِ المحلّل نفسِه
    col_mp3=f"{OUT}/column.mp3"; aok=False
    try:
        import edge_tts, ssl as _s, asyncio as _a
        import edge_tts.communicate as _c
        _ctx=_s.create_default_context(); _ctx.check_hostname=False; _ctx.verify_mode=_s.CERT_NONE
        try: _c._SSL_CTX=_ctx
        except Exception: pass
        async def _go():
            await edge_tts.Communicate(title+". "+text,"ar-SA-HamedNeural",rate="-6%").save(col_mp3)
        _a.run(_go())
        aok=os.path.getsize(col_mp3)>4000
    except Exception as e: print("صوت العمود تعذّر: "+str(e)[:60])
    json.dump({"name":"المُدوِّن","title":"كاتبُ الجريدة · مساعد ذكاء اصطناعي",
        "head":title,"text":text,"date":kw_today,"src_n":len(feed),
        "head_en":he_t,"text_en":he_x,
        "audio":"column.mp3" if aok else "",
        "updated":datetime.now(timezone.utc).isoformat(timespec="minutes")},
        open(COLF,"w"),ensure_ascii=False,indent=1)
    print("🖋️ المُدوِّن: «%s» — %d كلمة من %d عنوانًا مُسنَدًا%s"%(title,len(text.split()),len(feed)," + 🎧" if aok else ""))

mudawwin()

naqid()

# ═══ الإسناد يُحسب دائمًا — حتى لو تُخطّي التدقيق ═══
for _k in [k for k,v in cats.items() if len(v)<3 and k not in ("عاجل",)]:
    print(f"🔇 أُخفي قسم «{_k}» ({len(cats[_k])} خبرًا فقط)"); del cats[_k]
apply_isnad()
json.dump({"updated":datetime.now(timezone.utc).isoformat(timespec="minutes"),"cats":cats},
    open(f"{OUT}/news.json","w"),ensure_ascii=False,indent=1)

if os.environ.get("NEWS_ONLY"):
    try:
        _m=json.load(open(f"{OUT}/latest.json")); _t=datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if _m.get("video_date")==_t: mark("rawi","ok","فيديو اليوم جاهز")
        elif _m.get("date")==_t:     mark("rawi","ok","نشرة اليوم صوتيًا")
        else:
            _hk=(datetime.now(timezone.utc).hour+3)%24
            mark("rawi","skip",f"النشرة ٦ مساءً (~{(18-_hk)%24}س)")
    except Exception: mark("rawi","skip","بانتظار أول نشرة")
    archive()
    bundle()
    broadcast_official(); broadcast_alerts(); broadcast_news()
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
        f"7) الطول إلزامي: لا تقل النشرة عن ٣٥٠ كلمة ولا تزيد عن ٤٨٠. "
        f"غطِّ كل عنوان من العناوين الاثني عشر بجملتين على الأقل، بترتيب الأهمية، "
        f"مع جملة ربط قصيرة بين المحاور (الأزمة ثم الخليج ثم التقنية).\n\nالعناوين:\n{heads}\n\nأخرج نص النشرة فقط.")
    body={"contents":[{"parts":[{"text":prompt}]}],
          "generationConfig":{"maxOutputTokens":2600,"temperature":0.4,"thinkingConfig":{"thinkingBudget":0}}}
    try:
        d=gemini_post(body, timeout=60)
        txt=d["candidates"][0]["content"]["parts"][0]["text"].strip()
        txt=re.sub(r"[\*#`]","",txt)
        if OPEN_L.split(".")[0] in txt and len(txt)>80:
            print("🧠 النشرة بقلم Gemini"); return txt
    except Exception as e: print(f"Gemini↘ القالب: {str(e)[:100]}")
    return None

if os.environ.get("VIDEO_ONLY"):
    try:
        _m=json.load(open(f"{OUT}/latest.json"))
        if _m.get("video_date")==today:
            print("✅ فيديو اليوم موجود — لا حاجة"); sys.exit(0)
        full=_m["script"]; print("🎬 وضع الفيديو فقط — استئناف نشرة اليوم")
    except Exception as e:
        print(f"لا توجد نشرة لليوم بعد: {str(e)[:60]}"); sys.exit(0)
else:
    full = gemini_script() or template_script()
open(f"{OUT}/script-{today}.txt","w").write(full); print("SCRIPT:",full)
json.dump({"date":today,"script":full,
    "audio":f"bulletin-{today}.mp3","video":"latest.mp4",
    "items":[{"head":i["head"],"src":i["src"],"grade":i["grade"]} for i in items[:12]]},
    open(f"{OUT}/latest.json","w"),ensure_ascii=False,indent=1)

# جُمل ≤٦٥ حرفًا (≈ ≤٤.٧ ثانية = تحت سقف الـ٥ث)
SEGLEN=int(os.environ.get("SEG_LEN","95"))
def split65(s):
    out=[]
    while len(s)>SEGLEN:
        cut=max(s.rfind("،",0,SEGLEN), s.rfind(" ",0,SEGLEN)); cut=cut if cut>20 else SEGLEN
        out.append(s[:cut].strip()); s=s[cut:].strip()
    if s: out.append(s)
    return out
body = full.replace(OPEN_L,"").replace(CLOSE_L,"").strip()
MAXSEG=int(os.environ.get("MAX_SEGMENTS","3"))
chunks=[c for c in split65(body)][:MAXSEG]
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

# ═══ الاحتياطي المدفوع: RunPod (لا يعمل إلا إذا نفدت الحصة المجانية) ═══
RP_KEY=os.environ.get("RUNPOD_API_KEY","")
RP_EP=os.environ.get("RUNPOD_ENDPOINT_ID","")
RP_BUDGET=int(os.environ.get("RUNPOD_MAX_SEGMENTS","3"))   # سقف يومي يحمي محفظتك

def rp_used_today():
    try:
        b=json.load(open(f"{OUT}/rp_budget.json"))
        return b.get("n",0) if b.get("day")==today else 0
    except Exception: return 0

def rp_bump():
    json.dump({"day":today,"n":rp_used_today()+1},
        open(f"{OUT}/rp_budget.json","w"),ensure_ascii=False)

def runpod_gen(ap,vp):
    """يولّد مقطعًا عبر RunPod — يُستدعى فقط بعد فشل المسارات المجانية."""
    if not (RP_KEY and RP_EP): raise RuntimeError("RunPod غير مهيّأ")
    used=rp_used_today()
    if used>=RP_BUDGET: raise RuntimeError(f"سقف RunPod اليومي ({RP_BUDGET}) مستهلَك")
    import base64 as _b64
    payload={"input":{
        "image": _b64.b64encode(open("pipeline/anchor_face.jpg","rb").read()).decode(),
        "audio": _b64.b64encode(open(ap,"rb").read()).decode(),
        "prompt": PROMPT, "resolution": "480p", "seed": 77}}
    req=urllib.request.Request(f"https://api.runpod.ai/v2/{RP_EP}/runsync",
        data=json.dumps(payload).encode(),
        headers={"Authorization":"Bearer "+RP_KEY,"Content-Type":"application/json"})
    d=json.load(urllib.request.urlopen(req,timeout=900))
    if d.get("status")!="COMPLETED": raise RuntimeError(f"RunPod: {str(d)[:120]}")
    out=d.get("output") or {}
    b64 = out.get("video_base64") or out.get("video") or out.get("output")
    if isinstance(b64,dict): b64=b64.get("video_base64") or b64.get("data")
    if isinstance(b64,str) and b64.startswith("http"):
        urllib.request.urlretrieve(b64,vp)
    elif isinstance(b64,str):
        open(vp,"wb").write(_b64.b64decode(b64))
    else: raise RuntimeError("RunPod: مخرج غير مفهوم")
    rp_bump()
    print(f"💳 RunPod أنتج المقطع ({used+1}/{RP_BUDGET} اليوم)")

def gen(ap,vp):
    global _lc,_ec
    try:
        _lc=_lc or _mk("victor/LongCat-Video-Avatar-1.5")
        r=_lc.predict(image_path=handle_file("pipeline/anchor_face.jpg"),audio_path=handle_file(ap),
            prompt=PROMPT,resolution=os.environ.get("VID_RES","480p"),seed=77,vocal_mode="Clean speech (fast)",
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
            both=f"{e} || {e2}"
            out_of_quota = ("quota" in both.lower()) or ("try again in" in both.lower())
            if RP_KEY and RP_EP:
                try:
                    print("↘ تحويل للاحتياطي المدفوع")
                    runpod_gen(ap,vp); return
                except Exception as e3:
                    print(f"RunPod تعذّر: {str(e3)[:110]}")
            if out_of_quota: raise QuotaOut(both[:300])
            raise
    v=r[0] if isinstance(r,(list,tuple)) else r
    if isinstance(v,dict): v=v.get("video") or v.get("path")
    shutil.copy(v,vp)

# ═══ النسخة الأولى: صوتٌ فقط — الفيديو مؤجَّل ═══
if not os.environ.get("ENABLE_VIDEO"):
    mark("rawi","ok","نشرة صوتية")
    bundle(); broadcast_bulletin(); broadcast_official(); broadcast_alerts(); broadcast_news(); save_agents()
    print("🎙️ النشرة الصوتية جاهزة — الفيديو معطَّل في هذه النسخة")
    sys.exit(0)

# ═══ إنتاج الفيديو: قابل للاستئناف وواعٍ بالحصة ═══
SEG=f"{OUT}/seg"; os.makedirs(SEG,exist_ok=True)
GPU=f"{OUT}/gpu.json"


def gpu_state():
    try: return json.load(open(GPU))
    except Exception: return {}

def gpu_blocked():
    g=gpu_state(); nx=g.get("next")
    if not nx: return False, 0
    try:
        left=(datetime.fromisoformat(nx)-datetime.now(timezone.utc)).total_seconds()
        return left>0, max(0,round(left/60))
    except Exception: return False, 0

def gpu_note(msg):
    """يلتقط «Try again in HH:MM:SS» ويخزّن موعد الإتاحة."""
    m=re.search(r"[Tt]ry again in (\d+):(\d+):(\d+)", msg or "")
    st={"at":datetime.now(timezone.utc).isoformat(timespec="minutes"),"msg":(msg or "")[:180]}
    if m:
        secs=int(m.group(1))*3600+int(m.group(2))*60+int(m.group(3))
        nxt=datetime.now(timezone.utc).timestamp()+secs
        st["next"]=datetime.fromtimestamp(nxt,timezone.utc).isoformat(timespec="minutes")
        st["wait_min"]=round(secs/60)
    json.dump(st,open(GPU,"w"),ensure_ascii=False,indent=1)

# مقاطع اليوم — تُبنى مرةً وتُستأنف عند العودة
need=[f"{SEG}/{today}-{i}.mp4" for i in range(1,len(chunks)+1)]
have=[p for p in need if os.path.exists(p) and os.path.getsize(p)>20000]
print(f"🎞️ مقاطع اليوم: {len(have)}/{len(need)} جاهزة")

blocked,mins = gpu_blocked()
if blocked and len(have)<len(need):
    print(f"⏳ حصة GPU تعود بعد ~{mins} دقيقة — تخطٍ بلا استهلاك محاولات")
    mark("rawi","skip",f"الفيديو بعد ~{mins}د · الصوت جاهز"); save_agents(); sys.exit(0)

made=0
try:
    for i,ch in enumerate(chunks,1):
        vp=f"{SEG}/{today}-{i}.mp4"
        if os.path.exists(vp) and os.path.getsize(vp)>20000:
            continue
        ap=f"{OUT}/n{i}.mp3"; asyncio.run(tts(ch,ap))
        subprocess.run(["ffmpeg","-v","quiet","-y","-i",ap,"-af","apad=pad_dur=0.3",ap+".p.mp3"])
        gen(ap+".p.mp3",vp); made+=1
        print(f"✅ مقطع {i}/{len(chunks)}")
        for f in (ap,ap+".p.mp3"):
            try: os.remove(f)
            except Exception: pass
except QuotaOut as q:
    gpu_note(str(q))
    _b,_m = gpu_blocked()
    done=sum(1 for p in need if os.path.exists(p) and os.path.getsize(p)>20000)
    _hh=round(_m/60,1) if _m>=60 else 0
    _when=f"~{_hh}س" if _hh else f"~{_m}د"
    print(f"⏳ نفدت الحصة بعد {made} مقطعًا ({done}/{len(need)} محفوظة) — تعود بعد {_when}، وتُستأنف تلقائيًا")
    mark("rawi","ok" if done else "skip",f"{done}/{len(need)} مقطعًا · يُستأنف بعد {_when}")
    save_agents(); sys.exit(0)
except Exception as e:
    print(f"⚠️ توليد الفيديو: {str(e)[:110]}")
    mark("rawi","fail",str(e)[:70]); save_agents(); sys.exit(0)

# اكتملت كل المقاطع → اللحام
try: os.remove(GPU)
except Exception: pass
parts=(["daily/opening.mp4"] if os.path.exists("daily/opening.mp4") else [])+need
if os.path.exists("daily/outro.mp4"): parts.append("daily/outro.mp4")
lst=f"{OUT}/list.txt"
with open(lst,"w") as f:
    for p in parts: f.write(f"file '{os.path.abspath(p)}'\n")
subprocess.run(["ffmpeg","-v","quiet","-y","-f","concat","-safe","0","-i",lst,"-c:v","libx264","-crf","20",
    "-pix_fmt","yuv420p","-c:a","aac","-movflags","+faststart",f"{OUT}/bulletin-{today}.mp4"])
shutil.copy(f"{OUT}/bulletin-{today}.mp4",f"{OUT}/latest.mp4")
meta=json.load(open(f"{OUT}/latest.json")); meta["video_date"]=today
json.dump(meta,open(f"{OUT}/latest.json","w"),ensure_ascii=False,indent=1)
mark("rawi","ok","فيديو اليوم مكتمل")
print(f"🎬 اكتمل الفيديو: bulletin-{today}.mp4 ({len(need)} مقطعًا)")

bundle()
broadcast_bulletin()
broadcast_official(); broadcast_alerts(); broadcast_news()
try: mark("rawi", _LOG.get("rawi",{}).get("status","ok"), _LOG.get("rawi",{}).get("note","نشرة اليوم")); save_agents()
except Exception: pass
