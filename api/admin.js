'use strict';

/**
 * SANAD · لوحة التشغيل — /api/admin
 * Control plane for isnad.news (Vercel Node).
 */

const crypto = require('crypto');

const RAW_BASE = 'https://raw.githubusercontent.com/Soldiom/sanad-data/main/daily';
const GH_API = 'https://api.github.com';

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

const WORKFLOWS = {
  'news-refresh': 'news-refresh.yml',
  'daily-anchor': 'daily-anchor.yml',
};

function dataRepo() {
  return (
    process.env.GITHUB_REPO_DATA ||
    process.env.SANAD_DATA_REPO ||
    'Soldiom/sanad-data'
  );
}

function codeRepo() {
  return process.env.GITHUB_REPO_CODE || process.env.SANAD_CODE_REPO || 'Soldiom/sanad';
}

function ghToken() {
  return process.env.SANAD_DATA_TOKEN || process.env.GITHUB_TOKEN || '';
}

function adminPassword() {
  return process.env.ADMIN_PASSWORD || '';
}

function makeToken() {
  const pwd = adminPassword();
  if (!pwd) return '';
  const secret = process.env.ADMIN_SECRET || pwd;
  return crypto.createHash('sha256').update(pwd + '|' + secret).digest('hex');
}

function timingSafeEqualStr(a, b) {
  const ba = Buffer.from(String(a || ''), 'utf8');
  const bb = Buffer.from(String(b || ''), 'utf8');
  if (ba.length !== bb.length) return false;
  return crypto.timingSafeEqual(ba, bb);
}

function getBearer(req) {
  const h = String(req.headers.authorization || '');
  const m = h.match(/^Bearer\s+(.+)$/i);
  if (m) return m[1].trim();
  // optional cookie fallback
  const cookie = String(req.headers.cookie || '');
  const cm = cookie.match(/(?:^|;\s*)sanad_admin=([^;]+)/);
  if (cm) {
    try {
      return decodeURIComponent(cm[1].trim());
    } catch (_) {
      return cm[1].trim();
    }
  }
  return '';
}

function isAuthed(req) {
  const expected = makeToken();
  if (!expected) return false;
  const got = getBearer(req);
  return got && timingSafeEqualStr(got, expected);
}

function json(res, status, body) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.end(JSON.stringify(body));
}

function setCors(req, res) {
  const origin = String(req.headers.origin || '');
  const host = String(req.headers.host || '');
  if (origin && host) {
    try {
      const o = new URL(origin);
      if (o.host === host) {
        res.setHeader('Access-Control-Allow-Origin', origin);
        res.setHeader('Vary', 'Origin');
        res.setHeader('Access-Control-Allow-Credentials', 'true');
      }
    } catch (_) {
      /* ignore */
    }
  }
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
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

function queryAction(req) {
  const q = req.query || {};
  if (q.action) return String(q.action);
  if (req.url) {
    try {
      return new URL(req.url, 'http://local').searchParams.get('action') || '';
    } catch (_) {
      return '';
    }
  }
  return '';
}

async function fetchJson(url, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, {
      signal: ctrl.signal,
      headers: {
        Accept: 'application/json',
        'User-Agent': 'SANAD-Admin/1.0',
      },
    });
    if (!r.ok) return null;
    return await r.json();
  } catch (_) {
    return null;
  } finally {
    clearTimeout(t);
  }
}

function ensureControlMemory(data, sticky) {
  globalThis.__SANAD_CONTROL__ = {
    data: { ...DEFAULT_CONTROL, ...(data || {}) },
    sticky: !!sticky,
    updated: new Date().toISOString(),
  };
  return globalThis.__SANAD_CONTROL__;
}

async function loadControl() {
  const mem = globalThis.__SANAD_CONTROL__;
  if (mem && mem.data && mem.sticky) {
    return {
      control: { ...DEFAULT_CONTROL, ...mem.data },
      sticky: true,
      source: 'memory',
      warning: null,
    };
  }

  const token = ghToken();
  const repo = dataRepo();
  if (token) {
    try {
      const r = await fetch(
        `${GH_API}/repos/${repo}/contents/daily/control.json`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'application/vnd.github+json',
            'User-Agent': 'SANAD-Admin/1.0',
            'X-GitHub-Api-Version': '2022-11-28',
          },
        }
      );
      if (r.ok) {
        const meta = await r.json();
        const raw = Buffer.from(meta.content || '', 'base64').toString('utf8');
        const parsed = JSON.parse(raw);
        ensureControlMemory(parsed, true);
        return {
          control: { ...DEFAULT_CONTROL, ...parsed },
          sticky: true,
          source: 'github',
          sha: meta.sha,
          warning: null,
        };
      }
    } catch (_) {
      /* fall through */
    }
  }

  const remote = await fetchJson(`${RAW_BASE}/control.json`);
  if (remote && typeof remote === 'object') {
    ensureControlMemory(remote, false);
    return {
      control: { ...DEFAULT_CONTROL, ...remote },
      sticky: false,
      source: 'raw',
      warning: token
        ? 'تعذّر القراءة عبر GitHub API — استُخدم الملف العام.'
        : null,
    };
  }

  if (mem && mem.data) {
    return {
      control: { ...DEFAULT_CONTROL, ...mem.data },
      sticky: !!mem.sticky,
      source: 'memory',
      warning: 'لا مثابرة على GitHub — الحالة في الذاكرة فقط.',
    };
  }

  ensureControlMemory(DEFAULT_CONTROL, false);
  return {
    control: { ...DEFAULT_CONTROL },
    sticky: false,
    source: 'default',
    warning: 'لا مثابرة على GitHub — تُحفظ التغييرات في الذاكرة فقط (sticky:false).',
  };
}

async function saveControl(next) {
  const merged = { ...DEFAULT_CONTROL, ...next };
  // normalize arrays
  if (!Array.isArray(merged.paused_agents)) merged.paused_agents = [];
  if (!Array.isArray(merged.desks_enabled)) merged.desks_enabled = [];

  const token = ghToken();
  const repo = dataRepo();

  if (token) {
    try {
      // get current sha if exists
      let sha;
      const getR = await fetch(`${GH_API}/repos/${repo}/contents/daily/control.json`, {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github+json',
          'User-Agent': 'SANAD-Admin/1.0',
          'X-GitHub-Api-Version': '2022-11-28',
        },
      });
      if (getR.ok) {
        const meta = await getR.json();
        sha = meta.sha;
      }

      const body = {
        message: `chore(control): تحديث لوحة التشغيل ${new Date().toISOString()}`,
        content: Buffer.from(JSON.stringify(merged, null, 2) + '\n', 'utf8').toString(
          'base64'
        ),
        branch: process.env.SANAD_DATA_BRANCH || 'main',
      };
      if (sha) body.sha = sha;

      const putR = await fetch(`${GH_API}/repos/${repo}/contents/daily/control.json`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github+json',
          'Content-Type': 'application/json',
          'User-Agent': 'SANAD-Admin/1.0',
          'X-GitHub-Api-Version': '2022-11-28',
        },
        body: JSON.stringify(body),
      });

      if (putR.ok) {
        ensureControlMemory(merged, true);
        const putData = await putR.json().catch(() => ({}));
        return {
          ok: true,
          sticky: true,
          source: 'github',
          control: merged,
          commit: putData?.commit?.sha || null,
          warning: null,
        };
      }

      const errText = await putR.text().catch(() => '');
      ensureControlMemory(merged, false);
      return {
        ok: true,
        sticky: false,
        source: 'memory',
        control: merged,
        warning: `فشل الحفظ على GitHub (${putR.status}) — حُفظ في الذاكرة فقط. ${errText.slice(0, 180)}`,
      };
    } catch (e) {
      ensureControlMemory(merged, false);
      return {
        ok: true,
        sticky: false,
        source: 'memory',
        control: merged,
        warning: `خطأ GitHub — حُفظ في الذاكرة فقط: ${e?.message || e}`,
      };
    }
  }

  ensureControlMemory(merged, false);
  return {
    ok: true,
    sticky: false,
    source: 'memory',
    control: merged,
    warning: 'لا رمز GitHub (SANAD_DATA_TOKEN/GITHUB_TOKEN) — sticky:false، الحالة في الذاكرة فقط.',
  };
}

function verifyStats() {
  const v = globalThis.__SANAD_VERIFY__;
  if (!v) {
    return {
      spend: { day: new Date().toISOString().slice(0, 10), usd: 0, calls: 0 },
      activity: [],
      cache_size: 0,
    };
  }
  return {
    spend: { ...(v.spend || { day: '', usd: 0, calls: 0 }) },
    activity: Array.isArray(v.activity) ? v.activity.slice(-40) : [],
    cache_size: v.cache?.size ?? 0,
  };
}

async function buildStatus() {
  const sectionKeys = [
    'news',
    'verify',
    'council',
    'evolution',
    'agents',
    'forecast',
    'analyst',
    'alerts',
    'official',
    'rumors',
    'column',
    'latest',
    'dua',
    'cost',
  ];
  const [agents, cost, news, rumors, controlPack, ...sectionDocs] =
    await Promise.all([
      fetchJson(`${RAW_BASE}/agents.json`),
      fetchJson(`${RAW_BASE}/cost.json`),
      fetchJson(`${RAW_BASE}/news.json`),
      fetchJson(`${RAW_BASE}/rumors.json`),
      loadControl(),
      ...sectionKeys.map((k) => fetchJson(`${RAW_BASE}/${k}.json`)),
    ]);

  const sections = {};
  sectionKeys.forEach((k, i) => {
    const d = sectionDocs[i];
    if (!d) {
      sections[k] = null;
      return;
    }
    sections[k] =
      d.updated || d.built || (d.date ? String(d.date) + 'T00:00:00Z' : null);
  });

  const verifyRaw = verifyStats();
  const verify = {
    ...verifyRaw,
    day: verifyRaw.spend?.day || '',
    usd: verifyRaw.spend?.usd || 0,
    calls: verifyRaw.spend?.calls || 0,
    activity: verifyRaw.activity || [],
  };

  return {
    ok: true,
    updated: new Date().toISOString(),
    built: agents?.updated || news?.updated || null,
    agents: agents || null,
    cost: cost || null,
    rumors: rumors || null,
    sections,
    news: news
      ? {
          updated: news.updated || null,
          cats: news.cats ? Object.keys(news.cats) : [],
          count: news.cats
            ? Object.values(news.cats).reduce(
                (n, arr) => n + (Array.isArray(arr) ? arr.length : 0),
                0
              )
            : 0,
        }
      : null,
    verify,
    control: controlPack.control,
    control_meta: {
      sticky: controlPack.sticky,
      source: controlPack.source,
      warning: controlPack.warning,
    },
    env: {
      grok_key: !!process.env.GROK_API_KEY,
      admin_password: !!adminPassword(),
      github_token: !!ghToken(),
      data_repo: dataRepo(),
      code_repo: codeRepo(),
    },
  };
}

async function triggerWorkflow(workflowKey) {
  const file = WORKFLOWS[workflowKey];
  if (!file) {
    return { ok: false, status: 400, error: 'سير العمل غير معروف' };
  }
  const token = ghToken();
  if (!token) {
    return {
      ok: false,
      status: 500,
      error: 'لا رمز GitHub لتشغيل Actions',
    };
  }
  const repo = codeRepo();
  const r = await fetch(
    `${GH_API}/repos/${repo}/actions/workflows/${file}/dispatches`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'Content-Type': 'application/json',
        'User-Agent': 'SANAD-Admin/1.0',
        'X-GitHub-Api-Version': '2022-11-28',
      },
      body: JSON.stringify({
        ref: process.env.SANAD_CODE_BRANCH || 'main',
      }),
    }
  );
  if (r.status === 204 || r.ok) {
    return { ok: true, workflow: workflowKey, repo };
  }
  const text = await r.text().catch(() => '');
  return {
    ok: false,
    status: r.status >= 400 ? r.status : 500,
    error: `فشل تشغيل السير: ${r.status} ${text.slice(0, 200)}`,
  };
}

async function handleAction(action, body, req) {
  switch (action) {
    case 'login': {
      const pwd = adminPassword();
      if (!pwd) {
        return {
          status: 500,
          body: { error: 'ADMIN_PASSWORD غير مضبوط على الخادم' },
        };
      }
      if (!body?.password || !timingSafeEqualStr(body.password, pwd)) {
        return { status: 401, body: { error: 'كلمة المرور غير صحيحة' } };
      }
      const token = makeToken();
      return {
        status: 200,
        body: {
          ok: true,
          token,
          // cookie hint for clients that prefer cookies
          cookie: `sanad_admin=${token}; Path=/; SameSite=Strict; Secure`,
        },
      };
    }

    case 'logout': {
      // Client drops token; nothing server-side to clear for bearer tokens
      return { status: 200, body: { ok: true } };
    }

    case 'status': {
      if (!isAuthed(req)) {
        return { status: 401, body: { error: 'غير مصرّح' } };
      }
      const status = await buildStatus();
      return { status: 200, body: status };
    }

    case 'config': {
      if (!isAuthed(req)) {
        return { status: 401, body: { error: 'غير مصرّح' } };
      }
      const pack = await loadControl();
      return {
        status: 200,
        body: {
          ok: true,
          control: pack.control,
          sticky: pack.sticky,
          source: pack.source,
          warning: pack.warning,
        },
      };
    }

    case 'save_config': {
      if (!isAuthed(req)) {
        return { status: 401, body: { error: 'غير مصرّح' } };
      }
      const incoming = body?.config;
      if (!incoming || typeof incoming !== 'object' || Array.isArray(incoming)) {
        return { status: 400, body: { error: 'الحقل config مطلوب' } };
      }
      const pack = await loadControl();
      const merged = { ...pack.control, ...incoming };
      // never allow unknown wipe of required keys — re-apply defaults underneath
      const saved = await saveControl(merged);
      return {
        status: 200,
        body: {
          ok: true,
          control: saved.control,
          sticky: saved.sticky,
          source: saved.source,
          warning: saved.warning,
          commit: saved.commit || null,
        },
      };
    }

    case 'pause_agent': {
      if (!isAuthed(req)) {
        return { status: 401, body: { error: 'غير مصرّح' } };
      }
      const id = String(body?.id || '').trim();
      if (!id) return { status: 400, body: { error: 'معرّف الوكيل مطلوب' } };
      const pack = await loadControl();
      const paused = new Set(pack.control.paused_agents || []);
      paused.add(id);
      const saved = await saveControl({
        ...pack.control,
        paused_agents: [...paused],
      });
      return {
        status: 200,
        body: {
          ok: true,
          paused_agents: saved.control.paused_agents,
          sticky: saved.sticky,
          warning: saved.warning,
        },
      };
    }

    case 'resume_agent': {
      if (!isAuthed(req)) {
        return { status: 401, body: { error: 'غير مصرّح' } };
      }
      const id = String(body?.id || '').trim();
      if (!id) return { status: 400, body: { error: 'معرّف الوكيل مطلوب' } };
      const pack = await loadControl();
      const paused = (pack.control.paused_agents || []).filter((x) => x !== id);
      const saved = await saveControl({ ...pack.control, paused_agents: paused });
      return {
        status: 200,
        body: {
          ok: true,
          paused_agents: saved.control.paused_agents,
          sticky: saved.sticky,
          warning: saved.warning,
        },
      };
    }

    case 'clear_verify_cache': {
      if (!isAuthed(req)) {
        return { status: 401, body: { error: 'غير مصرّح' } };
      }
      const v = globalThis.__SANAD_VERIFY__;
      if (v && typeof v.clearCache === 'function') {
        v.clearCache();
      } else if (v && v.cache && typeof v.cache.clear === 'function') {
        v.cache.clear();
      } else {
        return {
          status: 200,
          body: {
            ok: true,
            cleared: false,
            warning: 'ذاكرة التحقق غير متاحة في هذه العملية (cold start منفصل).',
          },
        };
      }
      return {
        status: 200,
        body: { ok: true, cleared: true, cache_size: v.cache?.size ?? 0 },
      };
    }

    case 'trigger': {
      if (!isAuthed(req)) {
        return { status: 401, body: { error: 'غير مصرّح' } };
      }
      const workflow = String(body?.workflow || '').trim();
      const result = await triggerWorkflow(workflow);
      if (!result.ok) {
        return {
          status: result.status || 500,
          body: { error: result.error || 'فشل التشغيل' },
        };
      }
      return { status: 200, body: { ok: true, ...result } };
    }

    default:
      return { status: 400, body: { error: `إجراء غير معروف: ${action || '—'}` } };
  }
}

module.exports = async function handler(req, res) {
  setCors(req, res);
  const method = String(req.method || 'GET').toUpperCase();

  if (method === 'OPTIONS') {
    res.statusCode = 204;
    return res.end();
  }

  if (method === 'GET') {
    const action = queryAction(req) || 'status';
    if (action === 'login') {
      return json(res, 400, { error: 'استخدم POST لتسجيل الدخول' });
    }
    // GET actions still need auth except we don't allow login via GET
    const result = await handleAction(action, {}, req);
    return json(res, result.status, result.body);
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

  const action = String(body?.action || queryAction(req) || '').trim();
  if (!action) {
    return json(res, 400, { error: 'الحقل action مطلوب' });
  }

  try {
    const result = await handleAction(action, body, req);
    return json(res, result.status, result.body);
  } catch (e) {
    return json(res, 500, {
      error: 'خطأ داخلي في لوحة التشغيل',
      detail: String(e?.message || e).slice(0, 200),
    });
  }
};
