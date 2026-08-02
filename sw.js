/* سَنَد — عاملُ خدمةٍ محافِظ: يجعلُ الموقعَ قابلًا للتثبيت ويعملُ غلافُه دون شبكة،
   دون المساسِ بطزاجةِ البيانات — بياناتُ الأخبارِ تمرُّ للشبكةِ دائمًا. */
const SHELL = "sanad-shell-v2";
const PRECACHE = ["/", "/index.html", "/manifest.webmanifest",
  "/icons/icon-192.png", "/icons/icon-512.png", "/og-card.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()).catch(() => {}));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // بياناتٌ حيّة (bundle/json من مستودع البيانات) وأيُّ مصدرٍ خارجيّ: الشبكةُ أولًا دائمًا،
  // كي لا تتعفّنَ الأخبارُ في الكاش. لا نتدخّل — نتركُها للمتصفّح.
  if (url.origin !== self.location.origin) return;
  if (url.pathname.endsWith(".json")) return;

  // تنقّلُ الصفحة: الشبكةُ أولًا، والغلافُ المخبّأُ احتياطًا عند انقطاعها.
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).catch(() => caches.match("/index.html").then((r) => r || caches.match("/"))));
    return;
  }

  // أصولٌ ساكنةٌ من أصلِنا (أيقونات/بطاقة/manifest): الكاشُ أولًا ثم الشبكة.
  e.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res && res.ok && res.type === "basic") {
        const copy = res.clone();
        caches.open(SHELL).then((c) => c.put(req, copy)).catch(() => {});
      }
      return res;
    }).catch(() => hit)),
  );
});
