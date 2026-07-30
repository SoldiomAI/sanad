// الخريطة المسطّحة — MapLibre GL بلا بلاطاتٍ خارجيةٍ ولا مفاتيح:
// حدودُ الدول من Natural Earth (ملكٌ عام، مضمَّنةٌ في المستودع) + طبقاتُنا المُسنَدة.
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Tension, CountryTension } from "./data";
import { WORLD_URL } from "./data";
import { esc } from "./esc";

// ربطُ دولِ المِقياس بأكواد Natural Earth (adm0_a3)
const A3: Record<string, string> = {
  kw: "KWT", sa: "SAU", ae: "ARE", qa: "QAT", bh: "BHR",
  om: "OMN", iq: "IRQ", ir: "IRN", ye: "YEM", ps: "PSE",
};
export const BAND = (s: number): string =>
  s >= 75 ? "#9E2B37" : s >= 50 ? "#D07A2E" : s >= 25 ? "#C9A227" : "#3E9B72";

export interface MapApi { fly(c: CountryTension): void; resize(): void }

export function initFlat(el: HTMLElement, tension: Tension | null,
  onPick: (c: CountryTension) => void): MapApi {
  const byA3 = new Map<string, CountryTension>();
  for (const c of tension?.countries || []) byA3.set(A3[c.id] || "", c);

  const map = new maplibregl.Map({
    container: el,
    style: {
      version: 8,
      glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
      sources: { world: { type: "geojson", data: WORLD_URL } },
      layers: [
        { id: "bg", type: "background", paint: { "background-color": "#0A0E16" } },
        {
          id: "land", type: "fill", source: "world",
          paint: { "fill-color": "#161D2E", "fill-outline-color": "#232C40" },
        },
        {
          id: "hot", type: "fill", source: "world",
          filter: ["in", ["get", "adm0_a3"], ["literal", Object.values(A3)]],
          paint: { "fill-color": "#161D2E", "fill-opacity": 0.9 },
        },
        {
          id: "line", type: "line", source: "world",
          paint: { "line-color": "#2B3550", "line-width": 0.6 },
        },
      ],
    },
    center: [48, 27], zoom: 4.1, minZoom: 2, maxZoom: 9,
    attributionControl: { compact: true, customAttribution: "حدود: Natural Earth (ملك عام)" },
  });

  map.on("load", () => {
    // choropleth عدم الاستقرار — تعبيرُ مطابقةٍ مبنيٌّ من بيانات المِقياس الحقيقية
    if (byA3.size) {
      const expr: unknown[] = ["match", ["get", "adm0_a3"]];
      for (const [a3, c] of byA3) { if (a3) { expr.push(a3, BAND(c.score)); } }
      expr.push("#161D2E");
      map.setPaintProperty("hot", "fill-color", expr as never);
      map.setPaintProperty("hot", "fill-opacity", 0.55 as never);
    }
    // نقاطُ الدول: حجمُها بالمؤشر، ونقرتُها تفتح بطاقةَ الإسناد
    const feats = (tension?.countries || []).map((c) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [c.lon, c.lat] },
      properties: { id: c.id, score: c.score },
    }));
    map.addSource("dots", { type: "geojson", data: { type: "FeatureCollection", features: feats } });
    map.addLayer({
      id: "dots", type: "circle", source: "dots",
      paint: {
        "circle-radius": ["+", 5, ["*", 0.13, ["get", "score"]]],
        "circle-color": ["case", [">=", ["get", "score"], 75], "#9E2B37",
          [">=", ["get", "score"], 50], "#D07A2E",
          [">=", ["get", "score"], 25], "#C9A227", "#3E9B72"],
        "circle-opacity": 0.8, "circle-stroke-width": 1.4, "circle-stroke-color": "#0A0E16",
      },
    });
    const pick = (e: maplibregl.MapLayerMouseEvent) => {
      const id = e.features?.[0]?.properties?.id as string | undefined;
      const c = (tension?.countries || []).find((x) => x.id === id);
      if (c) onPick(c);
    };
    map.on("click", "dots", pick);
    map.on("click", "hot", (e) => {
      const a3 = e.features?.[0]?.properties?.adm0_a3 as string | undefined;
      const c = a3 ? byA3.get(a3) : undefined;
      if (c) onPick(c);
    });
    map.on("mouseenter", "dots", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "dots", () => { map.getCanvas().style.cursor = ""; });
    // وسمُ كلِّ نقطةٍ باسمها ورقمها (ثقة: النص من بياناتنا، مُهرَّب احتياطًا)
    for (const c of tension?.countries || []) {
      const d = document.createElement("div");
      d.style.cssText = "font:600 10px 'Noto Kufi Arabic';color:#E9E4D8;text-shadow:0 1px 3px #000;pointer-events:none;transform:translateY(14px)";
      d.textContent = `${c.name} ${c.score}`;
      new maplibregl.Marker({ element: d }).setLngLat([c.lon, c.lat]).addTo(map);
    }
    void esc; // (المُهرِّب يُستعمَل في بطاقات DOM خارج الخريطة)
  });

  return {
    fly: (c) => map.flyTo({ center: [c.lon, c.lat], zoom: 5.2 }),
    resize: () => map.resize(),
  };
}
