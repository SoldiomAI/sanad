'use strict';

const crypto = require('crypto');
const dns = require('dns');
const http = require('http');
const https = require('https');
const net = require('net');

const DEFAULT_LIMITS = Object.freeze({
  redirects: 3,
  connectTimeoutMs: 3500,
  readTimeoutMs: 8000,
  htmlBytes: 512 * 1024,
  imageBytes: 5 * 1024 * 1024,
  avBytes: 6 * 1024 * 1024,
  jsonLdBytes: 64 * 1024,
  textChars: 2500,
  metadataValueChars: 4096,
  titleChars: 512,
  descriptionChars: 2000,
  siteNameChars: 256,
});

const MEDIA_MIMES = new Set([
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
  'image/avif',
  'video/mp4',
  'video/webm',
  'audio/mpeg',
  'audio/wav',
  'audio/x-wav',
  'audio/ogg',
  'audio/mp4',
]);

const PAGE_MIMES = new Set([
  'text/html',
  'application/xhtml+xml',
]);

function reason(code, ar, en) {
  return { code, ar, en };
}

const REASONS = Object.freeze({
  invalid_url: reason('invalid_url', 'الرابط غير صالح.', 'The URL is invalid.'),
  unsupported_scheme: reason(
    'unsupported_scheme',
    'يُقبل http وhttps العامّان فقط.',
    'Only public HTTP and HTTPS URLs are supported.'
  ),
  credentials_in_url: reason(
    'credentials_in_url',
    'لا تُقبل بيانات الدخول داخل الرابط.',
    'Credentials embedded in URLs are not accepted.'
  ),
  blocked_host: reason(
    'blocked_host',
    'يشير الرابط إلى مضيف خاص أو محجوز وغير مسموح.',
    'The URL points to a private or reserved host.'
  ),
  dns_failed: reason(
    'dns_failed',
    'تعذّر حل اسم المضيف العام.',
    'The public hostname could not be resolved.'
  ),
  dns_rebinding: reason(
    'dns_rebinding',
    'أعاد DNS عنوانًا خاصًا أو محجوزًا؛ أُوقف الطلب.',
    'DNS returned a private or reserved address, so the request was blocked.'
  ),
  too_many_redirects: reason(
    'too_many_redirects',
    'تجاوز الرابط عدد التحويلات الآمنة.',
    'The URL exceeded the safe redirect limit.'
  ),
  unsafe_redirect: reason(
    'unsafe_redirect',
    'حوّل الرابط إلى وجهة غير آمنة.',
    'The URL redirected to an unsafe destination.'
  ),
  timeout: reason(
    'timeout',
    'انتهت مهلة الاتصال أو القراءة.',
    'The connection or read timed out.'
  ),
  inaccessible: reason(
    'inaccessible',
    'تعذّر الوصول إلى الرابط العام.',
    'The public URL could not be reached.'
  ),
  login_required: reason(
    'login_required',
    'الصفحة تتطلب تسجيل الدخول أو تمنع القراءة العامة.',
    'The page requires login or blocks public reading.'
  ),
  unsupported_type: reason(
    'unsupported_type',
    'نوع المحتوى غير مدعوم للفحص.',
    'The content type is not supported for inspection.'
  ),
  type_mismatch: reason(
    'type_mismatch',
    'نوع الملف المعلن لا يطابق بصمته.',
    'The declared content type does not match the file signature.'
  ),
  too_large: reason(
    'too_large',
    'حجم الوسائط يتجاوز حد الفحص الآمن.',
    'The media exceeds the safe inspection size limit.'
  ),
  malformed_response: reason(
    'malformed_response',
    'أعاد المضيف استجابة غير قابلة للفحص.',
    'The host returned a response that could not be inspected.'
  ),
  no_media: reason(
    'no_media',
    'لم نعثر على وسائط عامة قابلة للفحص في الصفحة.',
    'No publicly accessible media was found on the page.'
  ),
});

function parseIpv4(address) {
  const parts = String(address || '').split('.');
  if (parts.length !== 4) return null;
  const nums = parts.map((part) => Number(part));
  if (nums.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) return null;
  return nums;
}

function isPublicIpv4(address) {
  const p = parseIpv4(address);
  if (!p) return false;
  const [a, b, c] = p;
  if (a === 0 || a === 10 || a === 127) return false;
  if (a === 100 && b >= 64 && b <= 127) return false;
  if (a === 169 && b === 254) return false;
  if (a === 172 && b >= 16 && b <= 31) return false;
  if (a === 192 && b === 0 && c === 0) return false;
  if (a === 192 && b === 0 && c === 2) return false;
  if (a === 192 && b === 88 && c === 99) return false;
  if (a === 192 && b === 168) return false;
  if (a === 198 && (b === 18 || b === 19)) return false;
  if (a === 198 && b === 51 && c === 100) return false;
  if (a === 203 && b === 0 && c === 113) return false;
  if (a >= 224) return false;
  return true;
}

function expandIpv6(address) {
  let input = String(address || '').toLowerCase().split('%')[0];
  const mapped = input.match(/^(.*:)(\d+\.\d+\.\d+\.\d+)$/);
  if (mapped) {
    const v4 = parseIpv4(mapped[2]);
    if (!v4) return null;
    input = `${mapped[1]}${((v4[0] << 8) | v4[1]).toString(16)}:${(
      (v4[2] << 8) |
      v4[3]
    ).toString(16)}`;
  }
  const halves = input.split('::');
  if (halves.length > 2) return null;
  const left = halves[0] ? halves[0].split(':') : [];
  const right = halves[1] ? halves[1].split(':') : [];
  const missing = 8 - left.length - right.length;
  if ((halves.length === 1 && missing !== 0) || missing < 0) return null;
  const groups = [...left, ...Array(missing).fill('0'), ...right];
  if (groups.length !== 8 || groups.some((g) => !/^[0-9a-f]{1,4}$/.test(g))) return null;
  return groups.map((g) => parseInt(g, 16));
}

function isPublicIpv6(address) {
  const g = expandIpv6(address);
  if (!g) return false;
  if (g.every((part) => part === 0) || g.slice(0, 7).every((part) => part === 0) && g[7] === 1) {
    return false;
  }
  if (g.slice(0, 5).every((part) => part === 0) && g[5] === 0xffff) {
    const mapped = `${g[6] >> 8}.${g[6] & 255}.${g[7] >> 8}.${g[7] & 255}`;
    return isPublicIpv4(mapped);
  }
  // Conservatively allow only global unicast space; special transition and
  // documentation prefixes inside it remain blocked below.
  if ((g[0] & 0xe000) !== 0x2000) return false;
  if ((g[0] & 0xfe00) === 0xfc00) return false;
  if ((g[0] & 0xffc0) === 0xfe80) return false;
  if ((g[0] & 0xff00) === 0xff00) return false;
  if (g[0] === 0x2001 && g[1] === 0x0db8) return false;
  if (g[0] === 0x2002) return false;
  if ((g[0] & 0xfff0) === 0x3ff0) return false;
  return true;
}

function isPublicIp(address) {
  const version = net.isIP(String(address || '').split('%')[0]);
  if (version === 4) return isPublicIpv4(address);
  if (version === 6) return isPublicIpv6(address);
  return false;
}

function normalizeHostname(hostname) {
  return String(hostname || '')
    .toLowerCase()
    .replace(/\.$/, '')
    .replace(/^\[|\]$/g, '');
}

function validatePublicUrl(raw) {
  let parsed;
  try {
    parsed = raw instanceof URL ? new URL(raw.href) : new URL(String(raw || '').trim());
  } catch (_) {
    return { ok: false, reason: REASONS.invalid_url };
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    return { ok: false, reason: REASONS.unsupported_scheme };
  }
  if (parsed.username || parsed.password) {
    return { ok: false, reason: REASONS.credentials_in_url };
  }
  const hostname = normalizeHostname(parsed.hostname);
  if (
    !hostname ||
    hostname === 'localhost' ||
    hostname.endsWith('.localhost') ||
    hostname.endsWith('.local') ||
    hostname.endsWith('.internal')
  ) {
    return { ok: false, reason: REASONS.blocked_host };
  }
  if (net.isIP(hostname) && !isPublicIp(hostname)) {
    return { ok: false, reason: REASONS.blocked_host };
  }
  parsed.hash = '';
  return { ok: true, url: parsed.href, parsed, hostname };
}

async function resolvePublicHost(hostname, lookup = dns.promises.lookup) {
  const normalized = normalizeHostname(hostname);
  if (net.isIP(normalized)) {
    if (!isPublicIp(normalized)) throw Object.assign(new Error('blocked_host'), { reason: REASONS.blocked_host });
    return [{ address: normalized, family: net.isIP(normalized) }];
  }
  let records;
  try {
    records = await lookup(normalized, { all: true, verbatim: true });
  } catch (_) {
    throw Object.assign(new Error('dns_failed'), { reason: REASONS.dns_failed });
  }
  const list = Array.isArray(records) ? records : records ? [records] : [];
  if (!list.length) throw Object.assign(new Error('dns_failed'), { reason: REASONS.dns_failed });
  if (list.some((entry) => !isPublicIp(entry.address))) {
    throw Object.assign(new Error('dns_rebinding'), { reason: REASONS.dns_rebinding });
  }
  return list;
}

function contentType(headers) {
  return String(headers['content-type'] || '').split(';')[0].trim().toLowerCase();
}

function kindFromMime(mime) {
  if (mime.startsWith('image/')) return 'image';
  if (mime.startsWith('video/')) return 'video';
  if (mime.startsWith('audio/')) return 'audio';
  if (PAGE_MIMES.has(mime)) return 'page';
  return 'unknown';
}

function kindFromPath(pathname) {
  const p = String(pathname || '').toLowerCase();
  if (/\.(jpe?g|png|gif|webp|avif)$/.test(p)) return 'image';
  if (/\.(mp4|webm|mov|m4v)$/.test(p)) return 'video';
  if (/\.(mp3|wav|ogg|m4a|aac)$/.test(p)) return 'audio';
  if (/\.(html?|xhtml)$/.test(p)) return 'page';
  return 'unknown';
}

function sniffMime(buffer) {
  if (!Buffer.isBuffer(buffer) || !buffer.length) return '';
  if (buffer.length >= 8 && buffer.subarray(0, 8).equals(Buffer.from('89504e470d0a1a0a', 'hex'))) return 'image/png';
  if (buffer.length >= 3 && buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) return 'image/jpeg';
  if (buffer.subarray(0, 6).toString('ascii').match(/^GIF8[79]a$/)) return 'image/gif';
  if (buffer.length >= 12 && buffer.subarray(0, 4).toString('ascii') === 'RIFF' && buffer.subarray(8, 12).toString('ascii') === 'WEBP') return 'image/webp';
  if (buffer.length >= 12 && buffer.subarray(4, 8).toString('ascii') === 'ftyp') {
    const brand = buffer.subarray(8, 16).toString('ascii').toLowerCase();
    if (brand.includes('avif')) return 'image/avif';
    if (brand.includes('m4a')) return 'audio/mp4';
    return 'video/mp4';
  }
  if (buffer.length >= 4 && buffer.subarray(0, 4).equals(Buffer.from('1a45dfa3', 'hex'))) return 'video/webm';
  if (buffer.subarray(0, 3).toString('ascii') === 'ID3' || (buffer[0] === 0xff && (buffer[1] & 0xe0) === 0xe0)) return 'audio/mpeg';
  if (buffer.length >= 12 && buffer.subarray(0, 4).toString('ascii') === 'RIFF' && buffer.subarray(8, 12).toString('ascii') === 'WAVE') return 'audio/wav';
  if (buffer.subarray(0, 4).toString('ascii') === 'OggS') return 'audio/ogg';
  const prefix = buffer.subarray(0, 512).toString('utf8').replace(/^\uFEFF/, '').trimStart().toLowerCase();
  if (/^(?:<!doctype html|<html|<head|<meta|<title)/.test(prefix)) return 'text/html';
  return '';
}

function capFor(kind, limits) {
  if (kind === 'image') return limits.imageBytes;
  if (kind === 'video' || kind === 'audio') return limits.avBytes;
  return limits.htmlBytes;
}

function defaultRequestUrl({ url, address, family, limits, headers }) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const transport = parsed.protocol === 'https:' ? https : http;
    let settled = false;
    let connected = false;
    const req = transport.request(parsed, {
      method: 'GET',
      headers,
      agent: false,
      servername: normalizeHostname(parsed.hostname),
      lookup(_hostname, lookupOptions, callback) {
        if (lookupOptions?.all) {
          callback(null, [{ address, family }]);
          return;
        }
        callback(null, address, family);
      },
    });
    const connectTimer = setTimeout(() => {
      req.destroy(Object.assign(new Error('timeout'), { reason: REASONS.timeout }));
    }, limits.connectTimeoutMs);
    req.on('socket', (socket) => {
      socket.once(parsed.protocol === 'https:' ? 'secureConnect' : 'connect', () => {
        connected = true;
        clearTimeout(connectTimer);
      });
    });
    req.setTimeout(limits.readTimeoutMs, () => {
      req.destroy(Object.assign(new Error('timeout'), { reason: REASONS.timeout }));
    });
    req.on('response', (res) => {
      clearTimeout(connectTimer);
      const readTimer = setTimeout(() => {
        res.destroy(Object.assign(new Error('timeout'), { reason: REASONS.timeout }));
      }, limits.readTimeoutMs);
      const responseHeaders = {};
      for (const [name, value] of Object.entries(res.headers)) {
        responseHeaders[name.toLowerCase()] = Array.isArray(value) ? value.join(', ') : String(value || '');
      }
      const declared = contentType(responseHeaders);
      const hintedKind = kindFromMime(declared) !== 'unknown'
        ? kindFromMime(declared)
        : kindFromPath(parsed.pathname);
      const cap = capFor(hintedKind, limits);
      const declaredLength = Number(responseHeaders['content-length'] || 0);
      if (hintedKind === 'image' && declaredLength > cap) {
        res.destroy();
        settled = true;
        clearTimeout(readTimer);
        return resolve({
          status: res.statusCode || 0,
          headers: responseHeaders,
          body: Buffer.alloc(0),
          truncated: true,
          errorReason: REASONS.too_large,
        });
      }
      const chunks = [];
      let length = 0;
      let truncated = false;
      res.on('data', (chunk) => {
        if (settled) return;
        const value = Buffer.from(chunk);
        const remaining = cap - length;
        if (remaining > 0) {
          chunks.push(value.subarray(0, remaining));
          length += Math.min(value.length, remaining);
        }
        if (value.length > remaining || length >= cap && declaredLength > cap) {
          truncated = true;
          res.destroy();
        }
      });
      const finish = () => {
        if (settled) return;
        settled = true;
        clearTimeout(readTimer);
        resolve({
          status: res.statusCode || 0,
          headers: responseHeaders,
          body: Buffer.concat(chunks),
          truncated,
        });
      };
      res.on('end', finish);
      res.on('close', finish);
      res.on('error', (error) => {
        if (truncated) finish();
        else if (!settled) {
          settled = true;
          clearTimeout(readTimer);
          reject(error);
        }
      });
    });
    req.on('error', (error) => {
      clearTimeout(connectTimer);
      if (!settled) {
        settled = true;
        reject(error);
      }
    });
    req.on('close', () => {
      if (!connected) clearTimeout(connectTimer);
    });
    req.end();
  });
}

async function secureFetchResource(rawUrl, options = {}, deps = {}) {
  const limits = { ...DEFAULT_LIMITS, ...(options.limits || {}) };
  const lookup = deps.lookup || dns.promises.lookup;
  const requestUrl = deps.requestUrl || defaultRequestUrl;
  let current = String(rawUrl || '');
  const redirects = [];

  for (let hop = 0; hop <= limits.redirects; hop += 1) {
    const valid = validatePublicUrl(current);
    if (!valid.ok) {
      return { ok: false, reason: hop ? REASONS.unsafe_redirect : valid.reason, redirects };
    }
    let records;
    try {
      records = await resolvePublicHost(valid.hostname, lookup);
    } catch (error) {
      return { ok: false, reason: error.reason || REASONS.dns_failed, redirects };
    }
    const selected = records[0];
    let response;
    try {
      response = await requestUrl({
        url: valid.url,
        address: selected.address,
        family: selected.family,
        limits,
        headers: {
          Accept: 'text/html,application/xhtml+xml,image/png,image/jpeg,image/gif,image/webp,image/avif,video/mp4,video/webm,audio/mpeg,audio/mp4,audio/wav,audio/ogg;q=0.9',
          'User-Agent': 'SANAD-Fahis/2.0 (+https://www.isnad.news/privacy)',
        },
      });
    } catch (error) {
      return { ok: false, reason: error.reason || (error.message === 'timeout' ? REASONS.timeout : REASONS.inaccessible), redirects };
    }
    const status = Number(response.status || 0);
    if ([301, 302, 303, 307, 308].includes(status)) {
      const location = response.headers?.location;
      if (!location) return { ok: false, reason: REASONS.malformed_response, redirects };
      if (hop === limits.redirects) return { ok: false, reason: REASONS.too_many_redirects, redirects };
      let next;
      try {
        next = new URL(location, valid.url).href;
      } catch (_) {
        return { ok: false, reason: REASONS.unsafe_redirect, redirects };
      }
      const nextValid = validatePublicUrl(next);
      if (!nextValid.ok) return { ok: false, reason: REASONS.unsafe_redirect, redirects };
      redirects.push({ from: valid.url, to: nextValid.url, status });
      current = nextValid.url;
      continue;
    }
    if (status === 401 || status === 403) {
      return { ok: false, status, reason: REASONS.login_required, finalUrl: valid.url, redirects };
    }
    if (status < 200 || status >= 300) {
      return { ok: false, status, reason: REASONS.inaccessible, finalUrl: valid.url, redirects };
    }
    if (response.errorReason) {
      return { ok: false, status, reason: response.errorReason, finalUrl: valid.url, redirects };
    }
    const body = Buffer.isBuffer(response.body) ? response.body : Buffer.from(response.body || '');
    const declaredMime = contentType(response.headers || {});
    const sniffedMime = sniffMime(body);
    const declaredKind = kindFromMime(declaredMime);
    const sniffedKind = kindFromMime(sniffedMime);
    let mime = declaredMime;
    if (declaredKind === 'unknown' || declaredMime === 'application/octet-stream') mime = sniffedMime;
    if (!PAGE_MIMES.has(mime) && !MEDIA_MIMES.has(mime)) {
      return { ok: false, status, reason: REASONS.unsupported_type, finalUrl: valid.url, redirects };
    }
    if (['image', 'video', 'audio'].includes(declaredKind) && sniffedKind === 'unknown') {
      return { ok: false, status, reason: REASONS.type_mismatch, finalUrl: valid.url, redirects };
    }
    const equivalentMimes =
      declaredMime === sniffedMime ||
      new Set([declaredMime, sniffedMime]).size === 2 &&
        ['audio/wav', 'audio/x-wav'].includes(declaredMime) &&
        ['audio/wav', 'audio/x-wav'].includes(sniffedMime) ||
      // Generic ISO-BMFF brands sniff as video/mp4, but may validly carry audio.
      // The reverse is unsafe: an explicit M4A brand must not satisfy video/mp4.
      declaredMime === 'audio/mp4' && sniffedMime === 'video/mp4';
    if (
      declaredKind !== 'unknown' &&
      sniffedKind !== 'unknown' &&
      (!equivalentMimes && (declaredKind !== sniffedKind ||
        ['image', 'video'].includes(declaredKind) && !equivalentMimes)
      )
    ) {
      return { ok: false, status, reason: REASONS.type_mismatch, finalUrl: valid.url, redirects };
    }
    const kind = kindFromMime(mime);
    if (kind === 'image' && response.truncated) {
      return { ok: false, status, reason: REASONS.too_large, finalUrl: valid.url, redirects };
    }
    return {
      ok: true,
      status,
      finalUrl: valid.url,
      headers: response.headers || {},
      mime,
      kind,
      body,
      truncated: !!response.truncated,
      redirects,
      resolvedAddress: selected.address,
      digest: crypto.createHash('sha256').update(body).digest('hex'),
    };
  }
  return { ok: false, reason: REASONS.too_many_redirects, redirects };
}

function decodeEntities(value) {
  const decodeCodePoint = (text, radix) => {
    const codePoint = Number.parseInt(text, radix);
    return Number.isInteger(codePoint) && codePoint >= 0 && codePoint <= 0x10ffff
      ? String.fromCodePoint(codePoint)
      : '\ufffd';
  };
  return String(value || '')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => decodeCodePoint(n, 16))
    .replace(/&#(\d+);/g, (_, n) => decodeCodePoint(n, 10));
}

function attrs(tag) {
  const out = {};
  const re = /([:\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/g;
  let match;
  while ((match = re.exec(tag))) {
    out[match[1].toLowerCase()] = decodeEntities(match[2] ?? match[3] ?? match[4] ?? '');
  }
  return out;
}

function absoluteUrl(value, baseUrl) {
  if (!value || /^data:|^blob:/i.test(value)) return '';
  try {
    const url = new URL(value, baseUrl);
    return ['http:', 'https:'].includes(url.protocol) &&
      !url.username &&
      !url.password &&
      url.href.length <= 2000
      ? url.href
      : '';
  } catch (_) {
    return '';
  }
}

function collectJsonLd(value, baseUrl, out, depth = 0) {
  if (depth > 8 || out.length >= 24 || value == null) return;
  if (Array.isArray(value)) {
    for (const item of value) collectJsonLd(item, baseUrl, out, depth + 1);
    return;
  }
  if (typeof value !== 'object') return;
  const type = String(value['@type'] || '').toLowerCase();
  const add = (raw, kind, method, priority) => {
    const values = Array.isArray(raw) ? raw : [raw];
    for (const item of values) {
      const candidate = typeof item === 'string' ? item : item?.url || item?.contentUrl;
      const url = absoluteUrl(candidate, baseUrl);
      if (url) out.push({ url, kind, method, priority });
    }
  };
  if (type.includes('video')) {
    add(value.contentUrl || value.embedUrl, 'video', 'json-ld-video', 30);
    add(value.thumbnailUrl, 'image', 'json-ld-thumbnail', 70);
  } else if (type.includes('audio')) {
    add(value.contentUrl || value.embedUrl, 'audio', 'json-ld-audio', 35);
  } else if (type.includes('image')) {
    add(value.contentUrl || value.url, 'image', 'json-ld-image', 55);
  }
  add(value.video, 'video', 'json-ld-video', 32);
  add(value.audio, 'audio', 'json-ld-audio', 37);
  add(value.image, 'image', 'json-ld-image', 60);
  for (const child of Object.values(value)) {
    if (child && typeof child === 'object') collectJsonLd(child, baseUrl, out, depth + 1);
  }
}

function extractPageMetadata(buffer, baseUrl, limits = DEFAULT_LIMITS) {
  const html = Buffer.isBuffer(buffer) ? buffer.toString('utf8') : String(buffer || '');
  const metas = {};
  for (const tag of html.match(/<meta\b[^>]*>/gi) || []) {
    const a = attrs(tag);
    const key = String(a.property || a.name || '').toLowerCase().slice(0, 128);
    if (key && a.content && !metas[key]) {
      metas[key] = a.content.trim().slice(0, limits.metadataValueChars);
    }
  }
  const links = {};
  for (const tag of html.match(/<link\b[^>]*>/gi) || []) {
    const a = attrs(tag);
    const rel = String(a.rel || '').toLowerCase();
    if (rel && a.href && !links[rel]) links[rel] = absoluteUrl(a.href, baseUrl);
  }
  const titleMatch = html.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i);
  const title = (
    metas['og:title'] ||
    metas['twitter:title'] ||
    decodeEntities(titleMatch?.[1] || '').replace(/\s+/g, ' ').trim()
  ).slice(0, limits.titleChars);
  const description = (
    metas['og:description'] ||
    metas.description ||
    metas['twitter:description'] ||
    ''
  ).slice(0, limits.descriptionChars);
  const candidates = [];
  const add = (value, kind, method, priority) => {
    const url = absoluteUrl(value, baseUrl);
    if (url) candidates.push({ url, kind, method, priority });
  };
  add(metas['og:video:secure_url'] || metas['og:video:url'] || metas['og:video'], 'video', 'open-graph-video', 10);
  add(metas['twitter:player:stream'], 'video', 'twitter-player', 15);
  add(metas['og:audio:secure_url'] || metas['og:audio'], 'audio', 'open-graph-audio', 20);
  add(metas['og:image:secure_url'] || metas['og:image'], 'image', 'open-graph-image', 40);
  add(metas['twitter:image:src'] || metas['twitter:image'], 'image', 'twitter-image', 45);
  for (const tag of html.match(/<(?:video|audio|source)\b[^>]*>/gi) || []) {
    const a = attrs(tag);
    const tagName = tag.match(/^<(\w+)/i)?.[1]?.toLowerCase();
    const declared = String(a.type || '').toLowerCase();
    let kind = tagName === 'audio' ? 'audio' : tagName === 'video' ? 'video' : kindFromMime(declared);
    if (kind === 'unknown' || kind === 'page') kind = kindFromPath(a.src);
    if (['image', 'video', 'audio'].includes(kind)) add(a.src, kind, `${tagName}-source`, 25);
    if (tagName === 'video') add(a.poster, 'image', 'video-poster', 5);
  }
  const jsonLdRe = /<script\b[^>]*type\s*=\s*(?:"application\/ld\+json"|'application\/ld\+json')[^>]*>([\s\S]*?)<\/script>/gi;
  let jsonMatch;
  let jsonCount = 0;
  while ((jsonMatch = jsonLdRe.exec(html)) && jsonCount < 12) {
    jsonCount += 1;
    const raw = jsonMatch[1].trim();
    if (!raw || Buffer.byteLength(raw) > limits.jsonLdBytes) continue;
    try {
      collectJsonLd(JSON.parse(raw), baseUrl, candidates);
    } catch (_) {
      // Malformed JSON-LD is ignored; other page metadata remains usable.
    }
  }
  const seen = new Set();
  const unique = candidates
    .filter((item) => {
      const key = `${item.kind}|${item.url}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => a.priority - b.priority)
    .slice(0, 16);
  const snippet = decodeEntities(
    html
      .replace(/<script[\s\S]*?<\/script>/gi, ' ')
      .replace(/<style[\s\S]*?<\/style>/gi, ' ')
      .replace(/<noscript[\s\S]*?<\/noscript>/gi, ' ')
      .replace(/<!--[\s\S]*?-->/g, ' ')
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
  ).slice(0, limits.textChars);
  return {
    title,
    description,
    siteName: (metas['og:site_name'] || '').slice(0, limits.siteNameChars),
    canonicalUrl: links.canonical || absoluteUrl(metas['og:url'], baseUrl) || baseUrl,
    candidates: unique,
    snippet,
    loginHint: /(?:log in|sign in|تسجيل الدخول|سجّل الدخول|login required)/i.test(snippet.slice(0, 1200)),
  };
}

function mediaShell(overrides = {}) {
  return {
    kind: 'none',
    url: '',
    mime: '',
    source: 'none',
    extraction_method: 'none',
    analysis_scope: 'none',
    inspected_url: '',
    bytes_fetched: 0,
    content_digest: '',
    truncated: false,
    buffer: null,
    local_signals: [],
    redirects: [],
    ...overrides,
  };
}

function inspectImageMarkers(buffer) {
  if (!Buffer.isBuffer(buffer) || !buffer.length) return [];
  const chunks = [];
  const maxMetadataBytes = 64 * 1024;
  if (sniffMime(buffer) === 'image/png') {
    let offset = 8;
    let total = 0;
    while (offset + 12 <= buffer.length && total < maxMetadataBytes) {
      const length = buffer.readUInt32BE(offset);
      const type = buffer.toString('ascii', offset + 4, offset + 8);
      const dataStart = offset + 8;
      const dataEnd = dataStart + length;
      if (dataEnd + 4 > buffer.length) break;
      if (type === 'tEXt') {
        const value = buffer.subarray(dataStart, Math.min(dataEnd, dataStart + maxMetadataBytes - total));
        chunks.push(value);
        total += value.length;
      } else if (type === 'iTXt') {
        const value = buffer.subarray(dataStart, Math.min(dataEnd, dataStart + maxMetadataBytes - total));
        const firstNull = value.indexOf(0);
        if (firstNull >= 0 && value[firstNull + 1] === 0) {
          chunks.push(value);
          total += value.length;
        }
      }
      offset = dataEnd + 4;
      if (type === 'IEND') break;
    }
  } else if (sniffMime(buffer) === 'image/jpeg') {
    let offset = 2;
    let total = 0;
    while (offset + 4 <= buffer.length && total < maxMetadataBytes && buffer[offset] === 0xff) {
      const marker = buffer[offset + 1];
      if (marker === 0xda || marker === 0xd9) break;
      const length = buffer.readUInt16BE(offset + 2);
      if (length < 2 || offset + 2 + length > buffer.length) break;
      if (marker === 0xe1 || marker === 0xed || marker === 0xfe) {
        const value = buffer.subarray(
          offset + 4,
          Math.min(offset + 2 + length, offset + 4 + maxMetadataBytes - total)
        );
        chunks.push(value);
        total += value.length;
      }
      offset += 2 + length;
    }
  }
  const text = Buffer.concat(chunks).toString('utf8').toLowerCase();
  const markers = [
    ['generative fill', 'Structured metadata names a generative-fill workflow.'],
    ['stable diffusion', 'Structured metadata names Stable Diffusion.'],
    ['comfyui', 'Structured metadata names ComfyUI.'],
    ['midjourney', 'Structured metadata names Midjourney.'],
    ['dall-e', 'Structured metadata names DALL-E.'],
    ['adobe firefly', 'Structured metadata names Adobe Firefly.'],
  ];
  return markers
    .filter(([needle]) => text.includes(needle))
    .map(([, signal]) => signal)
    .slice(0, 4);
}

async function inspectPublicUrl(rawUrl, deps = {}, options = {}) {
  const limits = { ...DEFAULT_LIMITS, ...(options.limits || {}) };
  const root = await secureFetchResource(rawUrl, { limits }, deps);
  if (!root.ok) {
    return {
      ok: false,
      live: false,
      finalUrl: root.finalUrl || rawUrl,
      hostname: safeHostname(root.finalUrl || rawUrl),
      reason: root.reason || REASONS.inaccessible,
      title: '',
      description: '',
      snippet: '',
      media: mediaShell(),
      redirects: root.redirects || [],
    };
  }
  if (['image', 'video', 'audio'].includes(root.kind)) {
    const scope = root.truncated ? 'metadata_only' : 'original_media';
    return {
      ok: true,
      live: true,
      finalUrl: root.finalUrl,
      hostname: safeHostname(root.finalUrl),
      reason: null,
      title: '',
      description: '',
      snippet: '',
      contentType: root.mime,
      media: mediaShell({
        kind: root.kind,
        url: root.finalUrl,
        mime: root.mime,
        source: 'direct',
        extraction_method: 'direct-url',
        analysis_scope: scope,
        inspected_url: root.finalUrl,
        bytes_fetched: root.body.length,
        content_digest: root.digest,
        truncated: root.truncated,
        buffer: !root.truncated ? root.body : null,
        local_signals: root.kind === 'image' && !root.truncated
          ? inspectImageMarkers(root.body)
          : [],
        redirects: root.redirects || [],
      }),
      redirects: root.redirects,
    };
  }

  let page;
  try {
    page = extractPageMetadata(root.body, root.finalUrl, limits);
  } catch (_) {
    return {
      ok: false,
      live: true,
      finalUrl: root.finalUrl,
      hostname: safeHostname(root.finalUrl),
      reason: REASONS.malformed_response,
      title: '',
      description: '',
      snippet: '',
      media: mediaShell(),
      redirects: root.redirects,
    };
  }
  const selected = page.candidates.find((item) => item.method !== 'video-poster') || null;
  const poster = page.candidates.find((item) => item.method === 'video-poster') || null;
  let media = mediaShell();
  let mediaReason = null;
  if (selected) {
    const fetched = await secureFetchResource(selected.url, { limits }, deps);
    if (fetched.ok && fetched.kind === selected.kind) {
      media = mediaShell({
        kind: selected.kind,
        url: fetched.finalUrl,
        mime: fetched.mime,
        source: 'page',
        extraction_method: selected.method,
        analysis_scope: !fetched.truncated ? 'embedded_media' : 'metadata_only',
        inspected_url: fetched.finalUrl,
        bytes_fetched: fetched.body.length,
        content_digest: fetched.digest,
        truncated: fetched.truncated,
        buffer: !fetched.truncated ? fetched.body : null,
        local_signals: selected.kind === 'image' && !fetched.truncated
          ? inspectImageMarkers(fetched.body)
          : [],
        redirects: fetched.redirects || [],
      });
    } else {
      media = mediaShell({
        kind: selected.kind,
        source: 'page',
        extraction_method: selected.method,
        analysis_scope: 'metadata_only',
      });
      mediaReason = fetched.reason || REASONS.inaccessible;
    }
  }
  if (selected?.kind === 'video' && poster && (!media.buffer || media.truncated)) {
    const fetchedPoster = await secureFetchResource(poster.url, { limits }, deps);
    if (fetchedPoster.ok && fetchedPoster.kind === 'image' && !fetchedPoster.truncated) {
      media = mediaShell({
        ...media,
        kind: 'video',
        source: 'page',
        extraction_method: `${selected.method}+video-poster`,
        analysis_scope: 'poster_or_thumbnail',
        inspected_url: fetchedPoster.finalUrl,
        bytes_fetched: fetchedPoster.body.length,
        content_digest: fetchedPoster.digest,
        buffer: fetchedPoster.body,
        mime: fetchedPoster.mime,
        local_signals: inspectImageMarkers(fetchedPoster.body),
        redirects: [
          ...(media.redirects || []),
          ...(fetchedPoster.redirects || []),
        ],
      });
    }
  }
  if (!selected && poster) {
    const fetchedPoster = await secureFetchResource(poster.url, { limits }, deps);
    if (fetchedPoster.ok && fetchedPoster.kind === 'image' && !fetchedPoster.truncated) {
      media = mediaShell({
        kind: 'video',
        url: '',
        mime: fetchedPoster.mime,
        source: 'page',
        extraction_method: 'video-poster',
        analysis_scope: 'poster_or_thumbnail',
        inspected_url: fetchedPoster.finalUrl,
        bytes_fetched: fetchedPoster.body.length,
        content_digest: fetchedPoster.digest,
        buffer: fetchedPoster.body,
        local_signals: inspectImageMarkers(fetchedPoster.body),
        redirects: fetchedPoster.redirects || [],
      });
    }
  }
  const inaccessiblePage = page.loginHint && media.kind === 'none';
  return {
    ok: !inaccessiblePage,
    live: true,
    finalUrl: root.finalUrl,
    hostname: safeHostname(root.finalUrl),
    reason: inaccessiblePage ? REASONS.login_required : null,
    title: page.title,
    description: page.description,
    snippet: page.snippet,
    siteName: page.siteName,
    canonicalUrl: page.canonicalUrl,
    contentType: root.mime,
    media,
    mediaReason,
    redirects: root.redirects,
  };
}

function safeHostname(value) {
  try {
    return new URL(value).hostname;
  } catch (_) {
    return '';
  }
}

function extractProviderText(data) {
  if (!data || typeof data !== 'object') return '';
  if (typeof data.output_text === 'string') return data.output_text;
  const parts = [];
  for (const item of Array.isArray(data.output) ? data.output : []) {
    if (typeof item?.text === 'string') parts.push(item.text);
    for (const content of Array.isArray(item?.content) ? item.content : []) {
      if (typeof content?.text === 'string') parts.push(content.text);
    }
  }
  return parts.join('\n').trim();
}

function parseJsonObject(text) {
  let value = String(text || '').trim();
  const fence = value.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence) value = fence[1].trim();
  const start = value.indexOf('{');
  const end = value.lastIndexOf('}');
  if (start >= 0 && end > start) value = value.slice(start, end + 1);
  try {
    return JSON.parse(value);
  } catch (_) {
    return null;
  }
}

function cleanSignals(value) {
  return (Array.isArray(value) ? value : [])
    .filter((item) => typeof item === 'string' && item.trim())
    .map((item) => item.trim().slice(0, 240))
    .slice(0, 6);
}

function baseForensics(media, providerStatus = 'not_run', checkedAt = new Date().toISOString()) {
  const limitations = [];
  if (media.kind === 'video' && media.analysis_scope === 'poster_or_thumbnail') {
    limitations.push('Only a poster or thumbnail was inspected; the video itself was not forensically analyzed.');
  } else if (media.kind === 'video') {
    limitations.push('Full video frame and audio forensics are unavailable in the configured provider.');
  } else if (media.kind === 'audio') {
    limitations.push('Audio and voice deepfake analysis is unavailable in the configured provider.');
  } else if (media.kind === 'none') {
    limitations.push('No publicly accessible media bytes were available for analysis.');
  } else if (!media.buffer) {
    limitations.push('Media bytes were not available for direct pixel analysis.');
  }
  return {
    verdict: media.kind === 'none' ? 'not_applicable' : 'insufficient',
    verdict_label_ar: media.kind === 'none' ? 'لا ينطبق' : 'أدلة غير كافية',
    verdict_label_en: media.kind === 'none' ? 'Not applicable' : 'Insufficient evidence',
    confidence: null,
    deepfake_risk: 'unknown',
    analysis_scope: media.analysis_scope || 'none',
    signals_for: [],
    signals_against: [],
    limitations,
    provider: 'none',
    provider_status: providerStatus,
    checked_at: checkedAt,
  };
}

async function analyzeImageWithGrok(media, context = {}, deps = {}, options = {}) {
  const checkedAt = new Date().toISOString();
  const fallback = baseForensics(media, 'not_run', checkedAt);
  if (!media?.buffer || !['image', 'video'].includes(media.kind)) return fallback;
  const apiKey = options.apiKey || process.env.GROK_API_KEY;
  if (!apiKey) {
    fallback.provider_status = 'skipped_no_key';
    fallback.limitations.push('Paid AI analysis was skipped because no provider key is configured.');
    return fallback;
  }
  const providerFetch = deps.providerFetch || globalThis.fetch;
  if (typeof providerFetch !== 'function') {
    fallback.provider_status = 'unavailable';
    fallback.limitations.push('The configured analysis provider is unavailable.');
    return fallback;
  }
  const model = options.model || process.env.GROK_VERIFY_MODEL || 'grok-4-1-fast-non-reasoning';
  const prompt = `You are a media-forensics evidence assistant for SANAD. Inspect only the supplied image pixels. Do not identify people. Do not claim authenticity merely because artifacts are absent. A single model opinion is not proof. Return JSON only:
{"verdict":"likely_real|likely_manipulated|insufficient","confidence":0.0,"deepfake_risk":"low|moderate|high|unknown","signals_for":["evidence supporting the verdict"],"signals_against":["counter-evidence or ambiguity"],"limitations":["specific limits"]}
Use likely_real only when direct pixel analysis has affirmative, coherent supporting signals. Use likely_manipulated only for concrete visible forensic inconsistencies. Otherwise use insufficient.
Media kind: ${media.kind}
Inspection scope: ${media.analysis_scope}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs || 25000);
  try {
    const response = await providerFetch(options.url || 'https://api.x.ai/v1/responses', {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model,
        input: [{
          role: 'user',
          content: [
            { type: 'input_text', text: prompt },
            {
              type: 'input_image',
              image_url: `data:${media.mime};base64,${media.buffer.toString('base64')}`,
              detail: 'high',
            },
          ],
        }],
        max_output_tokens: 700,
        store: false,
      }),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      fallback.provider = 'xai';
      fallback.provider_status = `http_${response.status}`;
      fallback.limitations.push('The configured provider did not complete the image analysis.');
      return fallback;
    }
    const parsed = parseJsonObject(extractProviderText(data));
    if (!parsed) {
      fallback.provider = 'xai';
      fallback.provider_status = 'invalid_response';
      fallback.limitations.push('The configured provider returned no usable forensic evidence.');
      return fallback;
    }
    const localSignals = cleanSignals(media.local_signals);
    const modelSignalsFor = cleanSignals(parsed.signals_for);
    const signalsFor = [...new Set([...localSignals, ...modelSignalsFor])].slice(0, 6);
    const signalsAgainst = cleanSignals(parsed.signals_against);
    const requestedVerdict = ['likely_real', 'likely_manipulated', 'insufficient'].includes(parsed.verdict)
      ? parsed.verdict
      : 'insufficient';
    const directPixels = ['original_media', 'embedded_media'].includes(media.analysis_scope);
    const evidenceConflict = signalsFor.length > 0 && signalsAgainst.length > 0;
    const independentlyGroundedManipulation =
      requestedVerdict === 'likely_manipulated' &&
      directPixels &&
      localSignals.length > 0 &&
      modelSignalsFor.length > 0 &&
      !evidenceConflict;
    const verdict = independentlyGroundedManipulation ? 'likely_manipulated' : 'insufficient';
    const confidence = verdict === 'insufficient'
      ? null
      : Math.max(0, Math.min(1, Number(parsed.confidence)));
    const labels = {
      likely_real: ['يبدو حقيقيًا', 'Likely real'],
      likely_manipulated: ['يبدو مُعالَجًا أو مُتلاعَبًا به', 'Likely manipulated'],
      insufficient: ['أدلة غير كافية', 'Insufficient evidence'],
    };
    const limitations = cleanSignals(parsed.limitations);
    limitations.push('This is a bounded single-model assessment, not proof of authenticity or manipulation.');
    if (requestedVerdict === 'likely_real') {
      limitations.push('No independent authenticity evidence was available, so a likely-real verdict was not issued.');
    } else if (requestedVerdict === 'likely_manipulated' && !localSignals.length) {
      limitations.push('The model-reported artifacts lacked a matching structured generative-workflow metadata signal.');
    } else if (verdict === 'likely_manipulated') {
      limitations.push('The matching embedded workflow metadata is not authenticated provenance and can be altered.');
    }
    if (!directPixels) limitations.push('The original media was not directly analyzed.');
    if (evidenceConflict) limitations.push('The available forensic signals conflict, so no directional verdict was issued.');
    const ticks = Number(data?.usage?.cost_in_usd_ticks || 0);
    return {
      verdict,
      verdict_label_ar: labels[verdict][0],
      verdict_label_en: labels[verdict][1],
      confidence: Number.isFinite(confidence) ? confidence : null,
      deepfake_risk: verdict === 'insufficient'
        ? 'unknown'
        : verdict === 'likely_manipulated'
        ? (['moderate', 'high'].includes(parsed.deepfake_risk) ? parsed.deepfake_risk : 'moderate')
        : (['low', 'moderate', 'high', 'unknown'].includes(parsed.deepfake_risk) ? parsed.deepfake_risk : 'unknown'),
      analysis_scope: media.analysis_scope,
      signals_for: signalsFor,
      signals_against: signalsAgainst,
      limitations: [...new Set(limitations)].slice(0, 8),
      provider: 'xai',
      provider_status: 'completed',
      checked_at: checkedAt,
      usd: ticks > 0 ? ticks / 1e10 : 0,
    };
  } catch (error) {
    fallback.provider = 'xai';
    fallback.provider_status = error?.name === 'AbortError' ? 'timeout' : 'failed';
    fallback.limitations.push(
      error?.name === 'AbortError'
        ? 'The configured provider timed out before returning forensic evidence.'
        : 'The configured provider failed before returning forensic evidence.'
    );
    return fallback;
  } finally {
    clearTimeout(timeout);
  }
}

module.exports = {
  DEFAULT_LIMITS,
  REASONS,
  analyzeImageWithGrok,
  baseForensics,
  extractPageMetadata,
  inspectPublicUrl,
  isPublicIp,
  resolvePublicHost,
  secureFetchResource,
  sniffMime,
  validatePublicUrl,
};
