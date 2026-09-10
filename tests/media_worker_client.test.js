'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const test = require('node:test');

const {
  MAX_MEDIA_BYTES,
  analyzeWithWorker,
  normalizeManifest,
  validWorkerEndpoint,
} = require('../api/_media-worker');

function media(overrides = {}) {
  const buffer = overrides.buffer || Buffer.from('ffd8ffe000104a4649460001', 'hex');
  return {
    kind: 'image',
    mime: 'image/jpeg',
    buffer,
    truncated: false,
    analysis_scope: 'original_media',
    content_digest: crypto.createHash('sha256').update(buffer).digest('hex'),
    ...overrides,
  };
}

const MANIFEST = {
  endpoint: 'https://soldiom-sanad-media-worker.hf.space/analyze',
  capabilities: ['image', 'video', 'audio'],
  deployed_at: '2026-09-10T00:00:00Z',
  version: 'abc123',
};

test('worker manifest accepts only ready HTTPS Hugging Face analysis endpoints', () => {
  assert.equal(validWorkerEndpoint(MANIFEST.endpoint), true);
  for (const endpoint of [
    'http://soldiom-sanad-media-worker.hf.space/analyze',
    'https://example.com/analyze',
    'https://soldiom-sanad-media-worker.hf.space/health',
    'https://soldiom-sanad-media-worker.hf.space/analyze?next=internal',
  ]) {
    assert.equal(validWorkerEndpoint(endpoint), false, endpoint);
  }
  assert.deepEqual(normalizeManifest({ ...MANIFEST, ready: true }), MANIFEST);
  assert.equal(normalizeManifest({ ...MANIFEST, ready: false }), null);
});

test('worker call forwards only bounded media evidence and the incoming OIDC bearer', async () => {
  const input = media();
  let captured;
  const result = await analyzeWithWorker(input, 'short-lived-vercel-token', {
    loadWorkerManifest: async () => MANIFEST,
    workerFetch: async (url, options) => {
      captured = { url, options, body: JSON.parse(options.body) };
      return new Response(JSON.stringify({
        verdict: 'likely_real',
        confidence: 0.82,
        deepfake_risk_code: 'low',
        signals_for: ['JPEG structure parsed cleanly.'],
        signals_against: [],
        limitations: ['Bounded heuristic analysis.'],
        provider: 'gemini',
        provider_status: 'completed',
        checked_at: '2026-09-10T00:00:00Z',
        analysis_scope: 'original_media',
        bytes_analyzed: input.buffer.length,
        model_version: 'gemini-2.5-flash',
        worker_version: MANIFEST.version,
      }), { status: 200 });
    },
  });

  assert.equal(captured.url, MANIFEST.endpoint);
  assert.equal(captured.options.headers.Authorization, 'Bearer short-lived-vercel-token');
  assert.deepEqual(Object.keys(captured.body).sort(), [
    'digest',
    'kind',
    'media_base64',
    'mime',
    'scope',
  ]);
  assert.equal(JSON.stringify(captured).includes('http://'), false);
  assert.equal(result.provider, 'gemini');
  assert.equal(result.provider_status, 'completed');
  assert.equal(result.verdict_label_en, 'No clear manipulation indicators detected');
  assert.equal(result.bytes_analyzed, input.buffer.length);
});

test('completed directional responses fail closed unless evidence contract is complete', async (t) => {
  const input = media();
  const base = {
    verdict: 'likely_real',
    confidence: 0.82,
    deepfake_risk_code: 'low',
    signals_for: ['Direct pixel consistency signal.'],
    signals_against: [],
    limitations: [],
    provider_status: 'completed',
    analysis_scope: input.analysis_scope,
    bytes_analyzed: input.buffer.length,
  };
  for (const [name, override] of [
    ['missing confidence', { confidence: null }],
    ['low confidence', { confidence: 0.4 }],
    ['string confidence', { confidence: '0.95' }],
    ['wrong scope', { analysis_scope: 'thumbnail_only' }],
    ['missing byte evidence', { bytes_analyzed: 0 }],
    ['partial byte evidence', { bytes_analyzed: 1 }],
    ['string byte evidence', { bytes_analyzed: String(input.buffer.length) }],
    ['missing support', { signals_for: [] }],
  ]) {
    await t.test(name, async () => {
      const result = await analyzeWithWorker(input, 'token', {
        loadWorkerManifest: async () => MANIFEST,
        workerFetch: async () => new Response(JSON.stringify({ ...base, ...override })),
      });
      assert.equal(result.verdict, 'insufficient');
      assert.equal(result.confidence, null);
      assert.equal(result.deepfake_risk_code, 'unknown');
    });
  }
});

test('deployment manifest waits for the exact serving worker revision', () => {
  const workflow = fs.readFileSync('.github/workflows/deploy-media-worker.yml', 'utf8');
  assert.match(workflow, /health\.get\("worker_version"\) == os\.environ\["WORKER_VERSION"\]/);
  assert.match(workflow, /"version": health\["worker_version"\]/);
});

test('worker revision mismatch is always insufficient', async () => {
  const input = media();
  const result = await analyzeWithWorker(input, 'token', {
    loadWorkerManifest: async () => MANIFEST,
    workerFetch: async () => new Response(JSON.stringify({
      verdict: 'likely_real',
      confidence: 0.95,
      deepfake_risk_code: 'low',
      signals_for: ['Direct media consistency.'],
      signals_against: [],
      limitations: [],
      provider_status: 'completed',
      analysis_scope: input.analysis_scope,
      bytes_analyzed: input.buffer.length,
      worker_version: 'stale-revision',
    })),
  });
  assert.equal(result.verdict, 'insufficient');
  assert.equal(result.provider_status, 'worker_version_mismatch');
});

test('worker call fails closed without OIDC, manifest, or a valid response', async (t) => {
  await t.test('missing OIDC', async () => {
    let called = false;
    const result = await analyzeWithWorker(media(), '', {
      loadWorkerManifest: async () => {
        called = true;
        return MANIFEST;
      },
    });
    assert.equal(called, false);
    assert.equal(result.provider_status, 'skipped_oidc_unavailable');
    assert.equal(result.verdict, 'insufficient');
  });

  await t.test('manifest unavailable', async () => {
    const result = await analyzeWithWorker(media(), 'token', {
      loadWorkerManifest: async () => null,
    });
    assert.equal(result.provider_status, 'worker_unavailable');
  });

  await t.test('worker rejection', async () => {
    const result = await analyzeWithWorker(media(), 'token', {
      loadWorkerManifest: async () => MANIFEST,
      workerFetch: async () => new Response('{}', { status: 401 }),
    });
    assert.equal(result.provider_status, 'worker_oidc_rejected');
    assert.equal(result.bytes_analyzed, 0);
  });
});

test('worker call rejects incomplete, oversized, and unsupported media before network use', async (t) => {
  for (const fixture of [
    {
      name: 'truncated',
      value: media({ truncated: true }),
      status: 'skipped_incomplete_media',
    },
    {
      name: 'oversized',
      value: media({ buffer: Buffer.alloc(MAX_MEDIA_BYTES + 1) }),
      status: 'skipped_media_too_large',
    },
    {
      name: 'unsupported',
      value: media({ mime: 'image/webp' }),
      status: 'unsupported_media_format',
    },
    {
      name: 'kind and MIME mismatch',
      value: media({ kind: 'video', mime: 'image/jpeg' }),
      status: 'unsupported_media_format',
    },
  ]) {
    await t.test(fixture.name, async () => {
      let called = false;
      const result = await analyzeWithWorker(fixture.value, 'token', {
        loadWorkerManifest: async () => MANIFEST,
        workerFetch: async () => {
          called = true;
          throw new Error('must not call');
        },
      });
      assert.equal(called, false);
      assert.equal(result.provider_status, fixture.status);
      assert.equal(result.verdict, 'insufficient');
    });
  }
});
