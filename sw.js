/* سَنَد — عامل خدمة خفيف: قِشرة تعمل دون شبكة + بيانات آخِر حالة معروفة.
   الهدف: قارئٌ عائدٌ أثناء انقطاعٍ يرى آخر ما وصله — دائمًا مختومًا بعُمره. */
const SHELL = 'sanad-shell-v1';
const DATA  = 'sanad-data-v1';
const SHELL_ASSETS = [
  '/', '/index.html',
  '/fonts/sanad-text.woff2',
  '/fonts/sanad-display.woff2'
];
const DATA_HOST = 'raw.githubusercontent.com';

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(SHELL).then(c => c.addAll(SHELL_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== SHELL && k !== DATA).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  let url;
  try { url = new URL(req.url); } catch { return; }

  // تنقّل بين الصفحات: الشبكة أولًا، فإن غابت فآخر قِشرة محفوظة
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req).then(r => {
        const copy = r.clone();
        caches.open(SHELL).then(c => c.put('/index.html', copy)).catch(() => {});
        return r;
      }).catch(() => caches.match('/index.html', { ignoreSearch: true }))
    );
    return;
  }

  // الخطوط وأصول نفس الأصل: المخزَّن أولًا
  if (url.origin === self.location.origin) {
    e.respondWith(
      caches.match(req).then(hit => hit || fetch(req).then(r => {
        if (r.ok) { const copy = r.clone(); caches.open(SHELL).then(c => c.put(req, copy)).catch(() => {}); }
        return r;
      }).catch(() => hit))
    );
    return;
  }

  // بيانات سَنَد (JSON): قديمٌ-أثناء-التحديث، مع تجاهل مُبطِّل التخزين ?t=
  if (url.hostname === DATA_HOST && url.pathname.endsWith('.json')) {
    e.respondWith(
      caches.open(DATA).then(cache =>
        cache.match(req, { ignoreSearch: true }).then(cached => {
          const net = fetch(req).then(r => {
            if (r && r.ok) cache.put(req, r.clone());
            return r;
          }).catch(() => cached);
          return cached || net;
        })
      )
    );
    return;
  }
});
