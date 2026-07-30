import "./style.css";
import { loadAll, type Bundle, type Tension, type CountryTension } from "./data";
import { applyDir, flipLng, t } from "./i18n";
import { initFlat, type MapApi, BAND } from "./map";
import { initGlobe, type GlobeApi } from "./globe";
import {
  renderPulse, renderIndex, renderDetail, renderAlerts,
  renderFeed, renderRumors, renderFresh,
} from "./panels";
import { esc } from "./esc";

let bundle: Bundle = {};
let tension: Tension | null = null;
let flat: MapApi | null = null;
let globe: GlobeApi | null = null;
let globeOn = false;
let selected: string | null = null;

function pick(c: CountryTension): void {
  selected = c.id;
  renderIndex(tension, selected, pick);
  renderDetail(c);
  flat?.fly(c);
}

function legend(): void {
  const bands: [string, number][] = [[t("calm"), 0], [t("watch"), 25], [t("tense"), 50], [t("crit"), 75]];
  (document.getElementById("legend") as HTMLElement).innerHTML =
    bands.map(([k, v]) => `<span class="lg"><i style="background:${BAND(v)}"></i>${esc(k)}</span>`).join("");
}

function renderAll(): void {
  renderPulse(bundle, tension);
  renderIndex(tension, selected, pick);
  renderAlerts(bundle);
  renderFeed(bundle);
  renderRumors(bundle);
  renderFresh(bundle, tension);
  legend();
}

async function toggleView(): Promise<void> {
  const f = document.getElementById("flat") as HTMLElement;
  const g = document.getElementById("globe") as HTMLElement;
  const btn = document.getElementById("viewBtn") as HTMLElement;
  globeOn = !globeOn;
  if (globeOn) {
    f.style.display = "none"; g.style.display = "block"; btn.textContent = "🗺️";
    if (!globe) globe = await initGlobe(g, tension, pick);
    globe.start();
  } else {
    g.style.display = "block"; globe?.stop();
    g.style.display = "none"; f.style.display = "block"; btn.textContent = "🌍";
    flat?.resize();
  }
}

async function boot(): Promise<void> {
  applyDir();
  ({ bundle, tension } = await loadAll());
  renderAll();
  flat = initFlat(document.getElementById("flat") as HTMLElement, tension, pick);
  (document.getElementById("viewBtn") as HTMLElement).onclick = () => { void toggleView(); };
  (document.getElementById("lngBtn") as HTMLElement).onclick = flipLng;
  // تحديثٌ دوريٌّ كلَّ ٥ دقائق — نفس إيقاع بيانات sanad-data
  setInterval(async () => {
    ({ bundle, tension } = await loadAll());
    renderAll();
  }, 5 * 60 * 1000);
}

void boot();
