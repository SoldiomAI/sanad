'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const {
  createHandler,
  loadPublished,
  sanitizeSignal,
} = require('../api/_enterprise-v1');

const API_KEY = `sk_${'a'.repeat(32)}`;
const BASE_CONFIG = {
  enabled: true,
  authUrl: 'https://auth.example.test/verify',
  authToken: 'adapter-secret',
  dataBase: 'https://data.example.test',
  webhooksEnabled: false,
  localRateLimit: 60,
};
const EVIDENCE = {
  source_ref: 'ev_1',
  url: 'https://example.test/report',
  publisher: 'Example Wire',
  grade: 'حسن',
  published_at: '2026-08-30T00:00:00Z',
  title: 'Attributed report',
  title_en: 'Attributed report',
  dataset: 'news',
};
const SIGNALS = [
  {
    id: 'sig_1',
    type: 'multi-source-event',
    title: 'Energy signal',
    title_en: 'Energy signal',
    summary: 'Published summary',
    observed_at: '2026-08-30T00:00:00Z',
    observed_facts: ['Two attributable reports were published.'],
    sanad_assessment: 'The evidence converges.',
    inference: 'Operational impact is not established.',
    uncertainty: 'More direct evidence is required.',
    confidence: 0.8,
    severity: 'warning',
    countries: ['kw'],
    sectors: ['energy'],
    topics: ['shipping'],
    evidence: [EVIDENCE],
    contradictions: [],
    event_ids: ['evt_1'],
    created_at: '2026-08-30T00:00:00Z',
    updated_at: '2026-08-30T00:00:00Z',
  },
  {
    id: 'sig_2',
    type: 'watchlist-match',
    title: 'Finance signal',
    title_en: 'Finance signal',
    summary: 'Another summary',
    observed_at: '2026-08-30T00:00:00Z',
    observed_facts: ['One attributable report was published.'],
    sanad_assessment: 'Attention threshold met.',
    inference: 'Attention does not establish intent.',
    uncertainty: 'Keyword ambiguity remains.',
    confidence: 0.6,
    severity: 'info',
    countries: ['ae'],
    sectors: ['finance'],
    topics: ['economy'],
    evidence: [{ ...EVIDENCE, source_ref: 'ev_2' }],
    contradictions: [],
    event_ids: [],
    created_at: '2026-08-30T00:00:00Z',
    updated_at: '2026-08-30T00:00:00Z',
  },
];
const PUBLISHED = {
  events: {
    schemaVersion: '1.0',
    updatedAt: '2026-08-30T00:00:00Z',
    items: SIGNALS.map((row, index) => ({
      ...row,
      id: `evt_${index + 1}`,
      sanad_assessment: row.sanad_assessment,
    })),
  },
  signals: {
    schemaVersion: '1.0',
    updatedAt: '2026-08-30T00:00:00Z',
    cursor: 'sha256:test',
    items: SIGNALS,
  },
};

function request(route, query = '', key = API_KEY, method = 'GET') {
  return {
    method,
    url: `/api/v1?route=${route}${query ? `&${query}` : ''}`,
    query: { route },
    headers: {
      host: 'www.isnad.news',
      ...(key ? { 'x-api-key': key } : {}),
    },
  };
}

function response() {
  return {
    headers: {},
    setHeader(name, value) {
      this.headers[name] = value;
    },
    end(body = '') {
      this.body = body;
      this.json = body ? JSON.parse(body) : null;
    },
  };
}

function validAuth(overrides = {}) {
  return {
    valid: true,
    revoked: false,
    key_prefix: API_KEY.slice(0, 10),
    org_id: 'org_1',
    key_id: 'key_1',
    scopes: ['read:*'],
    audit_recorded: true,
    rate_limit: {
      allowed: true,
      limit: 100,
      remaining: 99,
      reset_at: '2026-08-30T01:00:00Z',
    },
    ...overrides,
  };
}

function handler(auth = validAuth(), options = {}) {
  return createHandler({
    config: { ...BASE_CONFIG, ...options.config },
    verifyAuthority: async () => auth,
    loadPublished: async () => PUBLISHED,
    localRateLimit: options.localRateLimit,
    now: options.now,
  });
}

async function invoke(currentHandler, req) {
  const res = response();
  await currentHandler(req, res);
  return res;
}

test('fails closed when the enterprise backend is disabled', async () => {
  const res = await invoke(
    createHandler({
      config: { ...BASE_CONFIG, enabled: false },
      verifyAuthority: async () => {
        throw new Error('must not run');
      },
    }),
    request('events')
  );
  assert.equal(res.statusCode, 503);
  assert.equal(res.json.error.code, 'enterprise_backend_disabled');
});

test('status is available only when the configured authority confirms readiness', async () => {
  const unavailable = await invoke(
    createHandler({ config: BASE_CONFIG, checkStatus: async () => false }),
    request('status', '', '')
  );
  assert.equal(unavailable.statusCode, 503);
  assert.equal(unavailable.json.available, false);
  const available = await invoke(
    createHandler({ config: BASE_CONFIG, checkStatus: async () => true }),
    request('status', '', '')
  );
  assert.equal(available.statusCode, 200);
  assert.equal(available.json.available, true);
});

test('rejects missing, invalid, and revoked API keys', async (t) => {
  await t.test('missing', async () => {
    const res = await invoke(handler(), request('events', '', ''));
    assert.equal(res.statusCode, 401);
    assert.equal(res.json.error.code, 'invalid_api_key');
  });
  await t.test('invalid', async () => {
    const res = await invoke(handler({ valid: false }), request('events'));
    assert.equal(res.statusCode, 401);
    assert.equal(res.json.error.code, 'invalid_api_key');
  });
  await t.test('revoked', async () => {
    const res = await invoke(handler(validAuth({ revoked: true })), request('events'));
    assert.equal(res.statusCode, 401);
    assert.equal(res.json.error.code, 'revoked_api_key');
  });
});

test('enforces scopes and a successfully recorded audit', async () => {
  const forbidden = await invoke(
    handler(validAuth({ scopes: ['read:events'] })),
    request('signals')
  );
  assert.equal(forbidden.statusCode, 403);
  const unaudited = await invoke(
    handler(validAuth({ audit_recorded: false })),
    request('events')
  );
  assert.equal(unaudited.statusCode, 503);
  assert.equal(unaudited.json.error.code, 'enterprise_audit_unavailable');
});

test('filters and paginates bounded signal responses', async () => {
  const first = await invoke(
    handler(),
    request('signals', 'country=kw&sector=energy&limit=1&page=1')
  );
  assert.equal(first.statusCode, 200);
  assert.equal(first.json.data.length, 1);
  assert.equal(first.json.data[0].id, 'sig_1');
  assert.equal(first.json.pagination.total, 1);
  const invalid = await invoke(handler(), request('signals', 'limit=101'));
  assert.equal(invalid.statusCode, 400);
  assert.equal(invalid.json.error.code, 'invalid_pagination');
});

test('returns bounded country and topic indexes from events and signals', async () => {
  const countries = await invoke(handler(), request('countries', 'q=kw&limit=10'));
  assert.equal(countries.statusCode, 200);
  assert.deepEqual(countries.json.data, [
    { id: 'kw', event_count: 1, signal_count: 1 },
  ]);
  const topics = await invoke(handler(), request('topics', 'q=shipping&limit=10'));
  assert.equal(topics.statusCode, 200);
  assert.deepEqual(topics.json.data, [
    { id: 'shipping', event_count: 1, signal_count: 1 },
  ]);
});

test('allowlists evidence and redacts internal fields recursively', () => {
  const signal = sanitizeSignal({
    ...SIGNALS[0],
    internal_prompt: 'secret prompt',
    raw_control_state: { secret: true },
    evidence: [
      {
        ...EVIDENCE,
        credentials: 'secret credential',
        internal_rule: 'secret rule',
      },
    ],
  });
  const encoded = JSON.stringify(signal);
  assert.equal(encoded.includes('internal_prompt'), false);
  assert.equal(encoded.includes('raw_control_state'), false);
  assert.equal(encoded.includes('credentials'), false);
  assert.equal(encoded.includes('internal_rule'), false);
  assert.equal(signal.evidence[0].url, EVIDENCE.url);
});

test('applies a local burst rate limit in addition to persistent authority limits', async () => {
  let now = Date.parse('2026-08-30T00:00:00Z');
  const currentHandler = handler(validAuth(), {
    localRateLimit: 2,
    now: () => now,
  });
  assert.equal((await invoke(currentHandler, request('events'))).statusCode, 200);
  assert.equal((await invoke(currentHandler, request('events'))).statusCode, 200);
  const limited = await invoke(currentHandler, request('events'));
  assert.equal(limited.statusCode, 429);
  assert.equal(limited.json.error.code, 'rate_limit_exceeded');
  now += 60000;
  assert.equal((await invoke(currentHandler, request('events'))).statusCode, 200);
});

test('produces deterministic, explicitly separated briefing sections', async () => {
  const currentHandler = handler();
  const first = await invoke(
    currentHandler,
    request('briefings', 'sector=energy&limit=10')
  );
  const second = await invoke(
    currentHandler,
    request('briefings', 'sector=energy&limit=10')
  );
  assert.equal(first.statusCode, 200);
  assert.deepEqual(first.json.sections, second.json.sections);
  assert.deepEqual(Object.keys(first.json.sections), [
    'OBSERVED_FACT',
    'SANAD_ASSESSMENT',
    'INFERENCE',
    'UNCERTAINTY',
    'EVIDENCE',
    'WHAT_TO_WATCH',
  ]);
  assert.deepEqual(first.json.signal_ids, ['sig_1']);
  assert.equal(first.json.sections.EVIDENCE[0].url, EVIDENCE.url);
});

test('keeps the webhook contract disabled by default without calling auth', async () => {
  const res = await invoke(
    createHandler({
      config: BASE_CONFIG,
      verifyAuthority: async () => {
        throw new Error('must not authenticate or deliver');
      },
    }),
    request('webhooks', '', API_KEY, 'POST')
  );
  assert.equal(res.statusCode, 503);
  assert.equal(res.json.error.code, 'webhooks_disabled');
});

test('loads the checked-in generated products through the production allowlist', async () => {
  const root = path.resolve(__dirname, '..');
  const published = await loadPublished(BASE_CONFIG, async (url) => {
    const name = url.endsWith('/events.json') ? 'events.json' : 'ontime-signals.json';
    return new Response(fs.readFileSync(path.join(root, 'daily', name), 'utf8'), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  });
  assert.equal(published.events.schemaVersion, '1.0');
  assert.equal(published.signals.schemaVersion, '1.0');
  assert.ok(published.events.items.length > 0);
  assert.ok(published.signals.items.length > 0);
  const encoded = JSON.stringify(published);
  for (const forbidden of ['internal_prompt', 'raw_control_state', 'credentials']) {
    assert.equal(encoded.includes(forbidden), false);
  }
});
