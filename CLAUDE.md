# History Photographed — AI Reel Pipeline

This project produces publish-ready Instagram Reels (9:16, 30–90s) in the storytelling style of [@historyphotographed](https://instagram.com/historyphotographed) — historical photos with narrated micro-stories.

## How to use it

Main entry point:
```
/make-reel "topic"
```
Walks Jude through three approval gates: **script → photo selection → final video**. The system never publishes; Jude uploads `final.mp4` to Instagram manually.

Quarterly formula refresh:
```
/analyze-formula
```
Scrapes ~100 top-performing @historyphotographed Reels via Apify, extracts hook patterns / cadence / vocabulary / endings into `reference/formula.md`. The scriptwriter agent loads this every run.

Re-enter the pipeline after rejecting at a gate:
```
/revise-reel --gate {script|photos|video}
```

## Hard rules (non-negotiable)

1. **Photos: public domain only.** Sources allowed: Wikimedia Commons, Library of Congress, Europeana (PD/CC0 tags only), NARA, Getty Open Content. Hard reject any image whose `license_tag` is not in the allow-list.
2. **No fabricated history.** Never use AI image generators to invent photos of real events. Photos come from archives, with verifiable provenance.
3. **No influencer voice cloning.** TTS only (ElevenLabs v3 primary, Hume Octave drama fallback, OpenAI gpt-4o-mini-tts budget).
4. **No @historyphotographed asset republishing.** Their corpus is for *formula extraction* only — not for reuse.
5. **Three gates always.** Never skip Jude's approval — script, photos, video.

## What lives where

```
.claude/agents/       — Reasoning sub-agents (formula-analyst, researcher, scriptwriter, photo-curator, shotlist-director, qc-reviewer)
.claude/skills/       — User-invokable workflows (make-reel, analyze-formula, revise-reel)
.claude/scripts/      — Deterministic Python tools (Apify, archives, TTS, FFmpeg)
.claude/prompts/      — Reusable prompt fragments (narration style, shotlist schema)
content/<date>_<slug>/ — Per-Reel working dir (research, script, photos, audio, final.mp4, manifest.json)
reference/formula.md  — Extracted storytelling formula (10 sections, scriptwriter system prompt)
reference/top-reels.json — Apify scrape output (input to formula-analyst)
```

## Output anatomy of one Reel

Inside `content/<YYYY-MM-DD>_<slug>/`:
- `research.md` — verified facts + sources from researcher agent
- `script.json` — tagged narration + `pronunciation_overrides` + per-line beat annotations
- `shotlist_candidates.json` — photos the curator found, with provenance
- `photos/approved/` — Jude-selected subset
- `audio/narration.mp3` — TTS output (chunked + stitched)
- `shotlist.json` — final shot-by-shot directives (timing + Ken Burns)
- `final.mp4` — 9:16 1080×1920 Reel, captions burned in
- `manifest.json` — full provenance trail (every asset's source URL + license tag)
- `qc.md` — adversarial QC report

## Banned hook patterns (script writer must avoid)

Empirically underperforming on 34k+ short-form clips:
1. Story openers — "Let me tell you about…"
2. YouTube greetings — "Hi everyone…"
3. Delay phrases — "Okay so…"
4. Mental-effort questions — "Have you ever wondered…"

## Cost ceiling

Budget: **$2–$10 per finished 60s Reel.** MVP runs ~$2; production ~$3.50–$5. Logged per Reel in `manifest.json`. If a run exceeds $10, halt and ask.

## First-time setup

```bash
# 1. System deps
brew install ffmpeg

# 2. Python deps (use a venv)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Copy .env.example → .env and fill in keys
cp .env.example .env
# Then add ELEVENLABS_API_KEY, ELEVENLABS_DEFAULT_VOICE, OPENAI_API_KEY at minimum
```

## Env vars (see `.env.example`)

```
APIFY_API_TOKEN              # Instagram scraping (already set)
ANTHROPIC_API_KEY            # Claude orchestration (already set)
ELEVENLABS_API_KEY           # TTS primary  (TODO: add before /make-reel)
ELEVENLABS_DEFAULT_VOICE     # voice_id of chosen narrator  (TODO)
OPENAI_API_KEY               # Whisper transcription + budget TTS  (TODO)
HUME_API_KEY                 # Drama-segment fallback  (production cut)
TOPAZ_API_KEY                # Colorization  (production cut)
```

## Project status

- **MVP cut** (in progress): Wikimedia-only archive search, ElevenLabs v3 only, no Topaz colorize, no qc-reviewer (Jude is QC at gates), no music bed.
- **Production cut** (later): adds formula-analyst pipeline, shotlist-director, Topaz colorize, qc-reviewer at all 3 gates, TTS fallbacks, music bed, revise-reel, multi-archive search.

Plan reference: `/Users/air/.claude/plans/i-want-the-create-idempotent-otter.md`
