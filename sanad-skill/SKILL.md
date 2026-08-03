---
name: sanad-verification
description: >
  SANAD (سَنَد) — Sovereign source-verification protocol for Arabic/Islamic-world news
  and OSINT. Applies the 1,200-year-old isnād methodology of hadith science (علم الحديث)
  fused with digital-forensics chain-of-custody to grade every claim as صحيح/حسن/ضعيف/مردود
  before it reaches a human. Use this skill whenever an agent must verify news about
  attacks, conflicts, or events in Muslim-majority countries; whenever a claim needs an
  official source and a working link; whenever deduplicating or merging multi-agent scout
  reports into one operations brief; or whenever the user asks to "تحقق من المصدر",
  "verify this", "هل الخبر صحيح", or requests an operations brief (موجز عمليات).
license: Proprietary — SOLDIOM Sovereign AI (Kuwait). All rights reserved.
---

# SANAD — بروتوكول الإسناد للتحقق السيادي

> **The thesis:** The Islamic world invented source verification. For twelve centuries,
> hadith scholars graded millions of reports through *isnād* (chain of transmission) and
> *matn* (content) criticism — the most rigorous information-authentication system ever
> built by humans. SANAD encodes that methodology, fused with modern digital-forensics
> chain-of-custody (ISO/IEC 27037), into an executable protocol for AI agents.
> No Western fact-checking framework has this lineage. This is sovereign Gulf IP.

## When to apply

Apply SANAD to **every factual claim** an agent intends to publish, display, or pass
downstream — especially: military/security events, casualties, official statements,
infrastructure damage, and anything that could cause panic or policy response.
**A claim that has not passed SANAD does not exist.** Silence is always preferable to
an ungraded claim.

## خمسة معايير من علم الحديث (Five Criteria from Hadith Science)

Every claim must pass five gates, in order. Fail any gate → drop to the indicated grade.

### 1. الإسناد — Chain of Transmission
Trace the claim backward to its origin. Ask: *who* said it *first*?
- Build the chain: `عرض النتيجة ← الوكيل ← المقال ← الوكالة ← البيان الرسمي الأصلي`
- Every hop must be identifiable. An anonymous hop (= مُبْهَم) breaks the chain.
- A claim whose chain ends at social media, a blog, or "sources say" is **مقطوع السند**
  (severed chain) → grade مردود.

### 2. عدالة الراوي — Integrity of the Narrator (Source Tiers)
Grade the *origin* source, not the re-publisher. Full registry: `references/source-registry.md`.
- **الطبقة الأولى (ثقة ثبت):** State news agencies of the country concerned (KUNA, SPA,
  WAM, QNA, BNA, ONA, PETRA, WAFA, INA…) + official ministry/military statements.
- **الطبقة الثانية (صدوق):** Reuters / AP / AFP **only when quoting a Tier-1 source by name**.
- **الطبقة الثالثة (مقبول بشاهد):** Established regional outlets — acceptable only as
  *corroboration* (شاهد), never as sole source.
- **مجروح (rejected narrator):** Anonymous accounts, aggregators, AI-generated sites,
  outlets with a documented fabrication record. Their reports are void even if true.

### 3. الضبط — Precision of Transmission
Does the re-published claim match the original wording?
- Fetch the origin URL. Compare numbers, dates, place names, and attributed quotes
  against the article. Any material drift = تصحيف (corruption) → downgrade one level.
- Numbers are sacred: casualties, distances, counts must match the origin exactly or be
  reported as a range with both sources cited.

### 4. الشاهد والمتابعة — Corroboration
- One Tier-1 source = grade **حسن** (publishable, marked single-source).
- Two independent Tier-1/Tier-2 chains for the same fact = grade **صحيح**.
- Independence test: two outlets quoting the *same* statement are ONE chain, not two.

### 5. نقد المتن — Content Criticism (the forensic gate)
Even a perfect chain can carry a broken text. Reject or downgrade when the *matn* shows:
- **الشذوذ (anomaly):** contradicts a stronger, better-attested report.
- **العلة (hidden defect):** impossible timeline, geography that doesn't exist,
  physics that doesn't work (drone ranges, blast radii), recycled old footage/dates.
- **علامات التلفيق (fabrication markers):** emotional superlatives in "official" text,
  numbers too round, statements no official body would phrase that way.
- For media artifacts (images/video), flag for deepfake/provenance analysis — do not
  authenticate media by eye. Mark `media_verified: false` unless a forensic pass ran.

## The Grades (الأحكام)

| Grade | الحكم | Meaning | Action |
|---|---|---|---|
| **صحيح** | SAHIH | Unbroken Tier-1 chain + corroborated + clean matn | Publish. Badge ✓✓ |
| **حسن** | HASAN | Unbroken Tier-1 chain, single source, clean matn | Publish, marked "مصدر واحد". Badge ✓ |
| **ضعيف** | DA'IF | Tier-3 only, or minor chain gap | Hold in watchlist. Never display as news. |
| **مردود** | MARDUD | Broken chain, rejected narrator, or failed matn | Discard. Log reason for audit. |

**Hard rule:** the published feed contains صحيح and حسن ONLY.

## Output contract

Every verified item MUST emit this schema (full schemas + examples in
`references/output-schema.md`):

```json
{
  "title": "…", "summary": "…",
  "grade": "صحيح|حسن",
  "isnad": ["origin official statement", "agency", "retrieval"],
  "source": "KUNA", "url": "https://…", "url_status": "fetched_200",
  "corroborations": [{"source": "Reuters", "url": "https://…"}],
  "time": "…", "region": "…", "severity": "عاجل|مهم|متابعة",
  "matn_flags": [], "media_verified": false,
  "custody": {"retrieved_at": "ISO-8601", "agent": "analyst", "hash": "sha256:…"}
}
```

- `url` must be the **fetched, working origin link** — never constructed, never a homepage.
- `custody` implements chain-of-custody: when the claim was captured, by which agent,
  and a hash of the captured text — so any brief is auditable months later (court-grade
  habit, per ISO/IEC 27037 practice).

## Operations brief (موجز العمليات)

When merging multi-agent reports:
1. Run all five pillars per item. 2. Deduplicate by *origin statement*, not headline —
keep the strongest chain. 3. Write 3–5 sentences, facts only, ordered عاجل → مهم →
متابعة, each sentence traceable to a graded item. 4. End the brief with the line:
`التحقق: بروتوكول سَنَد — ن صحيح، م حسن، استُبعد ك` (fill the counts).
5. If nothing passes: publish exactly `لا توجد تقارير مستوفية شروط الإسناد حتى الآن` —
never pad with weak items.

## Forbidden behaviors (المحظورات)

- Never invent, reconstruct, or "fix" a URL. Fetch it or drop the item.
- Never upgrade a grade because a claim is dramatic, viral, or requested.
- Never translate a claim in a way that hardens it ("قد" ≠ "أكد").
- Never present a Tier-3 report as news, even with a disclaimer.
- Never authenticate images/video without a forensic pass — text verification ≠ media verification.

## Viral social pack (بطاقة السوشيال)

When generating Instagram/Telegram cards or voice clips (`pipeline/social_pack.py`):

1. **Authenticated only:** صحيح / حسن. Never ship ضعيف or مردود on a card.
2. **Viral gate:** score the day’s lead with `viral_score`; skip the pack if below
   `SANAD_SOCIAL_VIRAL_MIN` (default 55). Silence beats a weak share.
3. **Arabic typography:** assert Pillow RAQM. Pass logical Arabic with
   `direction="rtl", language="ar"`. Never combine `arabic_reshaper` + `python-bidi`
   with RAQM (double-shaping reverses/disconnects letters).
4. **Voice:** Edge TTS `ar-KW-FahedNeural` (Kuwaiti) for the spoken line; rate ≈ `-2%`.
   Prefer silence over a failed voice clip.
5. **Assets:** `feed.png` (1080²), `story.png` (1080×1920), `caption_ar.txt`,
   optional `voice.mp3` — templates only for captions; no invented methodology.

## References

- `references/source-registry.md` — full tiered registry: Gulf, Levant, North Africa,
  wider Islamic world; domains, verification notes, known-impersonation warnings.
- `references/verification-protocol.md` — step-by-step agent runbook: fetch sequences,
  independence tests, timing rules, escalation to human, worked examples.
- `references/output-schema.md` — JSON Schemas for scout reports, analyst briefs,
  audit logs; failure codes (مقطوع، مبهم، تصحيف، شاذ، معلول).
