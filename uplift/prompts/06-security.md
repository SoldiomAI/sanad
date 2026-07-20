# Task 6 — Security

Response headers today carry HSTS and nothing else.

## Add

```
Content-Security-Policy       report-only first, then enforce
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

Ship CSP in report-only until the report stream is clean. An enforced CSP that
breaks the audio player during a conflict is worse than no CSP.

## Audit

- No key, token, or prompt in `sanad-data`, in any client bundle, or in any
  committed file. Scan history, not just `HEAD`.
- Every secret from environment variables.
- **Rotate anything that has ever appeared in plaintext — including in a chat
  log.** This has happened more than once. A token in a transcript is a live
  token until it is revoked.
- Fine-grained tokens: single repo, `Contents: Read and write`, 7-day expiry.
- Prefer `secrets.GITHUB_TOKEN` inside Actions so no token passes through a
  human hand at all.

## Definition of done

- All four headers present on every response
- CSP enforced, report stream clean for 48 hours first
- Secret scan over full git history, both repos, clean
- No classic PATs remain on the account
