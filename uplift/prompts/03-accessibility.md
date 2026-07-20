# Task 3 — Accessibility

Owns: `landmarks_main` `landmarks_nav` `landmarks_header` `aria_live_regions`
`skip_link`

## What is actually broken

**There are no landmarks at all** — zero `<main>`, `<nav>`, `<header>`. A
screen reader user has no way past the ticker into the feed. Add proper
landmarks, a skip link, and a sane tab order.

**Live regions: zero.** The ticker and the alerts panel update continuously
and announce nothing. Alerts from a defence ministry during an active conflict
are the highest-stakes content on this page, and today a blind reader is not
told they arrived.

```html
<div aria-live="polite">   <!-- ticker -->
<div aria-live="assertive"> <!-- official alerts -->
```

**The isnad chain is conveyed by lit and unlit dots alone** — colour and shape
with no text equivalent. The `title` already carries the full breakdown
(`الاتصال: جزئي ← عدالة المصدر: غائب …`). Expose it as `aria-label`, and
render the verdict as text beside the score rather than only as a coloured
badge.

## Also

- Check contrast at AA. Gold `#C9A227` on near-black passes for large text —
  check the **small metadata text**, which is where this palette fails.
- Respect `prefers-reduced-motion`: kill the ticker scroll and the `.rise`
  entry animations for readers who ask for it.
- The Three.js canvas needs a text alternative describing what it shows.

## Definition of done

- `main`, `nav`, `header` each present exactly once
- ≥ 2 `aria-live` regions, correct politeness levels
- Skip link present and first in tab order
- Every isnad chain has an `aria-label` with the five-criteria breakdown
- Keyboard-only pass: reach the feed, play the bulletin, open an item
- `prefers-reduced-motion: reduce` stops all autoplay motion
- axe-core: zero critical or serious violations
