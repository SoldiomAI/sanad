export type Lng = "ar" | "en";
export let LNG: Lng = (localStorage.getItem("mirsad-lng") as Lng) || "ar";

const S: Record<string, { ar: string; en: string }> = {
  beta: { ar: "تجريبي", en: "beta" },
  idx: { ar: "مؤشّرُ عدم الاستقرار", en: "Instability Index" },
  alr: { ar: "تحذيراتٌ رسمية", en: "Official Warnings" },
  feed: { ar: "الخلاصةُ المُسنَدة", en: "Verified Feed" },
  rum: { ar: "تحت المِجهر", en: "Under the Microscope" },
  frs: { ar: "مرقابُ الطزاجة", en: "Freshness Monitor" },
  disc: {
    ar: "مؤشرٌ حسابيٌّ شفّافٌ من موادَّ مُسنَدةٍ وحدَها — ليس تقييمًا استخباراتيًّا رسميًّا. الأحكامُ للمصادر لا للانتشار.",
    en: "A transparent, purely computed index from chain-verified material only — not an official intelligence assessment. Verdicts belong to sources, never to virality.",
  },
  calm: { ar: "هادئ", en: "calm" },
  watch: { ar: "مترقّب", en: "watchful" },
  tense: { ar: "متوتّر", en: "tense" },
  crit: { ar: "حرج", en: "critical" },
  events: { ar: "موادُّ اليومِ المُسنَدة", en: "Today's verified items" },
  parts: { ar: "تفكيكُ الرقم (إسنادُه)", en: "Score breakdown (its isnad)" },
  p_u: { ar: "عاجل", en: "urgent" },
  p_w: { ar: "ألفاظ تصعيد", en: "escalation terms" },
  p_a: { ar: "تحذيرات", en: "warnings" },
  p_r: { ar: "شائعات", en: "rumors" },
  p_n: { ar: "أخبار", en: "news" },
  p_o: { ar: "بيانات رسمية", en: "official statements" },
  updated: { ar: "آخر حساب", en: "computed" },
  ago_m: { ar: "قبل %s د", en: "%sm ago" },
  ago_h: { ar: "قبل %s س", en: "%sh ago" },
  src: { ar: "المصدر", en: "source" },
  noal: { ar: "لا تحذيراتَ ساريةً الآن — وهذا خبرٌ طيّب.", en: "No active warnings — good news." },
  qail: { ar: "قائلُها", en: "claimed by" },
  formula: { ar: "الصيغة", en: "formula" },
  all: { ar: "الكلّ", en: "All" },
};

export function t(k: string, arg?: string | number): string {
  const e = S[k];
  let s = e ? e[LNG] : k;
  if (arg !== undefined) s = s.replace("%s", String(arg));
  return s;
}

export function flipLng(): void {
  LNG = LNG === "ar" ? "en" : "ar";
  localStorage.setItem("mirsad-lng", LNG);
  location.reload();
}

export function applyDir(): void {
  document.documentElement.lang = LNG;
  document.documentElement.dir = LNG === "ar" ? "rtl" : "ltr";
  document.querySelectorAll<HTMLElement>("[data-i]").forEach((el) => {
    el.textContent = t(el.dataset.i as string);
  });
  const b = document.getElementById("lngBtn");
  if (b) b.textContent = LNG === "ar" ? "EN" : "ع";
}

export const LEVEL_KEY: Record<string, string> = {
  "هادئ": "calm", "مترقّب": "watch", "متوتّر": "tense", "حرج": "crit",
};
