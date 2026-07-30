// المُهرِّب المركزي: كلُّ نصٍّ قادمٍ من البيانات يمرُّ من هنا قبل أيّ حقنٍ في DOM،
// وكلُّ رابطٍ يُقيَّد بـ http(s) — نفس عقيدة isnad.news.
export function esc(s: unknown): string {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string),
  );
}
export function safeUrl(u: unknown): string {
  const s = String(u == null ? "" : u).trim();
  return /^https?:\/\//i.test(s) ? s.replace(/"/g, "%22") : "#";
}
