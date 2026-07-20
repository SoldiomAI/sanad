# The prompt — paste this into Claude Code

Run from a clone of `Soldiom/sanad`. Everything referenced below is in
`uplift/` in this repo.

---

You are raising **isnad.news** (سَنَد) to production grade.

It is an Arabic news platform that applies isnad methodology from hadith
science to modern news: every item is graded on a 7-point scale against five
criteria, and the chain of transmission is shown to the reader rather than
summarised for them. The reader is in Kuwait or the Gulf, on mobile, often on
a degraded network during an active conflict. Judge every decision against
that reader — not against a desktop on fibre.

## Repos

| repo | visibility | holds |
|---|---|---|
| `Soldiom/sanad` | **private** | all code, prompts, agent logic, workflows |
| `Soldiom/sanad-data` | public | JSON, media, the `screen-reel` skill |

The code was once publicly visible; the split fixed that. Nothing revealing
scoring logic or prompts crosses into the public repo — ever.

## Invariants

Not preferences. Breaking one is a bug no matter how good the rest of the
change is.

1. **Terminology.** Never `الأركان الخمسة`. Always
   `خمسة معايير من علم الحديث`. The five: الاتصال · عدالة المصدر · الضبط ·
   عدم الشذوذ · انتفاء العلة.
2. **No comparison.** Never position SANAD against other outlets. State the
   method; let the reader draw the conclusion. That judgement is only worth
   something coming from them.
3. **Attribution is per field, not per card.** An official badge belongs on
   the figure a ministry declared, never on a card carrying other figures too.
4. **Numbers never change silently.** Every changed figure goes to the
   corrections log with before, after, and both sources.
5. **Uncertainty is displayed as prominently as confidence.** A 2/7 is as
   legible as a 7/7. The moment weak items are quietly de-emphasised, the
   score stops being a measurement and becomes marketing.
6. **No secret in a repo, a bundle, or a chat.** Environment variables only.
   Fine-grained tokens, single repo, 7-day expiry.

## Where things stand — measured 2026-07-20, mobile, cold cache

| | now | target |
|---|---|---|
| TTFB | **2,566 ms** | < 400 |
| load | 4,844 ms | < 2,500 |
| page weight | **2,001 KB** | < 450 |
| fonts | **680 KB across 16 files** | < 90 KB, 2 files |
| audio before any click | **1,014 KB** | 0 |
| edge cache | `max-age=0` yet serving `age: 31,641` | `s-maxage` + SWR |
| serving region | **sfo1**, readers in Kuwait | nearest to Gulf |
| JSON-LD blocks | **0** | NewsArticle + ClaimReview + Organization |
| ARIA landmarks | main 0 · nav 0 · header 0 | complete |
| live regions | **0** | ticker + official alerts |
| daily bulletin | **a day stale**, shown as نشرة اليوم | same-day or disclosed |
| anchor workflow | 1 cron/day, no retry, no alert, hangs silently | retry + alert + timeout |
| console errors | 0 | keep at 0 |

Full machine-readable set: `uplift/baseline.json` — 41 metrics, each owned by
exactly one task.

## How to work

**One task per session.** Load `uplift/prompts/00-context.md` plus exactly one
task file. Loading two produces a branch that does both halfway.

```
Read uplift/prompts/00-context.md and uplift/prompts/01-speed.md.
Do only that task. Then re-run the checks and show before/after for the
rows that task owns.
```

Order, by reader impact:

| | task | why |
|---|---|---|
| 1 | `01-speed.md` | 2.5s of the 4.8s load, and the reader feels every one |
| 2 | `02-discoverability.md` | ClaimReview is how verification work is found at all |
| 3 | `03-accessibility.md` | official alerts currently announce nothing |
| 4 | `08-reliability.md` | a silent failure lives 24 hours today |
| 5 | `04-editorial.md` | turn invariants into CI gates, not memory |
| 6 | `06-security.md` | cheap; do it before it matters |
| 7 | `05-agents.md` | deepest change, least visible |
| 8 | `07-reel.md` | only after the platform holds |

Tasks 1–3 are worth more than the rest combined. Do not start at the bottom
because it is more interesting.

Small commits, one concern each.

## Gates — they must pass before you call anything done

```bash
node uplift/checks/audit-perf.js       # the audit that produced the baseline
node uplift/checks/audit-detail.js     # fonts, audio, landmarks, headings
bash uplift/checks/copy-guard.sh .     # terminology + comparison language
python3 uplift/checks/consistency.py   # every task still measurable
```

`copy-guard.sh` and `consistency.py` are wired to fail loudly. If you add a
task or a metric, `consistency.py` will tell you what you forgot.

## Judgement

When a fix would improve a number but hurt the reader, choose the reader and
say so in the report. The metrics exist to serve that reader; the moment they
are optimised against them, they are worse than having none.

If you find something not in this brief, act on it and say so — the site is
live and it changes under you. During the writing of this package the agents
published twice and a workflow hung; both were real findings that nobody had
planned for.

## Report at the end of every session

- The rows you own, before and after, real measured numbers, no rounding in
  your favour.
- Anything you could not fix, and why. An honest gap list is worth more than a
  padded one.
- Anything you could not verify, stated plainly rather than omitted.
- If a target was missed, by how much. Never state a range and let the good
  end stand for the result.

Start with task 1.
