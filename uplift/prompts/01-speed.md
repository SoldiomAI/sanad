# Task 1 — Delivery speed

Owns: `ttfb_ms` `dom_interactive_ms` `load_ms` `page_weight_kb` `font_kb`
`font_files` `audio_preload_kb` `js_kb` `html_kb` `feed_items_in_dom`

## The four that matter

Everything else on this page is noise next to these.

**1 — The origin is in San Francisco and the readers are in Kuwait.**
That alone is most of the 2,566 ms TTFB. And the response says
`cache-control: public, max-age=0, must-revalidate`, so there is no edge cache
to hide behind — every reader waits on the origin.

Move the deployment region to the nearest Vercel region to the Gulf (`fra1`
today). Then stop hitting the origin at all for the common case: the page is a
snapshot the agents regenerate every three hours, so serve it from the edge.

```
Cache-Control: public, s-maxage=300, stale-while-revalidate=3600
```

A reader during a strike gets a cached page in under 400 ms and a fresh one in
the background. Do not make anyone wait on a cold function for content that is
forty minutes old regardless.

**2 — 680 KB of fonts across 16 woff2 files**, served from Google Fonts.
Self-host. Subset to the Arabic block plus the Latin digits and punctuation
actually used. Ship **two** weights — one text, one display. `font-display:
swap`. Preload only those two. Expect under 90 KB. Every weight beyond the
second is a cost the reader pays and cannot perceive.

**3 — The audio bulletin downloads 1,014 KB before anyone presses play.**
The `?t=` cache-buster on its URL also means it can never be cached, so it
re-downloads on every visit. Set `preload="none"`, attach `src` on first
interaction, replace the buster with a content-hashed filename and a long
`max-age`. Half the page weight recovered from one attribute.

**4 — Three.js loads eagerly for a section below the fold.** Dynamic import
behind `IntersectionObserver`, with a static poster so the section is not
blank while it loads.

## Then

- Render ~12 feed items and add progressively. 57 items is 174 KB of HTML
  most readers never scroll to.
- Service worker, stale-while-revalidate on `bundle.json`, small offline
  shell. During a network brownout a returning reader should still see the
  last known state — **always stamped with its age**. Never show stale data
  without its timestamp.

## Definition of done

```bash
node checks/audit-perf.js
```

- `ttfb_ms` < 400 · `load_ms` < 2500 · `page_weight_kb` < 450
- `font_files` ≤ 2 · `font_kb` < 90
- `audio_preload_kb` == 0 before any click
- `console_errors` still 0
- Offline reload shows last state with a visible age stamp
