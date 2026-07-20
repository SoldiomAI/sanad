# Task 8 — Reliability of the daily pipeline

Owns: `bulletin_freshness` `failure_visibility` `stale_disclosure`

## What actually happened

Measured 2026-07-20 15:41 UTC:

```
news-refresh    04:16 · 07:03 · 10:02 · 12:42     all success      ✅
bundle.json     built = 2026-07-20T12:47Z          3 hours old      ✅
daily/          bulletin-2026-07-18.mp3
                bulletin-2026-07-19.mp3 + .mp4
                (no 2026-07-20)                                     ❌
latest.date     "2026-07-19"                                        ❌
```

The news feed refreshes every three hours and is healthy. The daily anchor
bulletin is a full day behind, and the page presents yesterday's bulletin under
the heading **نشرة اليوم** — a claim nobody intended to make.

The anchor workflow history explains it:

```
19 Jul 15:24   schedule            ❌ failure
19 Jul 17:52   workflow_dispatch   ✅ success     ← rescued by hand
20 Jul 15:39   schedule            ⏳ running
```

`daily-anchor.yml` runs on `cron: '0 15 * * *'` — **once a day**. When it fails
there is no retry, no alert, and no signal on the page. The failure lives for
24 hours, and it survived only because a human happened to trigger it manually
without knowing they were performing a rescue.

Compare with `news-refresh.yml` on `cron: '0 */3 * * *'`: eight chances a day,
so a single failure is invisible and harmless. The anchor has one chance, so a
single failure is total.

## Three changes

**1 — Conditional retry.** A second scheduled run one hour later that checks
whether today's bulletin exists and exits immediately if it does. Cheap when
things work, decisive when they do not.

```yaml
on:
  schedule:
    - cron: '0 15 * * *'
    - cron: '0 16 * * *'   # retry only if today's bulletin is missing
```

Guard the job on the absence of `daily/bulletin-$(date -u +%F).mp3`. Do not
regenerate a bulletin that already exists — it burns GPU quota, and quota
exhaustion is itself a documented cause of failure here.

**2 — Alert on failure and on silence.** Send to `t.me/sanad_news` admin — not
the public channel — when the anchor workflow concludes `failure`, and when no
bulletin has been produced for the current day past 17:00 UTC.

The agents broadcast to readers continuously and broadcast nothing when they
themselves fall over. Fix that asymmetry. **Silence must be an event.**

**3 — Disclose staleness in the UI.** If `latest.date` is older than today,
the page must say so rather than labelling it **نشرة اليوم**.

```
نشرةُ ١٩ يوليو — لم تصدر نشرةُ اليوم بعد
```

This follows directly from the existing invariant that uncertainty is shown as
prominently as confidence. A platform whose entire proposition is grading the
reliability of information cannot quietly present day-old content as current.
That is the one failure mode that costs more than an outage.

## Also worth fixing while here

The HTML is served from the edge at **`age: 31641`** — 8.8 hours — with
`x-vercel-cache: HIT`, despite `cache-control: max-age=0, must-revalidate`.
Data is fetched client-side with a cache-buster so readers still get fresh
news, but the caching layer is not doing what the headers claim. Task 1 owns
the fix; verify here that the two are consistent once it lands.

## Definition of done

- Retry cron present, guarded on today's bulletin being absent
- A forced failure produces an admin alert within 10 minutes
- No bulletin by 17:00 UTC produces an alert without any failure occurring
- With `latest.date` set to yesterday in a test fixture, the page renders the
  stale-date wording and never the words **نشرة اليوم**
- One deliberate end-to-end failure exercise, executed and documented
