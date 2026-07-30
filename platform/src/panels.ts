// اللوحاتُ الجانبية وبطاقةُ الدولة — كلُّ نصٍّ من البيانات يمرُّ بـesc/safeUrl حصرًا.
import { esc, safeUrl } from "./esc";
import { t, LNG, LEVEL_KEY } from "./i18n";
import { BAND } from "./map";
import type { Bundle, Tension, CountryTension } from "./data";
import { flatNews, ageMin } from "./data";

const $ = (id: string) => document.getElementById(id) as HTMLElement;
const nm = (c: CountryTension) => (LNG === "en" ? c.en : c.name);
const lvl = (c: CountryTension) => t(LEVEL_KEY[c.level] || "calm");
const G_CLS: Record<string, string> = { "صحيح": "s", "حسن": "h" };
const G_EN: Record<string, string> = { "صحيح": "Verified ✓", "حسن": "Credible", "ضعيف الإسناد": "Weak chain" };
const gchip = (g: string) =>
  `<span class="g ${G_CLS[g] || "d"}">${esc(LNG === "en" ? G_EN[g] || g : g)}</span>`;
const agoTxt = (iso?: string) => {
  const m = ageMin(iso);
  if (m == null) return "";
  return m < 90 ? t("ago_m", m) : t("ago_h", Math.round(m / 6) / 10);
};

export function renderPulse(b: Bundle, tension: Tension | null): void {
  const m = ageMin(tension?.updated || b.built);
  $("pulse").textContent = m == null ? "" :
    (LNG === "en"
      ? `🌡️ index computed ${t("ago_m", m)} · ${b.agents?.healthy ?? "–"}/${b.agents?.total ?? "–"} agents healthy`
      : `🌡️ ${t("updated")} ${t("ago_m", m)} · ${b.agents?.healthy ?? "–"}/${b.agents?.total ?? "–"} وكيلًا سليمًا`);
}

export function renderIndex(tension: Tension | null, sel: string | null,
  onPick: (c: CountryTension) => void): void {
  const L = $("idxL"); L.innerHTML = "";
  for (const c of tension?.countries || []) {
    const row = document.createElement("div");
    row.className = "crow" + (sel === c.id ? " on" : "");
    const d = c.delta || 0;
    row.innerHTML =
      `<span class="nm">${esc(nm(c))}</span>
       <span class="bar"><i style="width:${Math.max(3, c.score)}%;background:${BAND(c.score)}"></i></span>
       <span class="sc" style="color:${BAND(c.score)}">${c.score}</span>
       <span class="dl ${d > 0 ? "up" : d < 0 ? "dn" : ""}">${d > 0 ? "▲" + d : d < 0 ? "▼" + -d : "–"}</span>`;
    row.onclick = () => onPick(c);
    L.appendChild(row);
  }
  $("idxNote").textContent =
    (LNG === "en" ? "formula: " : t("formula") + ": ") + (tension?.formula || "");
}

export function renderDetail(c: CountryTension | null): void {
  const D = $("detail");
  if (!c) { D.style.display = "none"; return; }
  const p = c.parts;
  const parts: [string, number][] = [
    [t("p_u"), p.u], [t("p_w"), p.w], [t("p_a"), p.a],
    [t("p_r"), p.r], [t("p_n"), p.n], [t("p_o"), p.o],
  ];
  D.innerHTML =
    `<span class="x" id="dx">✕</span>
     <h2>${esc(nm(c))}
       <span class="score" style="color:${BAND(c.score)}">${c.score}/100 · ${esc(lvl(c))}</span></h2>
     <div class="evh">${esc(t("parts"))}</div>
     <div class="chips">${parts.map(([k, v]) => `<span class="chip">${esc(k)} <b>${v}</b></span>`).join("")}</div>
     ${c.events.length ? `<div class="evh">${esc(t("events"))}</div>` +
       c.events.map((e) =>
         `<div class="ev"><a href="${safeUrl(e.u)}" target="_blank" rel="noopener">${esc(e.h)}</a>
          <div class="m">${gchip(e.g)}<span>${esc(e.src || "")}</span><span>${esc(agoTxt(e.at))}</span></div></div>`).join("") : ""}`;
  D.style.display = "block";
  (document.getElementById("dx") as HTMLElement).onclick = () => renderDetail(null);
}

export function renderAlerts(b: Bundle): void {
  const list = b.alerts?.list || [];
  $("alrL").innerHTML = list.length
    ? list.slice(0, 6).map((a) =>
        `<div class="al"><span class="b">${esc(a.body)}${a.when ? " · " + esc(a.when) : ""}</span><br>
         ${esc(a.txt)}${a.u ? ` <a href="${safeUrl(a.u)}" target="_blank" rel="noopener">↗</a>` : ""}</div>`).join("")
    : `<div class="note">${esc(t("noal"))}</div>`;
}

export function renderFeed(b: Bundle): void {
  const items = flatNews(b).slice(0, 22);
  $("feedL").innerHTML = items.map((i) => {
    const head = LNG === "en" ? i.he || i.head : i.head;
    return `<div class="fi"><a href="${safeUrl(i.link)}" target="_blank" rel="noopener">${esc(head)}</a>
      <div class="m">${gchip(i.grade)}<span>${esc(i.src || "")}</span>
      ${i.w ? `<span>⛓ ${i.w}</span>` : ""}<span>${esc(agoTxt(i.at))}</span></div></div>`;
  }).join("");
}

export function renderRumors(b: Bundle): void {
  const V_CLS: Record<string, string> = { "صحّ": "t", "لم يصحّ": "f" };
  const V_EN: Record<string, string> = { "صحّ": "true", "لم يصحّ": "false", "قيد التحقق": "unverified" };
  const items = (b.rumors?.items || []).slice(0, 6);
  $("rumL").innerHTML = items.map((r) =>
    `<div class="ru"><span class="v ${V_CLS[r.verdict] || "o"}">${esc(LNG === "en" ? V_EN[r.verdict] || r.verdict : r.verdict)}</span>
     ${esc(r.claim)}${r.qail ? `<div class="q">🗣 ${esc(t("qail"))}: ${esc(r.qail)}</div>` : ""}</div>`).join("");
}

export function renderFresh(b: Bundle, tension: Tension | null): void {
  const rows: [string, string | undefined][] = [
    [LNG === "en" ? "News" : "الأخبار", b.news?.updated],
    [LNG === "en" ? "Official" : "من المَنبع", b.official?.wired || b.official?.updated],
    [LNG === "en" ? "Warnings" : "التحذيرات", (b.alerts as { wired?: string; updated?: string } | undefined)?.wired || b.alerts?.updated],
    [LNG === "en" ? "Rumors" : "الشائعات", b.rumors?.updated],
    [LNG === "en" ? "Index" : "المؤشر", tension?.updated],
    [LNG === "en" ? "Column" : "عمود الجريدة", b.column?.updated],
  ];
  $("frsL").innerHTML = rows.map(([k, iso]) => {
    const m = ageMin(iso);
    const col = m == null ? "#6B7488" : m <= 45 ? "#3E9B72" : m <= 240 ? "#C9A227" : "#C34250";
    return `<div class="fr"><span class="dot" style="background:${col}"></span>
      <span>${esc(k)}</span><span class="ag">${m == null ? "—" : esc(agoTxt(iso))}</span></div>`;
  }).join("");
}
