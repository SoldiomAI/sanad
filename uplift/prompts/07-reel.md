# Task 7 — Distribution

Do this only after the platform holds. A reel pointing at a 4.8-second load is
an advertisement for the load.

## The reel pipeline exists — use it, do not rewrite it

`sanad-data/skills/screen-reel/`

**Narrative contract: experience first, then reveal.** An ordinary headline,
then the grade surfacing underneath it, then the platform. Never open on the
brand. Never explain before showing.

**Read the grade off the live page.** If today's lead item is 6/7 rather than
2/7, rewrite the captions — a strong score is a different and equally honest
story. Never hardcode a score into a script.

## Traps — each one shipped broken output that survived review

- `viewport` must equal `recordVideo.size`, or the page fills a fraction of
  the frame. Record 720×1280 matched, upscale 1.5× — not 540×960 at 2×.
- Never `drawtext` for Arabic: letters render unjoined and reversed. Render
  captions to PNG via Pillow with `direction="rtl", language="ar"`.
- Do not combine `arabic_reshaper` + `python-bidi` with RAQM — double-shaping
  breaks the text. Assert `PIL.features.check("raqm")`.
- Fully vocalize all TTS input. Partial diacritics are worse than none:
  `خبرٍ` was read as `خِبْرة`; `خَبَرٍ` is correct.
- Whisper must verify generated audio. Three mispronunciations once survived
  review-by-listening in a single session.
- Measure pace on **speech only** — 120–150 wpm. Silence padding once made a
  122 wpm read look like 36.
- If pace is too fast, that is not randomness — do not re-roll seeds. Slow it
  with `atempo` (pitch-preserving).
- ffmpeg audio input index = caption PNG count + 1.
- Loudness-normalize to `I=-14 LUFS`. Platforms re-normalize and a quiet mix
  gets crushed.
- Silent is a legitimate ship. Prefer silence over a voice that fails
  verification, and say so in one line — do not bury it.

## Telegram

Exclusivity rules stand: official statements immediately; breaking news only
at `صحيح` or ≥ 6/7; new alerts only; MD5 fingerprints against repeats; daily
caps per type.

## Definition of done

- Coverage ≥ 85% · caption ink > 1500 px · 1080×1920 · < 5 MB · faststart
- Whisper diff on the **final composed** audio: zero word differences
- Pace 120–150 wpm measured on speech only
- One frame per beat extracted and **actually viewed** before shipping
- Anything not verified stated plainly in the report
