'use strict';

const crypto = require('crypto');

const API_VERSION = 'v1';
const DEFAULT_DATA_BASE =
  'https://raw.githubusercontent.com/SoldiomAI/sanad-data/main/daily';
const MAX_LIMIT = 100;
const DEFAULT_LIMIT = 25;
const MAX_PAGE = 1000;
const ALLOWED_WEBHOOK_EVENTS = [
  'signal.created',
  'signal.updated',
  'event.created',
  'event.updated',
];
const ROUTE_SCOPES = {
  events: 'read:events',
  signals: 'read:signals',
  countries: 'read:metadata',
  topics: 'read:metadata',
  briefings: 'read:briefings',
  webhooks: 'webhooks:write',
};
const rateBuckets = new Map();

class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function envConfig(env = process.env) {
  return {
    enabled: env.SANAD_ENTERPRISE_API_ENABLED === 'true',
    authUrl: String(env.SANAD_ENTERPRISE_AUTH_URL || '').trim(),
    authToken: String(env.SANAD_ENTERPRISE_AUTH_TOKEN || '').trim(),
    dataBase: String(env.SANAD_ENTERPRISE_DATA_BASE || DEFAULT_DATA_BASE).replace(/\/+$/, ''),
    webhooksEnabled: env.SANAD_ENTERPRISE_WEBHOOKS_ENABLED === 'true',
    localRateLimit: boundedInteger(
      env.SANAD_ENTERPRISE_LOCAL_RATE_LIMIT || '60',
      1,
      600,
      60
    ),
  };
}

function backendAvailable(config) {
  if (!config.enabled || !config.authUrl || !config.authToken) return false;
  try {
    return new URL(config.authUrl).protocol === 'https:';
  } catch (_) {
    return false;
  }
}

function boundedInteger(value, min, max, fallback) {
  if (!/^\d+$/.test(String(value || ''))) return fallback;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= min && parsed <= max
    ? parsed
    : fallback;
}

function text(value, max = 2000) {
  return typeof value === 'string' ? value.slice(0, max) : '';
}

function stringList(value, maxItems = 25, maxLength = 100) {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item) => typeof item === 'string')
    .slice(0, maxItems)
    .map((item) => item.slice(0, maxLength));
}

function numberOrNull(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function sanitizeEvidence(row) {
  if (!row || typeof row !== 'object') return null;
  return {
    source_ref: text(row.source_ref || row.id, 100),
    url: /^https?:\/\//i.test(String(row.url || '')) ? text(row.url, 4000) : '',
    publisher: text(row.publisher || row.source_name, 300),
    grade: text(row.grade || row.source_grade, 100),
    published_at: text(row.published_at || row.observed_at, 100),
    title: text(row.title, 1000),
    title_en: text(row.title_en, 1000),
    dataset: text(row.dataset, 100),
  };
}

function sanitizeContradiction(row) {
  if (!row || typeof row !== 'object') return null;
  return {
    type: text(row.type, 100),
    evidence_ids: stringList(row.evidence_ids, 20, 100),
    detail: text(row.detail, 1000),
  };
}

function sanitizeEvent(row) {
  if (!row || typeof row !== 'object') return null;
  return {
    id: text(row.id, 100),
    type: text(row.type, 100),
    title: text(row.title, 1000),
    title_en: text(row.title_en, 1000),
    observed_facts: stringList(row.observed_facts, 50, 2000),
    sanad_assessment: text(row.sanad_assessment, 2000),
    inference: text(row.inference, 2000),
    uncertainty: text(row.uncertainty, 2000),
    confidence: numberOrNull(row.confidence),
    severity: text(row.severity, 50),
    countries: stringList(row.countries),
    sectors: stringList(row.sectors),
    topics: stringList(row.topics),
    evidence: Array.isArray(row.evidence)
      ? row.evidence.map(sanitizeEvidence).filter(Boolean)
      : [],
    contradictions: Array.isArray(row.contradictions)
      ? row.contradictions.map(sanitizeContradiction).filter(Boolean)
      : [],
    created_at: text(row.created_at, 100),
    updated_at: text(row.updated_at, 100),
  };
}

function sanitizeSignal(row) {
  if (!row || typeof row !== 'object') return null;
  return {
    id: text(row.id, 100),
    type: text(row.type, 100),
    title: text(row.title, 1000),
    title_en: text(row.title_en, 1000),
    summary: text(row.summary, 2000),
    observed_at: text(row.observed_at, 100),
    observed_facts: stringList(row.observed_facts, 50, 2000),
    sanad_assessment: text(row.assessment || row.sanad_assessment, 2000),
    inference: text(row.inference, 2000),
    uncertainty: text(row.uncertainty, 2000),
    confidence: numberOrNull(row.confidence),
    severity: text(row.severity, 50),
    countries: stringList(row.countries),
    sectors: stringList(row.sectors),
    topics: stringList(row.topics),
    evidence: Array.isArray(row.evidence)
      ? row.evidence.map(sanitizeEvidence).filter(Boolean)
      : [],
    contradictions: Array.isArray(row.contradictions)
      ? row.contradictions.map(sanitizeContradiction).filter(Boolean)
      : [],
    event_ids: stringList(row.event_ids, 50, 100),
    created_at: text(row.created_at, 100),
    updated_at: text(row.updated_at, 100),
  };
}

function requestUrl(req) {
  return new URL(req.url || '/', 'https://api.isnad.news');
}

function routeFromRequest(req) {
  const queryRoute = req.query && req.query.route;
  const raw = Array.isArray(queryRoute) ? queryRoute[0] : queryRoute;
  if (raw) return String(raw).replace(/^\/+|\/+$/g, '').toLowerCase();
  return requestUrl(req).pathname.replace(/^\/api\/v1\/?|\/+$/g, '').toLowerCase();
}

function parseFilters(req) {
  const params = requestUrl(req).searchParams;
  const read = (name, max = 100) => {
    const values = params.getAll(name);
    if (values.length > 1) {
      throw new ApiError(400, 'invalid_filter', `${name} may be supplied once`);
    }
    const value = String(values[0] || '').trim();
    if (value.length > max) {
      throw new ApiError(400, 'invalid_filter', `${name} is too long`);
    }
    return value;
  };
  const limitRaw = read('limit', 3);
  const pageRaw = read('page', 4);
  if (limitRaw && !/^\d+$/.test(limitRaw)) {
    throw new ApiError(400, 'invalid_pagination', 'limit must be an integer');
  }
  if (pageRaw && !/^\d+$/.test(pageRaw)) {
    throw new ApiError(400, 'invalid_pagination', 'page must be an integer');
  }
  const limit = limitRaw ? Number(limitRaw) : DEFAULT_LIMIT;
  const page = pageRaw ? Number(pageRaw) : 1;
  if (limit < 1 || limit > MAX_LIMIT || page < 1 || page > MAX_PAGE) {
    throw new ApiError(
      400,
      'invalid_pagination',
      `limit must be 1-${MAX_LIMIT} and page must be 1-${MAX_PAGE}`
    );
  }
  return {
    limit,
    page,
    country: read('country').toLowerCase(),
    topic: read('topic'),
    sector: read('sector').toLowerCase(),
    type: read('type').toLowerCase(),
    severity: read('severity').toLowerCase(),
    q: read('q', 200).toLowerCase(),
  };
}

function matchesFilters(row, filters) {
  const includes = (items, wanted) =>
    !wanted || items.some((item) => String(item).toLowerCase() === wanted.toLowerCase());
  if (!includes(row.countries || [], filters.country)) return false;
  if (!includes(row.topics || [], filters.topic)) return false;
  if (!includes(row.sectors || [], filters.sector)) return false;
  if (filters.type && String(row.type || '').toLowerCase() !== filters.type) return false;
  if (
    filters.severity &&
    String(row.severity || '').toLowerCase() !== filters.severity
  ) {
    return false;
  }
  if (filters.q) {
    const haystack = [row.title, row.title_en, row.summary]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    if (!haystack.includes(filters.q)) return false;
  }
  return true;
}

function paginate(items, filters) {
  const total = items.length;
  const start = (filters.page - 1) * filters.limit;
  return {
    data: items.slice(start, start + filters.limit),
    pagination: {
      page: filters.page,
      limit: filters.limit,
      total,
      pages: Math.ceil(total / filters.limit),
      has_next: start + filters.limit < total,
    },
  };
}

async function fetchJson(url, fetchImpl = fetch) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetchImpl(url, {
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        'User-Agent': 'SANAD-Enterprise-API/1.0',
      },
    });
    if (!response.ok) {
      throw new ApiError(502, 'published_data_unavailable', 'Published SANAD data is unavailable');
    }
    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(502, 'published_data_unavailable', 'Published SANAD data is unavailable');
  } finally {
    clearTimeout(timer);
  }
}

async function loadPublished(config, fetchImpl) {
  const [eventsDoc, signalsDoc] = await Promise.all([
    fetchJson(`${config.dataBase}/events.json`, fetchImpl),
    fetchJson(`${config.dataBase}/ontime-signals.json`, fetchImpl),
  ]);
  if (!Array.isArray(eventsDoc.events) || !Array.isArray(signalsDoc.signals)) {
    throw new ApiError(502, 'invalid_published_data', 'Published SANAD data has an invalid shape');
  }
  return {
    events: {
      schemaVersion: text(eventsDoc.schema_version, 50),
      updatedAt: text(eventsDoc.updated, 100),
      items: eventsDoc.events.map(sanitizeEvent).filter(Boolean),
    },
    signals: {
      schemaVersion: text(signalsDoc.schema_version, 50),
      updatedAt: text(signalsDoc.updated_at || signalsDoc.generated_at, 100),
      cursor: text(signalsDoc.cursor, 200),
      items: signalsDoc.signals.map(sanitizeSignal).filter(Boolean),
    },
  };
}

function extractApiKey(req) {
  const direct = String(req.headers?.['x-api-key'] || '').trim();
  const bearer = String(req.headers?.authorization || '').match(/^Bearer\s+(.+)$/i);
  if (direct && bearer) {
    throw new ApiError(400, 'ambiguous_credentials', 'Supply one API credential');
  }
  return direct || (bearer ? bearer[1].trim() : '');
}

function timingSafeEqualText(a, b) {
  const left = Buffer.from(String(a || ''), 'utf8');
  const right = Buffer.from(String(b || ''), 'utf8');
  if (left.length !== right.length) return false;
  return crypto.timingSafeEqual(left, right);
}

function consumeLocalRate(key, limit, now = Date.now()) {
  const minute = Math.floor(now / 60000);
  const digest = crypto.createHash('sha256').update(key).digest('hex');
  let bucket = rateBuckets.get(digest);
  if (!bucket || bucket.minute !== minute) bucket = { minute, count: 0 };
  bucket.count += 1;
  rateBuckets.set(digest, bucket);
  if (rateBuckets.size > 5000) {
    for (const [id, candidate] of rateBuckets) {
      if (candidate.minute !== minute) rateBuckets.delete(id);
    }
  }
  return {
    allowed: bucket.count <= limit,
    limit,
    remaining: Math.max(0, limit - bucket.count),
    resetAt: new Date((minute + 1) * 60000).toISOString(),
  };
}

async function callAuthAuthority(req, route, key, config, fetchImpl = fetch) {
  const requestId = crypto.randomUUID();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  let response;
  try {
    response = await fetchImpl(config.authUrl, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-SANAD-Adapter-Secret': config.authToken,
      },
      body: JSON.stringify({
        action: 'verify_api_key_and_record_usage',
        credential: key,
        key_prefix: key.slice(0, 10),
        request: {
          id: requestId,
          api_version: API_VERSION,
          method: String(req.method || 'GET').toUpperCase(),
          route,
        },
      }),
    });
  } catch (_) {
    throw new ApiError(
      503,
      'enterprise_auth_unavailable',
      'Enterprise authentication is temporarily unavailable'
    );
  } finally {
    clearTimeout(timer);
  }
  let body = {};
  try {
    body = await response.json();
  } catch (_) {
    throw new ApiError(
      503,
      'enterprise_auth_invalid_response',
      'Enterprise authentication returned an invalid response'
    );
  }
  if (response.status === 401 || body.valid === false) {
    const code = body.revoked ? 'revoked_api_key' : 'invalid_api_key';
    throw new ApiError(401, code, body.revoked ? 'API key is revoked' : 'API key is invalid');
  }
  if (!response.ok) {
    throw new ApiError(
      503,
      'enterprise_auth_unavailable',
      'Enterprise authentication is temporarily unavailable'
    );
  }
  return body;
}

async function checkAuthAuthority(config, fetchImpl = fetch) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetchImpl(config.authUrl, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-SANAD-Adapter-Secret': config.authToken,
      },
      body: JSON.stringify({ action: 'status', api_version: API_VERSION }),
    });
    if (!response.ok) return false;
    const body = await response.json();
    return body.available === true;
  } catch (_) {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function authenticate(req, route, config, dependencies = {}) {
  if (!backendAvailable(config)) {
    throw new ApiError(
      503,
      'enterprise_backend_disabled',
      'Enterprise API authentication and audit backend is not configured'
    );
  }
  const key = extractApiKey(req);
  if (!/^sk_[A-Za-z0-9_-]{24,125}$/.test(key)) {
    throw new ApiError(401, 'invalid_api_key', 'A valid API key is required');
  }
  const localRate = consumeLocalRate(
    key,
    dependencies.localRateLimit || config.localRateLimit,
    dependencies.now ? dependencies.now() : Date.now()
  );
  if (!localRate.allowed) {
    throw new ApiError(429, 'rate_limit_exceeded', 'API rate limit exceeded', localRate);
  }
  const auth = dependencies.verifyAuthority
    ? await dependencies.verifyAuthority({ req, route, key, keyPrefix: key.slice(0, 10) })
    : await callAuthAuthority(req, route, key, config, dependencies.fetch);
  if (!auth || auth.valid !== true) {
    throw new ApiError(401, 'invalid_api_key', 'API key is invalid');
  }
  if (auth.revoked === true) {
    throw new ApiError(401, 'revoked_api_key', 'API key is revoked');
  }
  if (
    !auth.key_prefix ||
    !timingSafeEqualText(auth.key_prefix, key.slice(0, 10))
  ) {
    throw new ApiError(
      503,
      'enterprise_auth_invalid_response',
      'Enterprise authentication returned an invalid key binding'
    );
  }
  if (!auth.org_id || !auth.key_id || !Array.isArray(auth.scopes)) {
    throw new ApiError(
      503,
      'enterprise_auth_invalid_response',
      'Enterprise authentication omitted required identity or scope fields'
    );
  }
  if (auth.audit_recorded !== true) {
    throw new ApiError(
      503,
      'enterprise_audit_unavailable',
      'Enterprise usage audit could not be recorded'
    );
  }
  const persistentRate = auth.rate_limit;
  if (
    !persistentRate ||
    typeof persistentRate.allowed !== 'boolean' ||
    !Number.isFinite(persistentRate.limit) ||
    !Number.isFinite(persistentRate.remaining) ||
    !persistentRate.reset_at
  ) {
    throw new ApiError(
      503,
      'enterprise_rate_limit_unavailable',
      'Enterprise persistent rate limit is not configured'
    );
  }
  if (!persistentRate.allowed) {
    throw new ApiError(429, 'rate_limit_exceeded', 'API rate limit exceeded', {
      limit: persistentRate.limit,
      remaining: persistentRate.remaining,
      resetAt: persistentRate.reset_at,
    });
  }
  const requiredScope = ROUTE_SCOPES[route];
  if (
    requiredScope &&
    !auth.scopes.includes('*') &&
    !(requiredScope.startsWith('read:') && auth.scopes.includes('read:*')) &&
    !auth.scopes.includes(requiredScope)
  ) {
    throw new ApiError(403, 'insufficient_scope', `API key lacks ${requiredScope}`);
  }
  return {
    orgId: auth.org_id,
    keyId: auth.key_id,
    rate: {
      limit: persistentRate.limit,
      remaining: persistentRate.remaining,
      resetAt: persistentRate.reset_at,
    },
  };
}

function dimensionRows(published, field) {
  const counts = new Map();
  for (const [kind, rows] of [
    ['event_count', published.events.items],
    ['signal_count', published.signals.items],
  ]) {
    for (const row of rows) {
      for (const value of row[field] || []) {
        const current = counts.get(value) || { id: value, event_count: 0, signal_count: 0 };
        current[kind] += 1;
        counts.set(value, current);
      }
    }
  }
  return [...counts.values()].sort(
    (a, b) =>
      b.event_count + b.signal_count - (a.event_count + a.signal_count) ||
      a.id.localeCompare(b.id)
  );
}

function stableBriefing(signals, filters) {
  const severity = { critical: 4, high: 3, warning: 2, medium: 2, info: 1, low: 0 };
  const selected = signals
    .filter((row) => matchesFilters(row, filters))
    .sort(
      (a, b) =>
        (severity[String(b.severity).toLowerCase()] || 0) -
          (severity[String(a.severity).toLowerCase()] || 0) ||
        (b.confidence || 0) - (a.confidence || 0) ||
        a.id.localeCompare(b.id)
    )
    .slice(0, Math.min(filters.limit, 25));
  const withId = (row, value) => ({ signal_id: row.id, value });
  const evidence = [];
  const seenEvidence = new Set();
  for (const row of selected) {
    for (const item of row.evidence) {
      const key = item.source_ref || item.url;
      if (!key || seenEvidence.has(key)) continue;
      seenEvidence.add(key);
      evidence.push({ signal_id: row.id, ...item });
    }
  }
  return {
    briefing_type: filters.sector ? 'sector' : 'daily',
    sector: filters.sector || null,
    methodology: 'deterministic extraction from published SANAD signals; no model call',
    sections: {
      OBSERVED_FACT: selected.flatMap((row) =>
        row.observed_facts.map((value) => withId(row, value))
      ),
      SANAD_ASSESSMENT: selected
        .filter((row) => row.sanad_assessment)
        .map((row) => withId(row, row.sanad_assessment)),
      INFERENCE: selected
        .filter((row) => row.inference)
        .map((row) => withId(row, row.inference)),
      UNCERTAINTY: selected
        .filter((row) => row.uncertainty)
        .map((row) => withId(row, row.uncertainty)),
      EVIDENCE: evidence,
      WHAT_TO_WATCH: selected.map((row) => ({
        signal_id: row.id,
        value: `New attributable evidence or changes to severity/confidence for: ${row.title}`,
        countries: row.countries,
        sectors: row.sectors,
        topics: row.topics,
      })),
    },
    signal_ids: selected.map((row) => row.id),
  };
}

function envelope(resource, source, payload) {
  return {
    api_version: API_VERSION,
    schema_version: source.schemaVersion,
    resource,
    read_only: true,
    source_updated_at: source.updatedAt,
    classification: {
      observed_fact: 'Directly extracted from attributable published evidence',
      sanad_assessment: 'Deterministic SANAD assessment over published evidence',
      inference: 'Bounded interpretation; not an observed fact',
      uncertainty: 'Known limitation or unresolved ambiguity',
    },
    ...payload,
  };
}

function json(res, status, body, rate) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  if (rate) {
    res.setHeader('RateLimit-Limit', String(rate.limit));
    res.setHeader('RateLimit-Remaining', String(rate.remaining));
    res.setHeader('RateLimit-Reset', String(rate.resetAt));
  }
  res.end(JSON.stringify(body));
}

function setCors(req, res) {
  const origin = String(req.headers?.origin || '');
  const host = String(req.headers?.host || '');
  if (origin && host) {
    try {
      if (new URL(origin).host === host) {
        res.setHeader('Access-Control-Allow-Origin', origin);
        res.setHeader('Vary', 'Origin');
      }
    } catch (_) {
      // Invalid origins receive no CORS access.
    }
  }
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Authorization, X-API-Key');
}

function createHandler(dependencies = {}) {
  return async function handler(req, res) {
    setCors(req, res);
    const config = dependencies.config || envConfig();
    const method = String(req.method || 'GET').toUpperCase();
    const route = routeFromRequest(req);
    if (method === 'OPTIONS') {
      res.statusCode = 204;
      return res.end();
    }
    if (route === 'status') {
      if (method !== 'GET') {
        return json(res, 405, {
          error: { code: 'method_not_allowed', message: 'Only GET is allowed' },
        });
      }
      const configured = backendAvailable(config);
      const available =
        configured &&
        (dependencies.checkStatus
          ? await dependencies.checkStatus()
          : await checkAuthAuthority(config, dependencies.fetch));
      return json(res, available ? 200 : 503, {
        api_version: API_VERSION,
        available,
        authentication: 'customer_api_key',
        webhooks_enabled: available && config.webhooksEnabled,
      });
    }
    try {
      if (route === 'webhooks') {
        if (!config.webhooksEnabled) {
          throw new ApiError(
            503,
            'webhooks_disabled',
            'Enterprise webhooks are disabled'
          );
        }
        if (method !== 'POST') {
          throw new ApiError(405, 'method_not_allowed', 'Webhook registration requires POST');
        }
        await authenticate(req, route, config, dependencies);
        throw new ApiError(
          501,
          'webhook_delivery_not_implemented',
          'Webhook delivery is not implemented in this release',
          { allowed_event_types: ALLOWED_WEBHOOK_EVENTS }
        );
      }
      if (method !== 'GET') {
        throw new ApiError(405, 'method_not_allowed', 'Only GET is allowed');
      }
      if (!Object.prototype.hasOwnProperty.call(ROUTE_SCOPES, route)) {
        throw new ApiError(404, 'not_found', 'Unknown enterprise API resource');
      }
      const identity = await authenticate(req, route, config, dependencies);
      const filters = parseFilters(req);
      const published = dependencies.loadPublished
        ? await dependencies.loadPublished()
        : await loadPublished(config, dependencies.fetch);
      let response;
      if (route === 'events') {
        const rows = published.events.items.filter((row) => matchesFilters(row, filters));
        response = envelope('events', published.events, paginate(rows, filters));
      } else if (route === 'signals') {
        const rows = published.signals.items.filter((row) => matchesFilters(row, filters));
        response = envelope('signals', published.signals, {
          source_cursor: published.signals.cursor,
          ...paginate(rows, filters),
        });
      } else if (route === 'countries' || route === 'topics') {
        let rows = dimensionRows(published, route);
        if (filters.q) {
          rows = rows.filter((row) => row.id.toLowerCase().includes(filters.q));
        }
        response = envelope(route, published.events, paginate(rows, filters));
      } else {
        response = envelope(
          'briefings',
          published.signals,
          stableBriefing(published.signals.items, filters)
        );
      }
      return json(res, 200, response, identity.rate);
    } catch (error) {
      const known = error instanceof ApiError;
      const status = known ? error.status : 500;
      return json(res, status, {
        api_version: API_VERSION,
        error: {
          code: known ? error.code : 'internal_error',
          message: known ? error.message : 'Internal enterprise API error',
          ...(known && error.details ? { details: error.details } : {}),
        },
      });
    }
  };
}

module.exports = {
  ALLOWED_WEBHOOK_EVENTS,
  ApiError,
  createHandler,
  envConfig,
  checkAuthAuthority,
  loadPublished,
  matchesFilters,
  parseFilters,
  sanitizeEvent,
  sanitizeSignal,
  stableBriefing,
  timingSafeEqualText,
};
