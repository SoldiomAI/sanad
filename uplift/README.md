# SANAD uplift — Claude Code work package

One shared context, seven isolated tasks, and checks that actually run.

## Use

```bash
git clone <sanad private repo> && cd sanad
export GITHUB_TOKEN=...        # fine-grained, single repo, 7-day expiry
node checks/audit-perf.js      # record the before-numbers yourself
```

Then in Claude Code, one task at a time:

```
Read prompts/00-context.md and prompts/01-speed.md. Do only that task.
Re-run checks/audit-perf.js and show before/after for the rows it owns.
```

**Never load more than one task file at a time.** Each is scoped so it can be
finished, measured, and committed on its own. Loading two at once produces a
branch that does both halfway.

## Order — by reader impact, not by interest

| # | task | owns | why first |
|---|---|---|---|
| 1 | `01-speed.md` | TTFB, weight, fonts, audio | 2.5s of the 4.8s load |
| 2 | `02-discoverability.md` | JSON-LD, RSS, permalinks | ClaimReview is the strategic gap |
| 3 | `03-accessibility.md` | landmarks, live regions | alerts announce nothing today |
| 4 | `04-editorial.md` | terminology, attribution | the part that cannot be bought back |
| 5 | `06-security.md` | headers, secret audit | cheap, do it before it matters |
| 6 | `05-agents.md` | validation, idempotency | deepest change, least visible |
| 7 | `08-reliability.md` | retry, alerting, stale disclosure | one daily cron, no retry, no alert |
| 8 | `07-reel.md` | social distribution | only after the platform holds |

Tasks 1–3 are worth more than the rest combined, and task 8 is the one
that stops a silent failure living for 24 hours. Do not start at the bottom
because it is more interesting.

## Files

```
prompts/00-context.md      shared — load with every task
prompts/01..08             one task each, independently shippable
baseline.json              measured 2026-07-20, machine-readable
checks/audit-perf.js       the audit that produced baseline.json
checks/audit-detail.js     fonts, audio, landmarks, headings
checks/copy-guard.sh       CI gate for terminology and comparison language
checks/consistency.py      gate on the package itself — every task measurable
```

## Rules

A change you cannot measure is a change you cannot defend. Every task file
ends with a Definition of done that is a number or a command, never a feeling.

Every task owns at least one row of `baseline.json`, and
`checks/consistency.py` fails if that stops being true. A task nobody can
measure is a task nobody will finish.

Report misses by how much. Never state a range and let the good end stand for
the result.

```bash
python3 checks/consistency.py    # the package checks itself
bash checks/copy-guard.sh .      # the copy checks itself
```
