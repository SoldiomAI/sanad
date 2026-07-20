# Task 5 — Agents and data integrity

Eleven agents run every three hours. Today the failure modes are invisible
until they reach the reader.

## Harden

**Schema-validate every agent output before it can touch published data.**
A malformed run fails loudly and leaves the last good state intact. Never
publish partial.

**Make runs idempotent and content-addressed.** Re-running an agent on the
same inputs must produce the same output. Without this, a disputed grade
cannot be reproduced, and a grade that cannot be reproduced cannot be
defended.

**Log the grading inputs beside the grade.** When a reader disputes a 2/7 you
need to reconstruct exactly what the agent saw. Store the five criteria
evaluations individually — not just the total. The total is the conclusion;
the five are the argument.

**Alert on silence.** No publish in over 6 hours is an incident. Surface it on
the page as a stale-data banner. Showing old news as current is worse than
showing nothing.

**Rate-limit and back off** against source APIs. Degrade to cached sources
rather than dropping a section — a missing section reads as "nothing
happened", which is a claim you did not intend to make.

## Definition of done

- Every agent output passes schema validation or the run aborts
- Same inputs → identical output, proven by a repeat-run test
- Per-item storage includes all five criteria evaluations
- Stale-data banner appears automatically past 6 hours
- A forced source-API failure degrades to cache without dropping a section
