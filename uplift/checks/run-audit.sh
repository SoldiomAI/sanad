#!/usr/bin/env bash
# Reproduce the baseline measurement. Requires playwright + chromium.
set -euo pipefail
export NPM_CONFIG_PREFIX=/tmp/npm-global
export PATH="/tmp/npm-global/bin:$PATH"
command -v node >/dev/null || { echo "node required"; exit 1; }
[ -d /tmp/npm-global/lib/node_modules/playwright ] || {
  npm i -g playwright && npx playwright install chromium --with-deps; }
echo "── perf ──";   node "$(dirname "$0")/audit-perf.js"
echo "── detail ──"; node "$(dirname "$0")/audit-detail.js"
echo "── headers ──"
curl -sI https://isnad.news | grep -iE 'cache-control|x-vercel-id|content-security|x-content-type|referrer-policy|permissions-policy' || true
