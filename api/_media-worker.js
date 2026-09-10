'use strict';

const crypto = require('crypto');

const DEFAULT_MANIFEST_URL =
  'https://raw.githubusercontent.com/SoldiomAI/sanad-data/main/daily/media-worker.json';
const MAX_MEDIA_BYTES = 6 * 1024 * 1024;
const MANIFEST_TTL_MS = 5 * 60 * 1000;
const WORKER_TIMEOUT_MS = 55 * 1000;
const ALLOWED_MIMES = new Set([
  'image/jpeg',
  'image/png',
  'video/mp4',
  'video/webm',
  'audio/mpeg',
  'audio/wav',
  'audio/x-wav',
  'audio/ogg',
  'audio/mp4',
]);
const MIMES_BY_KIND = Object.freeze({
  image: new Set(['image/jpeg', 'image/png']),
  video: new Set(['video/mp4', 'video/webm']),
  audio: new Set(['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/ogg', 'audio/mp4']),
});

let manifestCache = null;

function insufficient(media, status, limitation) {
  return {
    verdict: 'insufficient',
    verdict_label_ar: 'أدلة غير كافية',
    verdict_label_en: 'Insufficient evidence',
    confidence: null,
    deepfake_risk: 'unknown',
    deepfake_risk_code: 'unknown',
    signals_for: [],
    signals_against: [],
    limitations: [limitation],
    provider: 'gemini',
    provider_status: status,
    checked_at: new Date().toISOString(),
    analysis_scope: media?.analysis_scope || 'none',
    bytes_analyzed: 0,
    model_version: '',
    worker_version: '',
  };
}

function validWorkerEndpoint(value) {
  try {
    const url = new URL(String(value || ''));
    return (
      url.protocol === 'https:' &&
      url.hostname.endsWith('.hf.space') &&
      url.pathname === '/analyze' &&
      !url.username &&
      !url.password &&
      !url.search &&
      !url.hash
    );
  } catch (_) {
    return false;
  }
}

function normalizeManifest(value) {
  if (!value || typeof value !== 'object' || value.ready !== true) return null;
  if (!validWorkerEndpoint(value.endpoint)) return null;
  if (!Array.isArray(value.capabilities)) return null;
  const capabilities = value.capabilities.filter((item) =>
    ['image', 'video', 'audio'].includes(item)
  );
  if (!capabilities.length) return null;
  return {
    endpoint: value.endpoint,
    capabilities,
    deployed_at: String(value.deployed_at || '').slice(0, 64),
    version: String(value.version || '').slice(0, 128),
  };
}

async function loadWorkerManifest(deps = {}, options = {}) {
  const now = Date.now();
  if (manifestCache && now - manifestCache.at < MANIFEST_TTL_MS) {
    return manifestCache.value;
  }
  const fetchImpl = deps.manifestFetch || globalThis.fetch;
  if (typeof fetchImpl !== 'function') return null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs || 5000);
  try {
    const response = await fetchImpl(options.manifestUrl || DEFAULT_MANIFEST_URL, {
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        'User-Agent': 'SANAD-Media-Worker-Client/1.0',
      },
    });
    if (!response.ok) return null;
    const manifest = normalizeManifest(await response.json());
    if (!manifest) return null;
    manifestCache = { at: now, value: manifest };
    return manifest;
  } catch (_) {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

function cleanStrings(value) {
  return (Array.isArray(value) ? value : [])
    .filter((item) => typeof item === 'string' && item.trim())
    .map((item) => item.trim().slice(0, 300))
    .slice(0, 8);
}

function normalizeWorkerEvidence(value, media, expectedVersion = '') {
  if (!value || typeof value !== 'object') return null;
  const verdict = ['likely_real', 'likely_manipulated', 'insufficient'].includes(value.verdict)
    ? value.verdict
    : 'insufficient';
  const risk = ['low', 'moderate', 'high', 'unknown'].includes(value.deepfake_risk_code)
    ? value.deepfake_risk_code
    : 'unknown';
  const providerStatus = String(value.provider_status || '').slice(0, 80);
  if (!providerStatus) return null;
  const workerVersion = String(value.worker_version || '').slice(0, 128);
  const versionValid = !!expectedVersion && workerVersion === expectedVersion;
  const completed = providerStatus === 'completed' && versionValid;
  const numericConfidence = value.confidence;
  const confidenceValid =
    Number.isFinite(numericConfidence) && numericConfidence >= 0.75 && numericConfidence <= 1;
  const bytesAnalyzed = value.bytes_analyzed;
  const bytesValid =
    Number.isInteger(bytesAnalyzed) &&
    bytesAnalyzed === media.buffer.length;
  const scopeValid = value.analysis_scope === media.analysis_scope;
  const signalsFor = cleanStrings(value.signals_for);
  const signalsAgainst = cleanStrings(value.signals_against);
  const directionalEvidenceValid = verdict === 'likely_real'
    ? signalsFor.length > 0
    : verdict === 'likely_manipulated'
      ? signalsAgainst.length > 0
      : true;
  const conclusive =
    completed &&
    verdict !== 'insufficient' &&
    confidenceValid &&
    bytesValid &&
    scopeValid &&
    directionalEvidenceValid;
  const normalizedVerdict = conclusive ? verdict : 'insufficient';
  const confidence = conclusive ? numericConfidence : null;
  return {
    verdict: normalizedVerdict,
    verdict_label_ar: normalizedVerdict === 'likely_manipulated'
      ? 'يبدو مُعالَجًا أو مُتلاعَبًا به'
      : normalizedVerdict === 'likely_real'
        ? 'لم تُرصد مؤشرات تلاعب واضحة'
        : 'أدلة غير كافية',
    verdict_label_en: normalizedVerdict === 'likely_manipulated'
      ? 'Likely manipulated'
      : normalizedVerdict === 'likely_real'
        ? 'No clear manipulation indicators detected'
        : 'Insufficient evidence',
    confidence,
    deepfake_risk: conclusive ? risk : 'unknown',
    deepfake_risk_code: conclusive ? risk : 'unknown',
    signals_for: signalsFor,
    signals_against: signalsAgainst,
    limitations: cleanStrings(value.limitations),
    provider: 'gemini',
    provider_status: providerStatus === 'completed' && !versionValid
      ? 'worker_version_mismatch'
      : completed
        ? 'completed'
        : providerStatus,
    checked_at: String(value.checked_at || new Date().toISOString()).slice(0, 64),
    analysis_scope: String(value.analysis_scope || media.analysis_scope || 'none').slice(0, 120),
    bytes_analyzed: completed && bytesValid ? bytesAnalyzed : 0,
    model_version: String(value.model_version || '').slice(0, 128),
    worker_version: workerVersion,
    sampling: value.sampling && typeof value.sampling === 'object' ? value.sampling : undefined,
    usd: 0,
  };
}

async function analyzeWithWorker(media, oidcToken, deps = {}, options = {}) {
  if (!media?.buffer || media.truncated) {
    return insufficient(
      media,
      'skipped_incomplete_media',
      'Complete media bytes were not available for worker analysis.'
    );
  }
  if (!ALLOWED_MIMES.has(media.mime) || !MIMES_BY_KIND[media.kind]?.has(media.mime)) {
    return insufficient(
      media,
      'unsupported_media_format',
      'The media format is not supported by the configured worker.'
    );
  }
  if (media.buffer.length > MAX_MEDIA_BYTES) {
    return insufficient(
      media,
      'skipped_media_too_large',
      'The media exceeds the six MiB worker forwarding limit.'
    );
  }
  if (!oidcToken || typeof oidcToken !== 'string') {
    return insufficient(
      media,
      'skipped_oidc_unavailable',
      'The production Vercel OIDC token was unavailable, so authenticated worker analysis was not attempted.'
    );
  }
  const manifest = await (deps.loadWorkerManifest || loadWorkerManifest)(deps, options);
  if (!manifest || !manifest.capabilities.includes(media.kind)) {
    return insufficient(
      media,
      'worker_unavailable',
      'The authenticated media worker is unavailable or does not advertise this media capability.'
    );
  }
  const fetchImpl = deps.workerFetch || globalThis.fetch;
  if (typeof fetchImpl !== 'function') {
    return insufficient(media, 'worker_unavailable', 'The authenticated media worker is unavailable.');
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs || WORKER_TIMEOUT_MS);
  try {
    const response = await fetchImpl(manifest.endpoint, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${oidcToken}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        media_base64: media.buffer.toString('base64'),
        digest: media.content_digest ||
          crypto.createHash('sha256').update(media.buffer).digest('hex'),
        mime: media.mime,
        kind: media.kind,
        scope: media.analysis_scope,
      }),
    });
    if (!response.ok) {
      const status = response.status === 401 || response.status === 403
        ? 'worker_oidc_rejected'
        : `worker_http_${response.status}`;
      return insufficient(
        media,
        status,
        'The authenticated media worker did not complete the analysis.'
      );
    }
    const evidence = normalizeWorkerEvidence(await response.json(), media, manifest.version);
    return evidence || insufficient(
      media,
      'worker_invalid_response',
      'The media worker returned an invalid evidence contract.'
    );
  } catch (error) {
    return insufficient(
      media,
      error?.name === 'AbortError' ? 'worker_timeout' : 'worker_failed',
      error?.name === 'AbortError'
        ? 'The authenticated media worker timed out.'
        : 'The authenticated media worker failed before returning evidence.'
    );
  } finally {
    clearTimeout(timer);
  }
}

function clearManifestCache() {
  manifestCache = null;
}

module.exports = {
  ALLOWED_MIMES,
  DEFAULT_MANIFEST_URL,
  MAX_MEDIA_BYTES,
  analyzeWithWorker,
  clearManifestCache,
  loadWorkerManifest,
  normalizeManifest,
  normalizeWorkerEvidence,
  validWorkerEndpoint,
};
