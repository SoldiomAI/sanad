// الكرةُ الأرضية — globe.gl بلا أيّ أصولٍ خارجية: كرةٌ داكنةٌ سياديةٌ
// تُلوَّن مضلّعاتُ دولِ المِقياس بمستوياتها، والنقاطُ أعمدةُ ضوءٍ بالمؤشر.
import Globe from "globe.gl";
import type { Tension, CountryTension } from "./data";
import { WORLD_URL } from "./data";
import { BAND } from "./map";

const A3: Record<string, string> = {
  kw: "KWT", sa: "SAU", ae: "ARE", qa: "QAT", bh: "BHR",
  om: "OMN", iq: "IRQ", ir: "IRN", ye: "YEM", ps: "PSE",
};

export interface GlobeApi { start(): void; stop(): void }

export async function initGlobe(el: HTMLElement, tension: Tension | null,
  onPick: (c: CountryTension) => void): Promise<GlobeApi> {
  const world = await fetch(WORLD_URL).then((r) => r.json());
  const byA3 = new Map<string, CountryTension>();
  for (const c of tension?.countries || []) byA3.set(A3[c.id] || "", c);

  const g = new Globe(el, { animateIn: false })
    .backgroundColor("#0A0E16")
    .showAtmosphere(true)
    .atmosphereColor("#C9A227")
    .atmosphereAltitude(0.12)
    .globeImageUrl(null as unknown as string)
    .polygonsData(world.features)
    .polygonCapColor((f: { properties?: { adm0_a3?: string } }) => {
      const c = byA3.get(f.properties?.adm0_a3 || "");
      return c ? BAND(c.score) + "CC" : "#1A2236";
    })
    .polygonSideColor(() => "#0E1422")
    .polygonStrokeColor(() => "#2B3550")
    .polygonAltitude((f: { properties?: { adm0_a3?: string } }) =>
      byA3.has(f.properties?.adm0_a3 || "") ? 0.012 : 0.004)
    .onPolygonClick((f: { properties?: { adm0_a3?: string } }) => {
      const c = byA3.get(f.properties?.adm0_a3 || "");
      if (c) onPick(c);
    })
    .pointsData(tension?.countries || [])
    .pointLat((o: object) => (o as CountryTension).lat)
    .pointLng((o: object) => (o as CountryTension).lon)
    .pointColor((o: object) => BAND((o as CountryTension).score))
    .pointAltitude((o: object) => 0.02 + (o as CountryTension).score / 260)
    .pointRadius(0.42)
    .onPointClick((o: object) => onPick(o as CountryTension))
    .pointLabel((o: object) => {
      const c = o as CountryTension;
      return `<div style="font:600 11px 'Noto Kufi Arabic';color:#E9E4D8">${c.name} · ${c.score}/100</div>`;
    });

  const mat = g.globeMaterial() as { color: { set(c: string): void } };
  mat.color.set("#0D1322");
  g.pointOfView({ lat: 26, lng: 48, altitude: 1.7 }, 0);

  const ctl = g.controls() as { autoRotate: boolean; autoRotateSpeed: number };
  ctl.autoRotateSpeed = 0.55;
  const rm = matchMedia("(prefers-reduced-motion: reduce)").matches;
  return {
    start() { ctl.autoRotate = !rm; g.resumeAnimation?.(); },
    stop() { ctl.autoRotate = false; g.pauseAnimation?.(); },
  };
}
