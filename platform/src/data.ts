// طبقة البيانات: نفس منبع isnad.news — مستودع sanad-data العام.
// كلُّ ما يصل من هنا بياناتٌ حقيقيّةٌ من أنبوب سَنَد المُسنَد؛ لا تُختلَق قيمٌ هنا أبدًا.
const RAW = "https://raw.githubusercontent.com/Soldiom/sanad-data/main/daily/";

export interface CountryTension {
  id: string; name: string; en: string; lat: number; lon: number;
  score: number; level: string; delta: number;
  parts: { n: number; u: number; w: number; a: number; r: number; o: number };
  events: { h: string; g: string; u: string; at: string; src: string }[];
}
export interface Tension {
  updated: string; note: string; formula: string; countries: CountryTension[];
}
export interface NewsItem {
  head: string; src: string; grade: string; at: string; link: string;
  he?: string; img?: string; w?: number; cat: string;
}
export interface Alert { kind: string; body: string; txt: string; act?: string; u?: string; when?: string }
export interface Rumor { claim: string; verdict: string; qail?: string; why?: string; first_seen?: string }
export interface Bundle {
  built?: string;
  news?: { updated?: string; cats?: Record<string, Omit<NewsItem, "cat">[]> };
  alerts?: { updated?: string; list?: Alert[] };
  rumors?: { updated?: string; items?: Rumor[] };
  official?: { updated?: string; wired?: string; src?: unknown[] };
  forecast?: { updated?: string };
  analyst?: { updated?: string };
  column?: { updated?: string };
  tension?: Tension;
  agents?: { updated?: string; healthy?: number; total?: number };
}

async function j<T>(name: string): Promise<T | null> {
  try {
    const r = await fetch(RAW + name + ".json?t=" + Math.floor(Date.now() / 60000));
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch { return null; }
}

export async function loadAll(): Promise<{ bundle: Bundle; tension: Tension | null }> {
  const bundle = (await j<Bundle>("bundle")) || {};
  // tension قد لا يكون في الحزمة بعدُ أوّلَ يوم — نجلبه مباشرةً كاحتياط
  const tension = bundle.tension || (await j<Tension>("tension"));
  return { bundle, tension: tension || null };
}

export function flatNews(b: Bundle): NewsItem[] {
  const out: NewsItem[] = [];
  const cats = b.news?.cats || {};
  for (const [cat, list] of Object.entries(cats))
    for (const it of list || []) out.push({ ...(it as Omit<NewsItem, "cat">), cat });
  out.sort((x, y) => String(y.at || "").localeCompare(String(x.at || "")));
  return out;
}

export function ageMin(iso?: string): number | null {
  if (!iso) return null;
  const ms = Date.now() - new Date(iso).getTime();
  return isFinite(ms) ? Math.max(0, Math.round(ms / 60000)) : null;
}
