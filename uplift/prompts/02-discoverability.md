# Task 2 — Findable and citable

Owns: `jsonld_blocks` `has_rss` `has_manifest` `h2_count`

## The strategic gap

The site emits **zero structured data**. SANAD's entire product is issuing
graded judgements on claims — and Google has a schema for exactly that. This
is how verification work surfaces in Search and Google News, and SANAD is
invisible to it.

Emit per graded item:

**`ClaimReview`**
- `claimReviewed` — the claim, in Arabic
- `author` — SANAD as `Organization`
- `reviewRating` — `ratingValue` from the 7-point isnad score,
  `bestRating: 7`, `worstRating: 1`, `alternateName` the Arabic verdict
  (`صحيح` / `حسن` / `ضعيف الإسناد`)
- `itemReviewed` — pointing at the original source URL

**`NewsArticle`** — headline, `datePublished`, `dateModified`,
`inLanguage: "ar"`, publisher.

**`Organization`** once per page — logo, `sameAs`.

Validate against the Rich Results Test before shipping. A malformed
`ClaimReview` is worse than none: it gets the domain flagged.

## Cheap and missing

- **RSS.** A news platform without a feed is invisible to every aggregator.
- **sitemap.xml.**
- **Web app manifest.**

## Permalinks

Give every graded item a **stable URL**. A verification platform whose
individual judgements cannot be linked, cited, or argued with cannot be held
to them — and being held to them is the entire proposition.

## Heading hierarchy

The page goes H1 → H3 with no H2. Crawlers and assistive tech both read that
as structurally flat. Fix the order; do not fake it with styling.

## Definition of done

- 3 JSON-LD blocks, all passing the Rich Results Test
- `/rss.xml`, `/sitemap.xml`, `/manifest.webmanifest` all 200
- Every feed item has a permalink that resolves and renders standalone
- Heading order valid — no level skipped
