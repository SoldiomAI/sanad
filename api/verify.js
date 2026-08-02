'use strict';

/**
 * SANAD · الفاحِص — /api/verify
 * Cost-optimized URL verification ladder for isnad.news (Vercel Node).
 */

const crypto = require('crypto');

const RAW_BASE = 'https://raw.githubusercontent.com/Soldiom/sanad-data/main/daily';
const GROK_URL = 'https://api.x.ai/v1/responses';
const CACHE_MAX = 200;
const ACTIVITY_MAX = 40;
const URL_MAX = 2000;
const FETCH_TIMEOUT_MS = 8000;
const FETCH_MAX_BYTES = 200 * 1024;
const EXTRACT_MAX = 2500;
const USD_TICKS = 1e10;

const DEFAULT_CONTROL = {
  verify_enabled: true,
  verify_daily_budget_usd: 0.5,
  verify_per_ip_hour: 5,
  pipeline_daily_budget_usd: 0.8,
  paid_kill_switch: false,
  paused_agents: [],
  desks_enabled: ['noura', 'samir', 'laith', 'huda', 'hakim'],
  maintenance: '',
  verify_tab: true,
};

/** @type {Map<string, {at:number, payload:object}>} */
const cache = new Map();
/** @type {Map<string, {hour:number, count:number}>} */
const rateBuckets = new Map();
const spend = { day: utcDay(), usd: 0, calls: 0 };
/** @type {Array<object>} */
const activity = [];

function clearCache() {
  cache.clear();
}

function syncGlobal() {
  globalThis.__SANAD_VERIFY__ = {
    cache,
    spend,
    activity,
    clearCache,
    rateBuckets,
  };
}
syncGlobal();

function utcDay() {
  return new Date().toISOString().slice(0, 10);
}

function ensureSpendDay() {
  const d = utcDay();
  if (spend.day !== d) {
    spend.day = d;
    spend.usd = 0;
    spend.calls = 0;
  }
}

function json(res, status, body) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(body));
}

function setCors(req, res) {
  const origin = String(req.headers.origin || '');
  const host = String(req.headers.host || '');
  const method = String(req.method || 'GET').toUpperCase();

  let allowed = null;
  if (origin && host) {
    try {
      const o = new URL(origin);
      if (o.host === host) allowed = origin;
    } catch (_) {
      /* ignore */
    }
  }

  if (allowed) {
    res.setHeader('Access-Control-Allow-Origin', allowed);
    res.setHeader('Vary', 'Origin');
  } else if (method === 'GET' || method === 'OPTIONS') {
    // Safe for non-credentialed health/stats probes
    res.setHeader('Access-Control-Allow-Origin', '*');
  }

  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.setHeader('Access-Control-Max-Age', '86400');
}

function clientIp(req) {
  const xff = String(req.headers['x-forwarded-for'] || '')
    .split(',')[0]
    .trim();
  return xff || String(req.socket?.remoteAddress || '0.0.0.0');
}

function hashIp(ip) {
  const salt = process.env.ADMIN_SECRET || process.env.ADMIN_PASSWORD || 'sanad';
  return crypto.createHash('sha256').update(String(ip) + '|' + salt).digest('hex').slice(0, 16);
}

function urlHash(url) {
  return crypto.createHash('sha256').update(url).digest('hex');
}

function cacheGet(key) {
  const hit = cache.get(key);
  if (!hit) return null;
  // LRU touch
  cache.delete(key);
  cache.set(key, hit);
  return hit.payload;
}

function cacheSet(key, payload) {
  if (cache.has(key)) cache.delete(key);
  cache.set(key, { at: Date.now(), payload });
  while (cache.size > CACHE_MAX) {
    const oldest = cache.keys().next().value;
    cache.delete(oldest);
  }
}

function pushActivity(entry) {
  activity.push(entry);
  while (activity.length > ACTIVITY_MAX) activity.shift();
}

function checkRate(ip, limit) {
  const hour = Math.floor(Date.now() / 3_600_000);
  let bucket = rateBuckets.get(ip);
  if (!bucket || bucket.hour !== hour) {
    bucket = { hour, count: 0 };
    rateBuckets.set(ip, bucket);
  }
  // prune stale buckets occasionally
  if (rateBuckets.size > 5000) {
    for (const [k, v] of rateBuckets) {
      if (v.hour !== hour) rateBuckets.delete(k);
    }
  }
  if (bucket.count >= limit) return false;
  bucket.count += 1;
  return true;
}

function isBlockedHost(hostname) {
  const h = String(hostname || '').toLowerCase().replace(/\.$/, '');
  if (!h) return true;
  if (
    h === 'localhost' ||
    h === 'localhost.localdomain' ||
    h.endsWith('.localhost') ||
    h === '0.0.0.0' ||
    h === '::1' ||
    h === '[::1]'
  ) {
    return true;
  }
  // IPv4 private / link-local / loopback
  const m = h.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
  if (m) {
    const a = +m[1],
      b = +m[2];
    if (a === 10) return true;
    if (a === 127) return true;
    if (a === 0) return true;
    if (a === 169 && b === 254) return true;
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 192 && b === 168) return true;
  }
  // IPv6 local / ULA
  if (h.startsWith('fc') || h.startsWith('fd') || h.startsWith('fe80')) return true;
  return false;
}

function validateUrl(raw) {
  if (typeof raw !== 'string') return { ok: false, error: 'الرابط مطلوب' };
  const url = raw.trim();
  if (!url) return { ok: false, error: 'الرابط مطلوب' };
  if (url.length > URL_MAX) return { ok: false, error: 'الرابط أطول من المسموح' };
  let u;
  try {
    u = new URL(url);
  } catch (_) {
    return { ok: false, error: 'رابط غير صالح' };
  }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') {
    return { ok: false, error: 'يُقبل http و https فقط' };
  }
  if (isBlockedHost(u.hostname)) {
    return { ok: false, error: 'المضيف غير مسموح' };
  }
  return { ok: true, url: u.href, parsed: u };
}

/** Official / wire / channel heuristics → Arabic rank */
function sourceTier(hostname, displayName) {
  const h = String(hostname || '').toLowerCase();
  const n = String(displayName || '').toLowerCase();
  const blob = h + ' ' + n;

  const officialHints = [
    'spa.gov',
    'kuna.net',
    'kuna.com',
    'wam.ae',
    'qna.org',
    'bna.bh',
    'omannews',
    'petra.gov',
    'wafa.ps',
    'ina.iq',
    'nna-leb',
    'sana.sy',
    'sabanew',
    'mena.org',
    'aa.com.tr',
    'map.ma',
    'aps.dz',
    'tap.info',
    'suna-sd',
    '.gov.',
    '.gov/',
    'ministry',
    'diwan',
  ];
  if (
    officialHints.some((x) => blob.includes(x)) ||
    /\.gov(\.[a-z]{2,})?$/.test(h) ||
    h.endsWith('.gov')
  ) {
    return {
      name: displayName || hostname,
      rank: 'رسمي',
      live: true,
    };
  }

  const agencyHints = [
    'reuters',
    'apnews',
    'associatedpress',
    'afp.com',
    'agencefrance',
    'bbc.',
    'bbc.com',
    'bbc.co',
    'aljazeera',
    'al-jazeera',
    ' الجزيرة',
    'spa.gov',
    'kuna',
    'wam.ae',
    'bloomberg',
  ];
  // User ladder: known majors → وكالة/رسمي; we already handled رسمي above
  if (agencyHints.some((x) => blob.includes(x.replace(/\s/g, ''))) || /reuters|bbc|aljazeera|apnews|afp/.test(blob)) {
    return {
      name: displayName || hostname,
      rank: 'وكالة',
      live: true,
    };
  }

  const channelHints = [
    'skynews',
    'alarabiya',
    'asharq',
    'cnn',
    'france24',
    'dw.com',
    'rt.com',
    'youtube',
    'youtu.be',
    'twitter',
    'x.com',
    'facebook',
    'instagram',
    'tiktok',
    'telegram',
    't.me',
  ];
  if (channelHints.some((x) => blob.includes(x))) {
    return {
      name: displayName || hostname,
      rank: 'قناة',
      live: true,
    };
  }

  return {
    name: displayName || hostname || 'مجهول',
    rank: 'مجهول',
    live: false,
  };
}

function gradeFromRank(rank) {
  if (rank === 'رسمي') return 'صحيح';
  if (rank === 'وكالة') return 'حسن';
  if (rank === 'قناة') return 'ضعيف الإسناد';
  return '—';
}

function verdictFromGrade(grade) {
  if (grade === 'صحيح' || grade === 'حسن') return 'صحّ';
  if (grade === 'ضعيف الإسناد') return 'قيد التحقق';
  return 'قيد التحقق';
}

function detectMediaKind(contentType, urlPath, html) {
  const ct = String(contentType || '').toLowerCase();
  const path = String(urlPath || '').toLowerCase();
  if (ct.startsWith('image/') || /\.(jpe?g|png|gif|webp|avif|bmp|svg)(\?|$)/i.test(path)) {
    return 'image';
  }
  if (
    ct.startsWith('video/') ||
    /\.(mp4|webm|mov|m4v|mkv|avi)(\?|$)/i.test(path) ||
    /og:type["'\s]+content=["']video/i.test(html || '')
  ) {
    return 'video';
  }
  // og:image presence alone → still page with possible media
  if (/property=["']og:image["']/i.test(html || '') || /name=["']twitter:image["']/i.test(html || '')) {
    return 'image';
  }
  return 'none';
}

function metaContent(html, prop) {
  const re1 = new RegExp(
    `<meta[^>]+(?:property|name)=["']${prop}["'][^>]+content=["']([^"']*)["']`,
    'i'
  );
  const re2 = new RegExp(
    `<meta[^>]+content=["']([^"']*)["'][^>]+(?:property|name)=["']${prop}["']`,
    'i'
  );
  const m = html.match(re1) || html.match(re2);
  return m ? decodeEntities(m[1]).trim() : '';
}

function decodeEntities(s) {
  return String(s || '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)));
}

function extractTitle(html) {
  const og = metaContent(html, 'og:title');
  if (og) return og;
  const tw = metaContent(html, 'twitter:title');
  if (tw) return tw;
  const m = html.match(/<title[^>]*>([^<]*)<\/title>/i);
  return m ? decodeEntities(m[1]).trim() : '';
}

function extractDescription(html) {
  return (
    metaContent(html, 'og:description') ||
    metaContent(html, 'description') ||
    metaContent(html, 'twitter:description') ||
    ''
  );
}

function extractTextSnippet(html, maxLen) {
  let t = String(html || '')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<noscript[\s\S]*?<\/noscript>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  t = decodeEntities(t);
  if (t.length > maxLen) t = t.slice(0, maxLen);
  return t;
}

async function readBody(req) {
  if (req.body != null) {
    if (typeof req.body === 'string') {
      try {
        return JSON.parse(req.body || '{}');
      } catch (_) {
        return {};
      }
    }
    if (typeof req.body === 'object') return req.body;
  }
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const raw = Buffer.concat(chunks).toString('utf8');
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch (_) {
    return {};
  }
}

async function fetchJson(url, timeoutMs = 6000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, {
      signal: ctrl.signal,
      headers: { Accept: 'application/json', 'User-Agent': 'SANAD-Fahis/1.0' },
    });
    if (!r.ok) return null;
    return await r.json();
  } catch (_) {
    return null;
  } finally {
    clearTimeout(t);
  }
}

async function loadControl() {
  const shared = globalThis.__SANAD_CONTROL__;
  if (shared && shared.data && typeof shared.data === 'object') {
    return { ...DEFAULT_CONTROL, ...shared.data, _sticky: !!shared.sticky };
  }
  const remote = await fetchJson(`${RAW_BASE}/control.json`);
  if (remote && typeof remote === 'object') {
    return { ...DEFAULT_CONTROL, ...remote };
  }
  return { ...DEFAULT_CONTROL };
}

function flattenNewsItems(news) {
  const out = [];
  if (!news || typeof news !== 'object') return out;
  const cats = news.cats || news.categories || {};
  if (Array.isArray(news.items)) {
    for (const it of news.items) if (it && it.link) out.push(it);
  }
  for (const list of Object.values(cats)) {
    if (!Array.isArray(list)) continue;
    for (const it of list) if (it && it.link) out.push(it);
  }
  return out;
}

function normalizeLink(u) {
  try {
    const x = new URL(u);
    x.hash = '';
    return x.href.replace(/\/$/, '');
  } catch (_) {
    return String(u || '').trim();
  }
}

async function matchFeed(url) {
  const target = normalizeLink(url);
  const [news, bundle] = await Promise.all([
    fetchJson(`${RAW_BASE}/news.json`),
    fetchJson(`${RAW_BASE}/bundle.json`),
  ]);
  const pools = [];
  if (news) pools.push(...flattenNewsItems(news));
  if (bundle && bundle.news) pools.push(...flattenNewsItems(bundle.news));
  for (const it of pools) {
    if (normalizeLink(it.link) === target) return it;
  }
  // soft match: same pathname host ignoring query noise for non-google hosts
  try {
    const tu = new URL(url);
    if (!tu.hostname.includes('news.google')) {
      for (const it of pools) {
        try {
          const iu = new URL(it.link);
          if (iu.hostname === tu.hostname && iu.pathname === tu.pathname) return it;
        } catch (_) {
          /* skip */
        }
      }
    }
  } catch (_) {
    /* skip */
  }
  return null;
}

async function fetchPage(url) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
  try {
    const r = await fetch(url, {
      signal: ctrl.signal,
      redirect: 'follow',
      headers: {
        Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'User-Agent':
          'Mozilla/5.0 (compatible; SANAD-Fahis/1.0; +https://isnad.news)',
      },
    });
    const ct = r.headers.get('content-type') || '';
    const reader = r.body?.getReader?.();
    let buf = Buffer.alloc(0);
    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf = Buffer.concat([buf, Buffer.from(value)]);
        if (buf.length > FETCH_MAX_BYTES) {
          try {
            reader.cancel();
          } catch (_) {
            /* ignore */
          }
          break;
        }
      }
    } else {
      const ab = await r.arrayBuffer();
      buf = Buffer.from(ab).subarray(0, FETCH_MAX_BYTES);
    }
    const text = buf.toString('utf8');
    const finalUrl = r.url || url;
    let path = '';
    try {
      path = new URL(finalUrl).pathname;
    } catch (_) {
      path = '';
    }
    const title = extractTitle(text);
    const description = extractDescription(text);
    const ogImage = metaContent(text, 'og:image') || metaContent(text, 'twitter:image');
    const snippet = extractTextSnippet(text, EXTRACT_MAX);
    const kind = detectMediaKind(ct, path || finalUrl, text);
    return {
      ok: r.ok,
      status: r.status,
      contentType: ct,
      finalUrl,
      title,
      description,
      ogImage,
      snippet,
      kind,
      live: r.ok,
      hostname: (() => {
        try {
          return new URL(finalUrl).hostname;
        } catch (_) {
          return '';
        }
      })(),
    };
  } catch (e) {
    return {
      ok: false,
      status: 0,
      contentType: '',
      finalUrl: url,
      title: '',
      description: '',
      ogImage: '',
      snippet: '',
      kind: 'none',
      live: false,
      hostname: (() => {
        try {
          return new URL(url).hostname;
        } catch (_) {
          return '';
        }
      })(),
      error: e?.name === 'AbortError' ? 'timeout' : 'fetch_failed',
    };
  } finally {
    clearTimeout(t);
  }
}

function needsGrok(source, mediaKind) {
  if (source.rank === 'مجهول') return true;
  if (mediaKind === 'image' || mediaKind === 'video') return true;
  return false;
}

function extractGrokText(data) {
  if (!data || typeof data !== 'object') return '';
  if (typeof data.output_text === 'string') return data.output_text;
  const parts = [];
  const out = data.output;
  if (Array.isArray(out)) {
    for (const item of out) {
      if (!item) continue;
      if (typeof item.text === 'string') parts.push(item.text);
      const content = item.content;
      if (Array.isArray(content)) {
        for (const c of content) {
          if (typeof c?.text === 'string') parts.push(c.text);
          else if (c?.type === 'output_text' && typeof c.text === 'string') parts.push(c.text);
        }
      }
    }
  }
  return parts.join('\n').trim();
}

function parseGrokJson(text) {
  if (!text) return null;
  let s = text.trim();
  const fence = s.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence) s = fence[1].trim();
  const start = s.indexOf('{');
  const end = s.lastIndexOf('}');
  if (start >= 0 && end > start) s = s.slice(start, end + 1);
  try {
    return JSON.parse(s);
  } catch (_) {
    return null;
  }
}

async function callGrok({ url, title, description, snippet, source, mediaKind }) {
  const key = process.env.GROK_API_KEY;
  if (!key) return { ok: false, reason: 'no_key' };

  const model = process.env.GROK_VERIFY_MODEL || 'grok-4-1-fast-non-reasoning';
  const extract = [title, description, snippet].filter(Boolean).join('\n\n').slice(0, EXTRACT_MAX);

  const prompt = `أنت الفاحِص في منصة سَنَد (isnad.news). افحص الرابط التالي باختصار شديد وأعد JSON فقط بلا شرح.
الرابط: ${url}
المصدر الظاهري: ${source.name} (${source.rank})
نوع الوسائط: ${mediaKind}
مقتطف الصفحة (مقطوع):
${extract || '(فارغ)'}

أعد كائن JSON بهذه الحقول فقط:
{
  "claim": "نص الادعاء المختصر",
  "verdict": "صحّ" | "لم يصحّ" | "قيد التحقق",
  "why": "سبب موجز بالعربية",
  "sources": [{"u":"url","t":"اسم"}],
  "deepfake_risk": "منخفض" | "متوسط" | "مرتفع" | "غير مقيّم",
  "media_note": "ملاحظة وسائط موجزة أو فارغة",
  "grade": "صحيح" | "حسن" | "ضعيف الإسناد" | "—",
  "source_rank": "رسمي" | "وكالة" | "قناة" | "مجهول"
}`;

  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 25000);
  try {
    const r = await fetch(GROK_URL, {
      method: 'POST',
      signal: ctrl.signal,
      headers: {
        Authorization: `Bearer ${key}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model,
        input: [{ role: 'user', content: prompt }],
        max_output_tokens: 600,
        store: false,
      }),
    });
    const data = await r.json().catch(() => null);
    if (!r.ok) {
      return { ok: false, reason: 'grok_http', status: r.status, data };
    }
    const ticks = Number(data?.usage?.cost_in_usd_ticks || 0);
    const usd = ticks > 0 ? ticks / USD_TICKS : 0;
    const parsed = parseGrokJson(extractGrokText(data));
    return { ok: true, usd, parsed, raw: data };
  } catch (e) {
    return { ok: false, reason: e?.name === 'AbortError' ? 'timeout' : 'grok_error' };
  } finally {
    clearTimeout(t);
  }
}

function baseResult(url) {
  return {
    url,
    tier: 'free',
    source: { name: '', rank: 'مجهول', live: false },
    claim: '',
    news: { verdict: 'قيد التحقق', why: '', sources: [] },
    media: { kind: 'none', deepfake_risk: 'غير مقيّم', note: '' },
    grade: '—',
    agent: 'الفاحِص',
    cost_tier: 'fetch',
  };
}

function fromFeedItem(url, item) {
  const host = (() => {
    try {
      return new URL(item.link || url).hostname;
    } catch (_) {
      return '';
    }
  })();
  const source = sourceTier(host, item.src || host);
  source.live = true;
  const grade = item.grade || gradeFromRank(source.rank);
  return {
    url,
    tier: 'free',
    source,
    claim: item.head || item.he || '',
    news: {
      verdict: verdictFromGrade(grade),
      why: 'الخبر مطابق لحصيلة سَنَد المنشورة.',
      sources: [{ u: item.link || url, t: item.src || source.name }],
    },
    media: { kind: 'none', deepfake_risk: 'غير مقيّم', note: '' },
    grade,
    agent: 'الفاحِص',
    cost_tier: 'feed',
  };
}

function fromFetchHeuristic(url, page, source) {
  const grade = gradeFromRank(source.rank);
  const claim = page.title || page.description || '';
  const why =
    source.rank === 'رسمي' || source.rank === 'وكالة'
      ? `المصدر مصنَّف ضمن فئة «${source.rank}» بعد مراجعة الرابط.`
      : 'راجَعنا الرابط وقيَّمنا المصدر الظاهر دون إعلان تفاصيل الغرفة.';
  return {
    url,
    tier: 'free',
    source: { ...source, live: !!page.live },
    claim,
    news: {
      verdict: verdictFromGrade(grade),
      why,
      sources: page.live ? [{ u: page.finalUrl || url, t: source.name }] : [],
    },
    media: {
      kind: page.kind || 'none',
      deepfake_risk: page.kind === 'none' ? 'غير مقيّم' : 'غير مقيّم',
      note: page.ogImage ? 'وُجدت صورة مرفقة بالرابط — لم يُقيَّم خطر التزييف بعد.' : '',
    },
    grade,
    agent: 'الفاحِص',
    cost_tier: 'fetch',
  };
}

function mergeGrok(base, grokParsed, usd) {
  const g = grokParsed || {};
  const rank = g.source_rank || base.source.rank;
  const grade = g.grade || gradeFromRank(rank);
  return {
    ...base,
    tier: 'grok',
    source: {
      name: base.source.name,
      rank: ['رسمي', 'وكالة', 'قناة', 'مجهول'].includes(rank) ? rank : base.source.rank,
      live: base.source.live,
    },
    claim: g.claim || base.claim,
    news: {
      verdict: ['صحّ', 'لم يصحّ', 'قيد التحقق'].includes(g.verdict) ? g.verdict : base.news.verdict,
      why: g.why || base.news.why,
      sources: Array.isArray(g.sources) && g.sources.length
        ? g.sources
            .filter((s) => s && s.u)
            .map((s) => ({ u: String(s.u), t: String(s.t || '') }))
        : base.news.sources,
    },
    media: {
      kind: base.media.kind,
      deepfake_risk: ['منخفض', 'متوسط', 'مرتفع', 'غير مقيّم'].includes(g.deepfake_risk)
        ? g.deepfake_risk
        : base.media.deepfake_risk,
      note: g.media_note != null ? String(g.media_note) : base.media.note,
    },
    grade: ['صحيح', 'حسن', 'ضعيف الإسناد', '—'].includes(grade) ? grade : base.grade,
    agent: 'الفاحِص',
    cost_tier: 'grok',
    _usd: usd,
  };
}

function blockedResult(url, why) {
  return {
    url,
    tier: 'free',
    source: { name: '', rank: 'مجهول', live: false },
    claim: '',
    news: { verdict: 'قيد التحقق', why, sources: [] },
    media: { kind: 'none', deepfake_risk: 'غير مقيّم', note: '' },
    grade: '—',
    agent: 'الفاحِص',
    cost_tier: 'blocked',
  };
}

module.exports = async function handler(req, res) {
  syncGlobal();
  setCors(req, res);

  const method = String(req.method || 'GET').toUpperCase();

  if (method === 'OPTIONS') {
    res.statusCode = 204;
    return res.end();
  }

  if (method === 'GET') {
    const q = req.query || {};
    // Support both Vercel parsed query and raw URL
    let action = q.action;
    if (!action && req.url) {
      try {
        action = new URL(req.url, 'http://local').searchParams.get('action');
      } catch (_) {
        /* ignore */
      }
    }
    if (action === 'stats') {
      ensureSpendDay();
      return json(res, 200, {
        ok: true,
        spend: { ...spend },
        activity: activity.slice(-ACTIVITY_MAX),
        cache_size: cache.size,
      });
    }
    return json(res, 200, { ok: true, service: 'verify' });
  }

  if (method !== 'POST') {
    return json(res, 405, { error: 'الطريقة غير مسموحة' });
  }

  let body;
  try {
    body = await readBody(req);
  } catch (_) {
    return json(res, 400, { error: 'جسم الطلب غير صالح' });
  }

  const validated = validateUrl(body?.url);
  if (!validated.ok) {
    return json(res, 400, { error: validated.error });
  }
  const url = validated.url;
  const key = urlHash(url);
  const ip = clientIp(req);
  const ipH = hashIp(ip);

  // 2. Cache
  const cached = cacheGet(key);
  if (cached) {
    pushActivity({
      at: new Date().toISOString(),
      host: validated.parsed.hostname,
      tier: cached.tier || 'free',
      verdict: cached.news?.verdict || '',
      usd: 0,
      ipHash: ipH,
    });
    return json(res, 200, { ...cached, cost_tier: 'cache', url });
  }

  // 3. Feed match (free)
  try {
    const feedHit = await matchFeed(url);
    if (feedHit) {
      const payload = fromFeedItem(url, feedHit);
      cacheSet(key, payload);
      pushActivity({
        at: new Date().toISOString(),
        host: validated.parsed.hostname,
        tier: 'free',
        verdict: payload.news.verdict,
        usd: 0,
        ipHash: ipH,
      });
      return json(res, 200, payload);
    }
  } catch (_) {
    /* continue ladder */
  }

  // 4. Fetch page
  const page = await fetchPage(url);
  const source = sourceTier(page.hostname || validated.parsed.hostname, page.hostname);
  source.live = !!page.live;
  let result = fromFetchHeuristic(url, page, source);

  // 5–9. Control + rate + budget + optional Grok
  const control = await loadControl();
  ensureSpendDay();

  if (control.verify_enabled === false) {
    result = blockedResult(url, control.maintenance || 'خدمة التحقق متوقفة مؤقتًا.');
    cacheSet(key, result);
    pushActivity({
      at: new Date().toISOString(),
      host: validated.parsed.hostname,
      tier: 'free',
      verdict: result.news.verdict,
      usd: 0,
      ipHash: ipH,
    });
    return json(res, 200, result);
  }

  const perIp = Number(control.verify_per_ip_hour ?? DEFAULT_CONTROL.verify_per_ip_hour);
  if (!checkRate(ip, Number.isFinite(perIp) ? perIp : 5)) {
    result = blockedResult(url, 'تجاوزت حد الطلبات لهذه الساعة. حاول لاحقًا.');
    // do not cache rate blocks permanently as feed results
    pushActivity({
      at: new Date().toISOString(),
      host: validated.parsed.hostname,
      tier: 'free',
      verdict: result.news.verdict,
      usd: 0,
      ipHash: ipH,
    });
    return json(res, 429, result);
  }

  const wantGrok = needsGrok(source, page.kind);
  const kill = !!control.paid_kill_switch;
  const budget = Number(control.verify_daily_budget_usd ?? 0.5);
  const underBudget = spend.usd < (Number.isFinite(budget) ? budget : 0.5);
  const hasKey = !!process.env.GROK_API_KEY;

  if (wantGrok && !kill && underBudget && hasKey) {
    const grok = await callGrok({
      url,
      title: page.title,
      description: page.description,
      snippet: page.snippet,
      source,
      mediaKind: page.kind,
    });
    if (grok.ok) {
      ensureSpendDay();
      spend.usd += grok.usd || 0;
      spend.calls += 1;
      syncGlobal();
      result = mergeGrok(result, grok.parsed, grok.usd);
      pushActivity({
        at: new Date().toISOString(),
        host: validated.parsed.hostname,
        tier: 'grok',
        verdict: result.news.verdict,
        usd: grok.usd || 0,
        ipHash: ipH,
      });
      const { _usd, ...clean } = result;
      cacheSet(key, clean);
      return json(res, 200, clean);
    }
    // Deep review unavailable → keep fetch heuristic with public wording
    result.news.why =
      (result.news.why || '') +
      (result.news.why ? ' ' : '') +
      'اكتفينا بمراجعة الرابط الظاهرة.';
  } else if (wantGrok && (kill || !underBudget || !hasKey)) {
    result.cost_tier = kill || !underBudget ? 'blocked' : result.cost_tier;
    if (kill || !underBudget) {
      result.news.why = 'الحكم أوليّ ضمن الحد اليومي للمراجعات المعمّقة.';
    } else if (!hasKey) {
      result.news.why =
        (result.news.why || '') +
        (result.news.why ? ' ' : '') +
        'الحكم أوليّ من مراجعة الرابط الظاهرة.';
    }
    if (source.rank === 'مجهول') {
      result.grade = '—';
      result.news.verdict = 'قيد التحقق';
    }
  }

  cacheSet(key, result);
  pushActivity({
    at: new Date().toISOString(),
    host: validated.parsed.hostname,
    tier: result.tier || 'free',
    verdict: result.news.verdict,
    usd: 0,
    ipHash: ipH,
  });
  return json(res, 200, result);
};
