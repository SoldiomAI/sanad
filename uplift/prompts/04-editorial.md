# Task 4 — Editorial integrity

Owns: the invariants in `00-context.md` — enforced by CI, not by memory

This is the part that cannot be bought back once lost. Every rule here was
already violated once and caught by a human. Make the machine catch it next
time.

## Turn conventions into gates

**Terminology.** Fail the build on `الأركان الخمسة`. The only accepted phrasing
is `خمسة معايير من علم الحديث`.

**Comparison language.** Fail on copy that positions SANAD against another
outlet. `checks/copy-guard.sh` carries the pattern list — extend it as new
phrasings appear, and treat every extension as evidence the gate is working.

**Attribution.** A test that fails when an official badge is attached at card
level rather than field level. This shipped once and misled readers about what
was officially confirmed.

**Corrections log.** A test that fails when a published figure differs from
the previous published figure without a corresponding corrections entry
carrying before, after, and both sources.

**Quality guard.** It must compare against the **published** version, not
local state. A previous bug let good live data be overwritten by a worse fresh
run because the comparison never looked at what was live.

## The display rule

Audit that low scores are rendered with the same weight, size, and contrast as
high ones. If a 2/7 is quieter than a 7/7 anywhere in the UI, that is a bug of
the most serious kind on this platform — the score stops being a measurement
the moment it is styled for persuasion.

## Definition of done

```bash
bash checks/copy-guard.sh    # exits non-zero on any violation
```

- Wired into CI, blocking merge
- Attribution test and corrections test both present and passing
- Quality guard reads the published version — proven by a test that fails if
  it is pointed back at local state
- A visual diff showing 2/7 and 7/7 rendered at identical weight
