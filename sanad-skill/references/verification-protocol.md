# SANAD Runbook — دليل التنفيذ للوكلاء
Step-by-step procedure. Follow in order; do not skip gates.

## Phase A — Scout (وكيل الرصد)
1. Search with time-bounded queries (last 24–48h). Prefer `site:` scoping to Tier-1
   domains when the tool allows.
2. For each candidate item, capture: headline, 2-sentence summary, source name,
   **the exact URL from search results**, timestamp, severity.
3. Discard immediately (do not pass downstream): items with no URL; URLs not on the
   registry; screenshots-as-source; "sources say" items.
4. Emit scout schema (see output-schema.md). Scouts do NOT grade — grading is the
   analyst's monopoly, so one biased scout cannot poison the feed.

## Phase B — Analyst (الوكيل المحلّل)
For each incoming item:

**B1. Fetch the URL.**
- 200 + content matches claim → `url_status: fetched_200`, continue.
- 404/redirect to homepage/paywall-empty → try to locate the same statement on the
  origin Tier-1 domain. Found → replace URL. Not found → مردود (مقطوع السند).

**B2. Trace the isnād.** Identify the ORIGIN (who spoke first: ministry, command,
agency). Record the chain as an array, origin-first.

**B3. Grade the narrator** against source-registry.md. Tier-3 origin → ضعيف (watchlist).

**B4. ضبط check.** Compare numbers/dates/names in the summary vs the fetched text.
Drift → fix the summary to match origin, note `matn_flags: ["تصحيف_مصحح"]`.

**B5. Independence & corroboration.**
- Search for a second chain to the SAME fact. Two outlets quoting one statement = one
  chain. Independent second chain found → صحيح. Otherwise → حسن.

**B6. Matn criticism.** Run the fabrication checklist:
- timeline possible? geography real? magnitudes plausible? phrasing consistent with
  official register? date of embedded media consistent with claim date?
- Any failure → downgrade one grade and record the flag (شاذ / معلول / علامة_تلفيق).
- Contradicts a stronger report → mark شاذ, keep only the stronger.

**B7. Custody stamp.** `retrieved_at` (ISO-8601), `agent`, sha256 of the fetched text
snippet you relied on. This makes every brief auditable later.

## Phase C — Merge & Brief
1. Deduplicate by ORIGIN STATEMENT (same ministry statement via 3 outlets = 1 item,
   keep strongest chain, move others to `corroborations`).
2. Sort عاجل → مهم → متابعة. Cap at 10.
3. Brief: 3–5 sentences, each traceable to a graded item; no adjectives of emotion,
   no speculation, no totals not present in sources.
4. Footer line with counts: `التحقق: بروتوكول سَنَد — X صحيح، Y حسن، استُبعد Z`.

## Escalation to human (رفع للعامل البشري)
Escalate instead of publishing when:
- A صحيح-grade item implies imminent public danger (evacuation-level) — human confirms
  before display.
- Two Tier-1 sources CONTRADICT each other (rare, serious) — publish neither; escalate.
- A registry change seems needed (new agency, compromised domain).

## Timing rules
- Crisis mode: re-run swarm ≤ every 15 min; carry forward previously-graded items
  without re-fetch for 2h (custody stamp shows original fetch).
- An item older than 48h leaves عاجل automatically.

## Worked examples

**Example 1 — upgrade path.** Scout brings "الدفاع الجوي يعترض مسيّرات فوق المنطقة
الشمالية — المصدر: صحيفة إقليمية". Analyst finds the same fact as a Ministry of Defence
statement on KUNA → origin re-pointed to KUNA (Tier 1), regional paper moved to
corroborations → grade صحيح.

**Example 2 — rejection.** Viral post: "استهداف ميناء X، ٤٠ قتيلًا" with a screenshot
of an "official statement". No matching text on any Tier-1 domain; number suspiciously
round; image metadata date = 2019 → مردود (مقطوع + علامة_تلفيق). Logged, never shown.

**Example 3 — precision fix.** Agency says "اعتراض ٣٢ مسيّرة"; scout summary says
"العشرات". Analyst rewrites to "٣٢ مسيّرة" citing the fetched text → تصحيف_مصحح,
grade unaffected.
