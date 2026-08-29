# SANAD Enterprise API v1

`/api/v1` is a read-only customer API over SANAD's published `events.json` and
allowlisted `ontime-signals.json`. It does not expose prompts, editorial rules,
control state, credentials, or unpublished records.

## Routes

| Route | Required scope | Filters |
| --- | --- | --- |
| `GET /api/v1/events` | `read:events` | `country`, `topic`, `sector`, `type`, `severity`, `q`, `limit`, `page` |
| `GET /api/v1/signals` | `read:signals` | same |
| `GET /api/v1/countries` | `read:metadata` | `q`, `limit`, `page` |
| `GET /api/v1/topics` | `read:metadata` | `q`, `limit`, `page` |
| `GET /api/v1/briefings` | `read:briefings` | same; `sector` produces a sector briefing |

`limit` is 1–100 and `page` is 1–1000. All data responses identify the API and
source schema versions and label observed facts, SANAD assessments, inference,
uncertainty, and evidence separately.

## Required external authentication deployment

This repository does **not** contain the source or schema for the existing
Supabase Edge Function behind `sanad-enterprise-api`. Vercel therefore does not
receive a Supabase service-role key and does not query `sanad_api_keys` directly.
The API fails closed with `503 enterprise_backend_disabled` until all three
Vercel variables are configured:

```text
SANAD_ENTERPRISE_API_ENABLED=true
SANAD_ENTERPRISE_AUTH_URL=https://<trusted-supabase-edge-function>
SANAD_ENTERPRISE_AUTH_TOKEN=<separate adapter-to-edge shared secret>
```

The HTTPS authority must accept `verify_api_key_and_record_usage`. In one
server-side operation it must:

1. derive the supplied key prefix, select the candidate in `sanad_api_keys`,
   hash the complete key with SHA-256, and compare fixed-length hashes in
   constant time;
2. reject missing or revoked keys, bind the key to its `org_id`, and return only
   its ID, prefix, and explicit scopes (use `read:*` only for a reviewed legacy
   read-only key);
3. atomically enforce a persistent per-key rate limit, update `last_used`, and
   insert an `api_request` row in `sanad_audit_log`;
4. never log or store the raw credential and never return the stored hash.

Required success response:

```json
{
  "valid": true,
  "revoked": false,
  "key_prefix": "sk_1234567",
  "org_id": "uuid",
  "key_id": "uuid",
  "scopes": ["read:events", "read:signals", "read:metadata", "read:briefings"],
  "audit_recorded": true,
  "rate_limit": {
    "allowed": true,
    "limit": 1000,
    "remaining": 999,
    "reset_at": "2026-08-30T03:00:00Z"
  }
}
```

An absent audit result or persistent rate-limit result is a `503`, not a
successful data response. Invalid and revoked keys are `401`; insufficient
scope is `403`; exhausted limits are `429`.

The same authority must accept `{ "action": "status", "api_version": "v1" }`
using the adapter secret and return `{ "available": true }` only when key
verification, persistent rate limiting, and `sanad_audit_log` writes are
operational. The invite-only portal hides the API capability unless this
readiness check succeeds.

## Deterministic briefing

Briefings make no model call. They select published signals in a stable order
and emit six explicit sections: `OBSERVED_FACT`, `SANAD_ASSESSMENT`,
`INFERENCE`, `UNCERTAINTY`, `EVIDENCE`, and `WHAT_TO_WATCH`.

## Webhook contract (disabled)

`SANAD_ENTERPRISE_WEBHOOKS_ENABLED` defaults to false. `/api/v1/webhooks`
returns `503 webhooks_disabled`; this release does not register or deliver any
webhook.

Before enabling a later implementation, the backend must persist subscriptions
and delivery attempts, allow only `signal.created`, `signal.updated`,
`event.created`, and `event.updated`, sign
`<timestamp>.<idempotency-key>.<raw-body>` with HMAC-SHA256, reject secrets
shorter than 32 random bytes, include timestamp and idempotency headers, retry
boundedly with backoff, and retain an auditable delivery log. No external send
is implemented in this increment.
