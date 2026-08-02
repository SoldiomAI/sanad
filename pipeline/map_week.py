# -*- coding: utf-8 -*-
"""Weekly authenticated-news map: per-country summaries for the world map UI."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = os.environ.get("SANAD_DAILY", "daily")
_KW = timezone(timedelta(hours=3))

# (iso2 matching assets/world.svg ids, AR name, EN name, aliases)
_WORLD = [
    ("kw", "الكويت", "Kuwait", ["الكويت", "كويتي", "الكويتية", "الكويتي"]),
    ("sa", "السعودية", "Saudi Arabia", ["السعودية", "سعودي", "الرياض", "جدة", "مكة", "الحجاز"]),
    ("ae", "الإمارات", "United Arab Emirates", ["الإمارات", "إماراتي", "أبوظبي", "دبي", "UAE"]),
    ("qa", "قطر", "Qatar", ["قطر", "قطري", "الدوحة"]),
    ("bh", "البحرين", "Bahrain", ["البحرين", "بحريني", "المنامة"]),
    ("om", "عُمان", "Oman", ["عمان", "عُمان", "مسقط", "عماني"]),
    ("iq", "العراق", "Iraq", ["العراق", "عراقي", "بغداد", "أربيل", "البصرة"]),
    ("ir", "إيران", "Iran", ["إيران", "إيراني", "طهران", "بوشهر", "هرمز"]),
    ("ye", "اليمن", "Yemen", ["اليمن", "يمني", "صنعاء", "الحوثي", "الحوثيين"]),
    ("ps", "فلسطين", "Palestine", ["فلسطين", "فلسطيني", "غزة", "القدس", "الضفة", "رفح", "حماس"]),
    ("il", "إسرائيل", "Israel", ["إسرائيل", "إسرائيلي", "تل أبيب", "نتانياهو", "الجيش الإسرائيلي"]),
    ("eg", "مصر", "Egypt", ["مصر", "مصري", "القاهرة", "سيناء"]),
    ("jo", "الأردن", "Jordan", ["الأردن", "أردني", "عمّان", "عمان الأردنية"]),
    ("lb", "لبنان", "Lebanon", ["لبنان", "لبناني", "بيروت", "حزب الله"]),
    ("sy", "سوريا", "Syria", ["سوريا", "سوري", "دمشق", "حلب"]),
    ("tr", "تركيا", "Turkey", ["تركيا", "تركي", "أنقرة", "إسطنبول"]),
    ("us", "أمريكا", "United States", ["أمريكا", "الولايات المتحدة", "واشنطن", "ترامب", "البنتاغون", "أمريكي", "USA", "U.S."]),
    ("gb", "بريطانيا", "United Kingdom", ["بريطانيا", "لندن", "البريطاني", "المملكة المتحدة", "UK"]),
    ("fr", "فرنسا", "France", ["فرنسا", "باريس", "فرنسي"]),
    ("de", "ألمانيا", "Germany", ["ألمانيا", "برلين", "ألماني"]),
    ("ru", "روسيا", "Russia", ["روسيا", "موسكو", "روسي", "بوتين"]),
    ("cn", "الصين", "China", ["الصين", "بكين", "صيني"]),
    ("in", "الهند", "India", ["الهند", "نيودلهي", "هندي"]),
    ("pk", "باكستان", "Pakistan", ["باكستان", "إسلام آباد", "باكستاني"]),
    ("af", "أفغانستان", "Afghanistan", ["أفغانستان", "كابل", "طالبان"]),
    ("ua", "أوكرانيا", "Ukraine", ["أوكرانيا", "كييف", "أوكراني"]),
    ("sd", "السودان", "Sudan", ["السودان", "خرطوم", "سوداني"]),
    ("ly", "ليبيا", "Libya", ["ليبيا", "طرابلس", "ليبي"]),
    ("tn", "تونس", "Tunisia", ["تونس", "تونسي"]),
    ("dz", "الجزائر", "Algeria", ["الجزائر", "جزائري"]),
    ("ma", "المغرب", "Morocco", ["المغرب", "مغربي", "الرباط"]),
    ("so", "الصومال", "Somalia", ["الصومال", "صومالي", "مقديشو"]),
    ("et", "إثيوبيا", "Ethiopia", ["إثيوبيا", "أديس أبابا"]),
    ("ss", "جنوب السودان", "South Sudan", ["جنوب السودان"]),
    ("cd", "الكونغو", "DR Congo", ["الكونغو", "كينشاسا"]),
    ("ng", "نيجيريا", "Nigeria", ["نيجيريا", "أبوجا"]),
    ("za", "جنوب أفريقيا", "South Africa", ["جنوب أفريقيا", "بريتوريا"]),
    ("br", "البرازيل", "Brazil", ["البرازيل", "برازيلي"]),
    ("jp", "اليابان", "Japan", ["اليابان", "طوكيو", "ياباني"]),
    ("kr", "كوريا الجنوبية", "South Korea", ["كوريا الجنوبية", "سيول"]),
    ("kp", "كوريا الشمالية", "North Korea", ["كوريا الشمالية", "بيونغ يانغ"]),
    ("au", "أستراليا", "Australia", ["أستراليا", "كانبرا"]),
    ("ca", "كندا", "Canada", ["كندا", "أوتاوا", "كندي"]),
    ("mx", "المكسيك", "Mexico", ["المكسيك", "مكسيكي"]),
    ("ar", "الأرجنتين", "Argentina", ["الأرجنتين"]),
    ("es", "إسبانيا", "Spain", ["إسبانيا", "مدريد"]),
    ("it", "إيطاليا", "Italy", ["إيطاليا", "روما"]),
    ("gr", "اليونان", "Greece", ["اليونان", "أثينا"]),
    ("cy", "قبرص", "Cyprus", ["قبرص"]),
    ("mt", "مالطا", "Malta", ["مالطا"]),
    ("ch", "سويسرا", "Switzerland", ["سويسرا", "جنيف"]),
    ("se", "السويد", "Sweden", ["السويد"]),
    ("no", "النرويج", "Norway", ["النرويج"]),
    ("nl", "هولندا", "Netherlands", ["هولندا", "أمستردام"]),
    ("be", "بلجيكا", "Belgium", ["بلجيكا", "بروكسل"]),
    ("pl", "بولندا", "Poland", ["بولندا", "وارسو"]),
    ("ro", "رومانيا", "Romania", ["رومانيا"]),
    ("hu", "هنغاريا", "Hungary", ["هنغاريا", "المجر"]),
    ("cz", "التشيك", "Czechia", ["التشيك", "براغ"]),
    ("at", "النمسا", "Austria", ["النمسا", "فيينا"]),
    ("pt", "البرتغال", "Portugal", ["البرتغال"]),
    ("ie", "أيرلندا", "Ireland", ["أيرلندا", "دبلن"]),
    ("fi", "فنلندا", "Finland", ["فنلندا"]),
    ("dk", "الدنمارك", "Denmark", ["الدنمارك"]),
    ("is", "آيسلندا", "Iceland", ["آيسلندا"]),
    ("nz", "نيوزيلندا", "New Zealand", ["نيوزيلندا"]),
    ("sg", "سنغافورة", "Singapore", ["سنغافورة"]),
    ("my", "ماليزيا", "Malaysia", ["ماليزيا"]),
    ("id", "إندونيسيا", "Indonesia", ["إندونيسيا", "جاكرتا"]),
    ("th", "تايلاند", "Thailand", ["تايلاند", "بانكوك"]),
    ("vn", "فيتنام", "Vietnam", ["فيتنام"]),
    ("ph", "الفلبين", "Philippines", ["الفلبين"]),
    ("bd", "بنغلاديش", "Bangladesh", ["بنغلاديش"]),
    ("lk", "سريلانكا", "Sri Lanka", ["سريلانكا"]),
    ("np", "نيبال", "Nepal", ["نيبال"]),
    ("mm", "ميانمار", "Myanmar", ["ميانمار", "بورما"]),
    ("kz", "كازاخستان", "Kazakhstan", ["كازاخستان"]),
    ("uz", "أوزبكستان", "Uzbekistan", ["أوزبكستان"]),
    ("tm", "تركمانستان", "Turkmenistan", ["تركمانستان"]),
    ("az", "أذربيجان", "Azerbaijan", ["أذربيجان", "باكو"]),
    ("am", "أرمينيا", "Armenia", ["أرمينيا"]),
    ("ge", "جورجيا", "Georgia", ["جورجيا", "تبليسي"]),
    ("by", "بيلاروس", "Belarus", ["بيلاروس", "روسيا البيضاء"]),
    ("md", "مولدوفا", "Moldova", ["مولدوفا"]),
    ("ba", "البوسنة", "Bosnia", ["البوسنة"]),
    ("rs", "صربيا", "Serbia", ["صربيا"]),
    ("hr", "كرواتيا", "Croatia", ["كرواتيا"]),
    ("al", "ألبانيا", "Albania", ["ألبانيا"]),
    ("xk", "كوسوفو", "Kosovo", ["كوسوفو"]),
    ("mk", "مقدونيا الشمالية", "North Macedonia", ["مقدونيا"]),
    ("bg", "بلغاريا", "Bulgaria", ["بلغاريا"]),
    ("cu", "كوبا", "Cuba", ["كوبا"]),
    ("ve", "فنزويلا", "Venezuela", ["فنزويلا"]),
    ("co", "كولومبيا", "Colombia", ["كولومبيا"]),
    ("pe", "بيرو", "Peru", ["بيرو"]),
    ("cl", "تشيلي", "Chile", ["تشيلي"]),
    ("ec", "الإكوادور", "Ecuador", ["الإكوادور"]),
    ("bo", "بوليفيا", "Bolivia", ["بوليفيا"]),
    ("py", "باراغواي", "Paraguay", ["باراغواي"]),
    ("uy", "أوروغواي", "Uruguay", ["أوروغواي"]),
    ("ke", "كينيا", "Kenya", ["كينيا", "نيروبي"]),
    ("tz", "تنزانيا", "Tanzania", ["تنزانيا"]),
    ("ug", "أوغندا", "Uganda", ["أوغندا"]),
    ("rw", "رواندا", "Rwanda", ["رواندا"]),
    ("gh", "غانا", "Ghana", ["غانا"]),
    ("ci", "ساحل العاج", "Ivory Coast", ["ساحل العاج", "كوت ديفوار"]),
    ("sn", "السنغال", "Senegal", ["السنغال"]),
    ("mr", "موريتانيا", "Mauritania", ["موريتانيا"]),
    ("ml", "مالي", "Mali", ["مالي "]),
    ("ne", "النيجر", "Niger", ["النيجر"]),
    ("td", "تشاد", "Chad", ["تشاد"]),
    ("cm", "الكاميرون", "Cameroon", ["الكاميرون"]),
    ("ao", "أنغولا", "Angola", ["أنغولا"]),
    ("mz", "موزمبيق", "Mozambique", ["موزمبيق"]),
    ("zw", "زيمبابوي", "Zimbabwe", ["زيمبابوي"]),
    ("na", "ناميبيا", "Namibia", ["ناميبيا"]),
    ("bw", "بوتسوانا", "Botswana", ["بوتسوانا"]),
    ("mg", "مدغشقر", "Madagascar", ["مدغشقر"]),
    ("mu", "موريشيوس", "Mauritius", ["موريشيوس"]),
    ("sc", "سيشل", "Seychelles", ["سيشل"]),
    ("dj", "جيبوتي", "Djibouti", ["جيبوتي"]),
    ("er", "إريتريا", "Eritrea", ["إريتريا"]),
    ("km", "جزر القمر", "Comoros", ["جزر القمر"]),
    ("ht", "هايتي", "Haiti", ["هايتي"]),
    ("do", "الدومينيكان", "Dominican Republic", ["الدومينيكان"]),
    ("pa", "بنما", "Panama", ["بنما"]),
    ("cr", "كوستاريكا", "Costa Rica", ["كوستاريكا"]),
    ("gt", "غواتيمالا", "Guatemala", ["غواتيمالا"]),
    ("hn", "هندوراس", "Honduras", ["هندوراس"]),
    ("sv", "السلفادور", "El Salvador", ["السلفادور"]),
    ("ni", "نيكاراغوا", "Nicaragua", ["نيكاراغوا"]),
    ("tw", "تايوان", "Taiwan", ["تايوان"]),
    ("hk", "هونغ كونغ", "Hong Kong", ["هونغ كونغ", "هونج كونج"]),
    ("mo", "ماكاو", "Macau", ["ماكاو"]),
]


def _auth(it: dict) -> bool:
    return bool(it.get("isnad") and it.get("grade") in ("صحيح", "حسن"))


def _hit(txt: str, aliases) -> bool:
    t = str(txt or "")
    if not t:
        return False
    tl = t.lower()
    for a in aliases:
        if not a:
            continue
        if a.lower() in tl or a in t:
            return True
    return False


def _item_blob(it: dict) -> str:
    return " ".join(
        str(it.get(k) or "")
        for k in ("head", "he", "src", "cat", "via")
    )


def _parse_at(iso: str):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except Exception:
        return None


def collect_week_items(days: int = 7):
    """Authenticated items from today + archive snaps covering the last `days`."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    seen = set()
    out = []

    def add_from_cats(cats, stamp=""):
        for cat, arr in (cats or {}).items():
            for it in arr or []:
                if not _auth(it):
                    continue
                at = _parse_at(it.get("at") or "")
                if at and at < cutoff:
                    continue
                key = (it.get("link") or "")[:180] or (it.get("head") or "")[:120]
                if key in seen:
                    continue
                seen.add(key)
                d = dict(it)
                d["cat"] = cat
                d["_snap"] = stamp
                out.append(d)

    # today
    try:
        news = json.loads(Path(OUT, "news.json").read_text())
        add_from_cats(news.get("cats"), "today")
    except Exception:
        pass

    # archives — newest first, keep one snap per calendar day
    idx_path = Path(OUT, "archive", "index.json")
    try:
        snaps = (json.loads(idx_path.read_text()).get("snaps") or [])[-80:]
    except Exception:
        snaps = []
    days_have = set()
    for s in reversed(snaps):
        sid = s.get("id") or ""
        day = sid[:10]
        if not re.match(r"\d{4}-\d{2}-\d{2}", day):
            continue
        try:
            if datetime.fromisoformat(day).replace(tzinfo=timezone.utc) < cutoff - timedelta(days=1):
                continue
        except Exception:
            continue
        if day in days_have:
            continue
        path = Path(OUT, "archive", f"{sid}.json")
        if not path.exists():
            continue
        try:
            snap = json.loads(path.read_text())
        except Exception:
            continue
        add_from_cats(snap.get("cats"), sid)
        days_have.add(day)
        if len(days_have) >= days:
            break

    return out


def _summary_ar(name: str, n: int, sahih: int, hasan: int, tops: list) -> str:
    if n <= 0:
        return f"لا أخبار مُسنَدة عن {name} خلال آخر أسبوع في حصيلة سَنَد."
    grade_bit = []
    if sahih:
        grade_bit.append(f"{sahih} صحيح")
    if hasan:
        grade_bit.append(f"{hasan} حسن")
    g = " و".join(grade_bit) if grade_bit else f"{n} خبرًا مُسنَدًا"
    lead = tops[0]["head"] if tops else ""
    more = f" أبرزها: «{lead}»." if lead else ""
    return f"خلال آخر أسبوع رصد سَنَد {n} خبرًا مُسنَدًا عن {name} ({g}).{more}"


def _summary_en(en: str, n: int, sahih: int, hasan: int, tops: list) -> str:
    if n <= 0:
        return f"No authenticated Sanad stories on {en} in the last week."
    bits = []
    if sahih:
        bits.append(f"{sahih} verified")
    if hasan:
        bits.append(f"{hasan} credible")
    g = " · ".join(bits) if bits else f"{n} graded"
    lead = ""
    if tops:
        lead = (tops[0].get("he") or "").strip()
        if not lead:
            h = (tops[0].get("head") or "").strip()
            if h and not re.search(r"[\u0600-\u06FF]", h):
                lead = h
    more = f" Lead: “{lead}”." if lead else ""
    return f"Over the last week Sanad graded {n} stories on {en} ({g}).{more}"


def build_map_week(days: int = 7) -> dict:
    items = collect_week_items(days)
    countries = []
    for cid, name, en, aliases in _WORLD:
        matched = [i for i in items if _hit(_item_blob(i), aliases + [name, en])]
        # Prefer Palestine over Israel when both tags match Gaza/Palestine-heavy items:
        # already handled by alias lists; dual matches OK (same story can appear in both).
        matched = sorted(
            matched,
            key=lambda i: (
                3 if i.get("grade") == "صحيح" else 2,
                str(i.get("at") or ""),
                i.get("score") or 0,
            ),
            reverse=True,
        )
        sahih = sum(1 for i in matched if i.get("grade") == "صحيح")
        hasan = sum(1 for i in matched if i.get("grade") == "حسن")
        tops = matched[:8]
        n = len(matched)
        heat = min(100, sahih * 18 + hasan * 8 + min(40, n * 3))
        countries.append(
            {
                "id": cid,
                "name": name,
                "en": en,
                "n": n,
                "sahih": sahih,
                "hasan": hasan,
                "heat": heat,
                "summary": _summary_ar(name, n, sahih, hasan, tops),
                "summary_en": _summary_en(en, n, sahih, hasan, tops),
                "stories": [
                    {
                        "head": x.get("head") or "",
                        "he": x.get("he") or "",
                        "grade": x.get("grade") or "",
                        "src": x.get("src") or "",
                        "link": x.get("link") or "",
                        "at": x.get("at") or "",
                        "score": x.get("score"),
                        "isnad": x.get("isnad") or {},
                    }
                    for x in tops
                ],
            }
        )
    countries.sort(key=lambda c: (-c["heat"], -c["n"], c["id"]))
    active = sum(1 for c in countries if c["n"] > 0)
    out = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "days": days,
        "note": "ملخص أسبوعي للأخبار المُسنَدة (صحيح/حسن) حسب الدولة — من حصيلة سَنَد والأرشيف",
        "total_stories": len(items),
        "active_countries": active,
        "countries": countries,
    }
    Path(OUT).mkdir(parents=True, exist_ok=True)
    Path(OUT, "map.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"🗺️ الخريطة: {active}/{len(countries)} دولةً نشطة · {len(items)} خبرًا مُسنَدًا / {days} أيام")
    return out


def map_week():
    return build_map_week(7)


if __name__ == "__main__":
    m = map_week()
    print(json.dumps({k: m.get(k) for k in ("updated", "total_stories", "active_countries", "days")}, ensure_ascii=False))
