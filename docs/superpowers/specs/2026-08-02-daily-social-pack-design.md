# Daily Social Pack (Viral Card) — Design

**Date:** 2026-08-02  
**Status:** Approved direction (user chose delivery model 3 + approach A)  
**Product:** Sanad / isnad.news  
**Goal:** Every day, auto-create a viral-ready Instagram pack, deliver it to the editor, and let them post manually under the isnad Instagram (and copy for other networks).

---

## 1. Problem

Sanad already grades news and can share links from the site, but there is no **daily, ready-to-post social pack**: square feed image, story image, caption, and a private delivery path. Manual design every day does not scale. Fully automatic Instagram posting is deferred (Meta setup + want human review).

## 2. Success criteria

- By Kuwait evening (or right after the day’s top authenticated story is known), the editor receives:
  - Feed PNG 1080×1080
  - Story PNG 1080×1920
  - Arabic caption (copy-paste)
  - Short story/WhatsApp text
  - Deep link to the story on isnad.news (`#/post/…`)
- Same pack is visible in `/admin` with download + copy + “posted” mark.
- Pack uses only **authenticated** stories (`صحيح` / `حسن`).
- No automatic publish to Instagram in v1.
- Generation cost stays near zero (templates + existing pipeline; no paid image API).

## 3. Non-goals (v1)

- Instagram / Meta Graph auto-publish
- Reels / video
- Daily Mudawwin column social posts (phase 2–3)
- Multi-story carousels
- Scheduling inside Meta

## 4. Recommended approach (locked)

**Approach A — pipeline-generated PNG pack + Telegram + Admin**

- Select top authenticated story of the day.
- Render branded HTML card templates → PNG (Chromium screenshot in CI/pipeline, or equivalent local render).
- Write text sidecars + `meta.json`.
- Telegram: private editor chat (not the public bulletin channel).
- Admin: Social tab for archive, download, copy, mark posted.

Typography must stay RTL-correct; prefer HTML→PNG over raw Pillow text shaping when both are available.

## 5. Architecture

```text
daily_anchor / news refresh
        │
        ▼
 select_social_story()     ← صحيح/حسن only, grade then recency
        │
        ▼
 render_social_pack()      ← HTML templates → feed.png + story.png
        │                    + caption_ar.txt + story_text.txt + meta.json
        ▼
 daily/social/YYYY-MM-DD/
        │
        ├──► tg_send_social_pack()   → private TELEGRAM_EDITOR_CHAT
        └──► published via sanad-data / site /daily/social/…
                    │
                    ▼
              /admin → Social tab
```

### Components

| Unit | Responsibility | Inputs | Outputs |
|------|----------------|--------|---------|
| `select_social_story` | Pick one viral story | `news.json` | story fields + post hash |
| `render_social_pack` | Build images + texts | story, brand assets, fonts | folder under `daily/social/DATE/` |
| `tg_send_social_pack` | Notify editor once/day | pack folder + TG secrets | Telegram messages; `tg.json` flag |
| Admin Social UI | Review / download / mark posted | pack JSON + images | `posted` flag in control or social meta |
| Deep link | Drive traffic back | `postPid(story)` | `https://isnad.news/#/post/{pid}` |

## 6. Story selection rules

1. Candidate pool: items with `isnad` and grade ∈ {`صحيح`, `حسن`}.
2. Sort: grade rank (`صحيح` > `حسن`), then newest `at`, then highest `score`.
3. Prefer stories with a usable headline (AR always; EN caption optional if `he` exists).
4. Idempotent: if `daily/social/DATE/meta.json` already exists for Kuwait today and `FORCE_SOCIAL` is unset, skip regenerate (unless story id changed and pack marked `draft` only — v1: skip if same date exists).
5. If pool empty: do not send Telegram noise; write `meta.json` with `status: "skipped"` and reason.

## 7. Pack file layout

```text
daily/social/YYYY-MM-DD/
  feed.png          # 1080×1080
  story.png         # 1080×1920
  caption_ar.txt    # IG feed caption
  caption_en.txt    # optional EN caption when he present
  story_text.txt    # short sticker / WhatsApp / Stories text
  meta.json         # machine-readable pack
```

### `meta.json` (v1 schema)

```json
{
  "date": "2026-08-02",
  "status": "ready",
  "platform": ["instagram_feed", "instagram_story", "whatsapp"],
  "head": "…",
  "he": "…",
  "grade": "صحيح",
  "src": "…",
  "link": "https://…",
  "score": 5,
  "post_url": "https://isnad.news/#/post/abcd1234",
  "pid": "abcd1234",
  "assets": {
    "feed": "feed.png",
    "story": "story.png",
    "caption_ar": "caption_ar.txt",
    "caption_en": "caption_en.txt",
    "story_text": "story_text.txt"
  },
  "posted": {
    "instagram": false,
    "other": false
  },
  "updated": "2026-08-02T18:00+00:00"
}
```

Also maintain `daily/social/index.json` listing recent packs (date, head, grade, status, posted flags) — last ~60 days.

## 8. Visual card (viral constraints)

Single composition, brand-first, no clutter:

- Full-bleed brand atmosphere (cream/ink theme matching Sanad — not generic purple AI look).
- Dominant: **سَنَد** mark + one headline.
- Supporting: grade badge (`صحيح ✓` / `حسن`), source name, isnad.news.
- No stat strips, no multi-card collage, no floating promo chips on the media.
- Story variant: same content, taller safe margins for IG UI chrome.
- Fonts: existing Sanad webfonts / Amiri + Noto Kufi already used on site.

Caption template (AR):

```text
{hook line}

«{headline}»
درجة الإسناد: {grade} · {src}

——
سَنَد يزن الخبر قبل النشر
{post_url}
```

Hook examples rotate from a small fixed list (templates only — no paid LLM required for v1 captions).

## 9. Telegram delivery

- **Secrets:** reuse `TELEGRAM_BOT_TOKEN`; add `TELEGRAM_EDITOR_CHAT` (private chat/group for editors). Do **not** post this pack to `TELEGRAM_CHANNEL` (public bulletin) in v1.
- Send order: `feed.png` with caption excerpt → `story.png` → full `caption_ar.txt` as message (or document).
- Idempotency: `tg.json` key `social_pack` = date when successfully delivered.
- Failures: log and leave pack on disk; Admin still works.

## 10. Admin Social tab

Under existing `admin.html` (token-gated):

- List packs from `social/index.json` (newest first).
- Detail: preview feed/story, buttons Copy caption / Copy link / Download PNGs.
- Toggle `posted.instagram` (and optional `posted.other`) via existing admin API pattern writing back to `meta.json` + index (or a small field in `control.json` map by date — prefer updating pack `meta.json` through admin API if write path exists; otherwise store posted map in `daily/social/posted.json` writable by admin).

**Posted-flag write path (explicit):** v1 uses `daily/social/posted.json` updated through `/api/admin` to avoid rewriting published pack blobs when possible:

```json
{ "2026-08-02": { "instagram": true, "other": false, "at": "…" } }
```

Admin UI merges this over `meta.json` for display.

## 11. Pipeline / CI integration

- New functions in `pipeline/daily_anchor.py` (or small `pipeline/social_pack.py` imported by it): `social_pack()` after news grades exist.
- Call from daily-anchor slot and/or end of news-refresh when authenticated items ≥ 1.
- Publish: existing `cp -r daily/*` to sanad-data already covers `daily/social/`.
- Site fallback: packs also available at `https://isnad.news/daily/social/DATE/…` when deployed.

## 12. Error handling

| Case | Behavior |
|------|----------|
| No authenticated news | `status: skipped`; no TG spam |
| Render failure | keep previous day’s pack; log; Admin shows error note if today missing |
| TG missing secrets | pack still written; skip send |
| Duplicate same day | skip unless `FORCE_SOCIAL=1` |

## 13. Testing

- Unit: story picker prefers `صحيح` over older `حسن`.
- Render smoke: produce both PNGs non-empty (>10KB) for a fixture story.
- Caption contains grade + `isnad.news` + `#/post/`.
- TG send mocked when secrets absent.
- Admin lists fixture pack and copy actions work.

## 14. Rollout phases

| Phase | Scope |
|-------|--------|
| **v1 (this spec)** | Daily card pack + TG editor + Admin Social |
| **v2** | 15–25s Reel from same card + TTS line |
| **v3** | Mudawwin column teaser 2–3×/week |
| **v4 (optional)** | Meta Graph publish after Business verification |

## 15. Open decisions (resolved)

| Decision | Choice |
|----------|--------|
| Delivery | Telegram private + Admin |
| Content v1 | Single top authenticated story card (feed + story) |
| Auto-post IG | No |
| Caption generation | Fixed rotating templates (no paid API) |
| Render | HTML template → PNG |

---

## Self-review notes

- No TBD placeholders left for v1 scope.
- Posted-flag path explicitly uses `posted.json` to avoid ambiguous admin writes.
- Scope is one implementation plan: pack generate + deliver + admin review.
