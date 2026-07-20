# Context — load this with every task

## What SANAD is

**isnad.news** (سَنَد) applies isnad methodology from hadith science to modern
news. Every item is graded on a 7-point scale against five criteria, and the
chain of transmission is shown to the reader rather than summarised for them.

The reader is in Kuwait or the Gulf, on mobile, often on a degraded network
during an active conflict. Judge every decision against that reader — not
against a desktop on fibre.

## Repos — do not collapse this split

| repo | visibility | holds |
|---|---|---|
| `Soldiom/sanad` | **private** | all code, prompts, agent logic, workflows |
| `Soldiom/sanad-data` | public | JSON, media, and the `screen-reel` skill |

The code was once publicly visible. The split fixed that. Nothing revealing
scoring logic or prompts crosses into the public repo — ever.

## Invariants

These are not preferences. Breaking one is a bug regardless of how good the
rest of the change is.

1. **Terminology.** Never "الأركان الخمسة". Always
   "خمسة معايير من علم الحديث". The five: الاتصال · عدالة المصدر · الضبط ·
   عدم الشذوذ · انتفاء العلة.
2. **No comparison.** Never position SANAD against other outlets — no
   "unlike others", no implied contrast, no naming competitors. State the
   method; let the reader draw the conclusion. That judgement is only worth
   something coming from them.
3. **Attribution is per field, not per card.** An official badge belongs on
   the specific figure a ministry declared, never on a card that also carries
   figures from elsewhere.
4. **Numbers never change silently.** Every changed figure goes to the
   corrections log with before, after, and both sources.
5. **Uncertainty is displayed as prominently as confidence.** A 2/7 is as
   legible as a 7/7. The moment weak items are quietly de-emphasised, the
   score stops being a measurement and becomes marketing.
6. **No secret in the repo, in a bundle, or in a chat.** Environment
   variables only. Fine-grained tokens, single repo, 7-day expiry.

## Working rules

- One task file at a time. Small commits, one concern each.
- Re-measure the rows your task owns and show before/after.
- If a fix would improve a number but hurt the reader, choose the reader and
  say so in the report.
- Report misses by how much. Never report a range and let the good end stand
  for the result.
