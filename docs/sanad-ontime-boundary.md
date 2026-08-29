# SANAD to OnTime signal boundary

SANAD remains the editorial and verification authority. OnTime receives a
read-only export of approved, attributed signals. It cannot write to SANAD or
modify news, evidence, source grades, verification outcomes, history, health
records, or editorial rules.

## Data flow and ownership

`pipeline/intelligence_signals.py` reads only the current local products
`news.json`, `official.json`, `osint.json`, `map.json`, `tension.json`,
`papers.json`, and `repos.json`. It makes no model or paid API calls. It writes:

| Product | Purpose | Health owner |
| --- | --- | --- |
| `daily/events.json` | Conservative event clusters with full evidence | `intelligence_signals` |
| `daily/signals.json` | SANAD assessments derived from qualified events and thresholds | `intelligence_signals` |
| `daily/ontime-signals.json` | Allowlisted downstream contract | `intelligence_signals` |

The daily runner generates all three files after the source products and before
`hirasa()` and `bundle()`. They are included in `daily/bundle.json` and copied
by `.github/workflows/news-refresh.yml` to the public
`SoldiomAI/sanad-data` repository. SANAD owns generation, freshness, failures,
schema changes, and editorial meaning. OnTime owns only polling, schema
validation, local ingestion health, and its decisions after ingestion.

Generation is deterministic for the same inputs. IDs are content-derived.
Existing `created_at` values are retained for stable IDs, while `updated_at`
changes only when content changes. Untimestamped or stale observations are
suppressed. A failed generator is recorded as a failed auxiliary module and
degrades health even if files from an earlier run remain on disk.

The export is a current approved snapshot. Absence in a later snapshot means
"not currently exported"; it is not a retraction instruction and never means
that a consumer should erase history. Consumers should version changed rows,
mark absent rows inactive if needed, and treat only a future explicit
retraction/tombstone as a request to label prior content retracted.

## Signal meanings

The signal types are:

- `contradiction`: an explicit denial and a substantially overlapping
  attributable headline; SANAD does not resolve the claim in this product.
- `multi-source-event`: at least two named sources and two distinct evidence
  URLs in one conservative event cluster.
- `country-risk-threshold`: the published SANAD tension score is at least 60;
  this is neither a prediction nor an official warning.
- `watchlist-match`: an existing public watch term has heat of at least 50 and
  at least one graded SANAD hit.
- `ai-research-trend`: at least two recent attributed papers match the same
  deterministic research-topic vocabulary.
- `ai-repository-trend`: at least two recently pushed repositories in a live
  GitHub radar share a SANAD classification. Fallback repository data never
  creates this signal.

Every record separates `observed_facts`, `sanad_assessment`, `inference`, and
`uncertainty`. Event facts state that an attributable source published a
headline; they do not silently promote the headline's claim into an established
real-world fact. `confidence` measures confidence in the deterministic signal
classification, not the truth probability of the underlying claim. Missing
evidence does not become a fact.

## Exact OnTime schema (`schema_version: "1.0"`)

```json
{
  "schema_version": "1.0",
  "generated_at": "ISO-8601 UTC string",
  "updated_at": "ISO-8601 UTC string",
  "cursor": "sha256:<64 lowercase hex chars>",
  "producer": "SANAD",
  "authority": "SANAD",
  "read_only": true,
  "signals": [
    {
      "id": "sig_<16 lowercase hex chars>",
      "type": "contradiction | multi-source-event | country-risk-threshold | watchlist-match | ai-research-trend | ai-repository-trend",
      "title": "string",
      "title_en": "string",
      "summary": "string",
      "observed_at": "ISO-8601 source timestamp",
      "valid_until": "optional ISO-8601 UTC string",
      "observed_facts": ["string"],
      "assessment": "string",
      "inference": "string",
      "uncertainty": "string",
      "confidence": 0.0,
      "severity": "info | low | medium | high | critical",
      "countries": ["ISO-like SANAD country ID"],
      "sectors": ["string"],
      "topics": ["string"],
      "evidence": [
        {
          "source_ref": "ev_<16 lowercase hex chars>",
          "url": "source URL",
          "publisher": "string",
          "grade": "existing SANAD grade or empty string",
          "published_at": "source timestamp",
          "title": "string",
          "title_en": "string",
          "dataset": "news | official | osint | map | tension | papers | repos"
        }
      ],
      "contradictions": [
        {
          "id": "con_<16 lowercase hex chars>",
          "type": "explicit-denial",
          "summary": "string",
          "evidence_ids": ["ev_<id>"]
        }
      ],
      "event_ids": ["evt_<16 lowercase hex chars>"],
      "created_at": "ISO-8601 UTC string",
      "updated_at": "ISO-8601 UTC string"
    }
  ]
}
```

The export is an explicit allowlist. It excludes credentials, prompts,
editorial rules, internal thresholds, raw control state, and non-approved
fields. Consumers must reject unknown major schema versions and preserve SANAD
IDs and provenance unchanged. The cursor is a deterministic SHA-256 of the
ordered approved signal content excluding lifecycle timestamps; consumers may
also hash the complete manifest independently.

## Field types

Strings are UTF-8 JSON strings. `confidence` is a JSON number in `[0, 1]`;
`read_only` is a boolean. `observed_facts`, `countries`, `sectors`, `topics`,
and `event_ids` are arrays of strings. `evidence` and `contradictions` are
arrays of objects. `signals` is an array of signal objects. `valid_until` is
optional; all other fields shown above are present, though a string or array
may be empty when the source did not publish that value.
