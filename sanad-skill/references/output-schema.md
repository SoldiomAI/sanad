# SANAD Output Schemas — عقود المخرجات

## 1. Scout report (وكيل الرصد) — ungraded
```json
{
  "agent": "gulf",
  "items": [{
    "title": "string (Arabic)",
    "summary": "string, 2 sentences",
    "source": "string (registry name)",
    "url": "https://… (exact from search, never constructed)",
    "time": "string",
    "severity": "عاجل|مهم|متابعة",
    "region": "gulf|palestine|mashreq|ummah"
  }]
}
```

## 2. Verified item (المحلّل) — graded
```json
{
  "title": "string",
  "summary": "string (numbers exactly match origin)",
  "grade": "صحيح|حسن",
  "isnad": ["بيان وزارة الدفاع الكويتية", "كونا", "retrieved 2026-07-18T09:41Z"],
  "source": "KUNA",
  "url": "https://www.kuna.net.kw/…",
  "url_status": "fetched_200",
  "corroborations": [{"source": "Reuters", "url": "https://…"}],
  "time": "قبل ساعتين",
  "region": "gulf",
  "severity": "عاجل",
  "matn_flags": [],
  "media_verified": false,
  "custody": {
    "retrieved_at": "2026-07-18T09:41:00Z",
    "agent": "analyst",
    "hash": "sha256:…"
  }
}
```

## 3. Operations brief (موجز العمليات)
```json
{
  "brief": "٣–٥ جمل وقائعية",
  "stats": {"sahih": 4, "hasan": 3, "excluded": 6},
  "footer": "التحقق: بروتوكول سَنَد — ٤ صحيح، ٣ حسن، استُبعد ٦",
  "items": ["<verified items, sorted, max 10>"]
}
```

## 4. Audit log entry (سجل الاستبعاد) — every rejection is logged
```json
{
  "rejected_title": "string",
  "reason_code": "مقطوع|مبهم|مجروح|تصحيف|شاذ|معلول|علامة_تلفيق|رابط_ميت",
  "detail": "one sentence",
  "candidate_url": "string|null",
  "at": "ISO-8601",
  "agent": "analyst"
}
```

## Failure codes (رموز الاستبعاد)
| Code | Meaning |
|---|---|
| مقطوع | Chain severed — origin unreachable/untraceable |
| مبهم | Anonymous hop ("sources say") |
| مجروح | Rejected narrator (registry) |
| تصحيف | Content drift vs origin (fixable → تصحيف_مصحح) |
| شاذ | Contradicts stronger report |
| معلول | Hidden defect (timeline/geo/physics) |
| علامة_تلفيق | Fabrication marker in matn |
| رابط_ميت | URL dead and origin not found |

## Display contract (للواجهة)
- صحيح → badge `✓✓ صحيح` (emerald). حسن → badge `✓ حسن — مصدر واحد` (amber).
- Always render `↗ فتح المصدر` linking `url`; corroborations as secondary links.
- Brief footer line is mandatory and non-editable by UI.
