---
name: make-reel
description: Produce a publish-ready 9:16 Instagram Reel from a topic, in @historyphotographed's style. Three approval gates — script, photos, final video. Default entry point for the project.
---

# /make-reel

Take a topic from Jude and produce a publish-ready Instagram Reel in the storytelling style of @historyphotographed. Three approval gates. Never auto-publishes.

## Usage

```
/make-reel "the Halifax explosion 1917"
/make-reel "the last photograph of Tsar Nicholas II"
/make-reel "the woman who survived the sinking of the Lusitania"
```

The argument is the topic — a single sentence describing what the Reel should be about.

## What this skill does

Orchestrate six stages with three approval gates. Stop and ask Jude at each gate. Never skip a gate.

### Setup
1. Generate `slug` from topic (lowercase, kebab-case, drop articles).
2. Create working dir: `content/<YYYY-MM-DD>_<slug>/`.
3. Initialize `manifest.json` with `topic`, `created_at`, empty `assets`, empty `costs_usd`, empty `gates`.

### Stage 1 — Research
- Launch the `researcher` sub-agent with the topic.
- Wait for `content/<dir>/research.md`.

### Stage 2 — Script
- Launch the `scriptwriter` sub-agent.
- The scriptwriter reads `reference/formula.md`, `.claude/prompts/narration-style.md`, and `content/<dir>/research.md`.
- Wait for `content/<dir>/script.json`.

### ◆ GATE 1: Script approval
- Print the `tagged_script` and the `ending_pattern_name` to Jude.
- Run the hook self-check: print `hooks_avoided` and confirm the first sentence does not match any banned pattern.
- Ask Jude: `Approve script? [y / e=edit / n=reject]`
  - `y` → record `gates.script_approved_at = now()` in manifest; proceed
  - `e` → tell Jude to edit `script.json` directly, then re-run from Gate 1
  - `n` → re-launch `scriptwriter` with Jude's feedback as additional input; loop

### Stage 3 — Photo curation
- Launch the `photo-curator` sub-agent.
- It reads `script.json` and calls `.claude/scripts/archive_search.py` per anchor.
- Wait for `content/<dir>/shotlist_candidates.json`.
- If `status: insufficient` → stop and ask Jude how to proceed (drop topic, broaden anchors, defer to production-cut multi-archive search).

### ◆ GATE 2: Photo approval
- Download all candidate images to `content/<dir>/photos/raw/` (use `requests` or `curl`, write `image_url` content to disk).
- Print a table of candidates: `archive_id | title | date_raw | license_tag | dimensions | source_url`.
- Ask Jude: which `archive_id`s to use (comma-separated), in what order?
- Copy selected images from `photos/raw/` to `photos/approved/`, renamed by shot order (`shot_000_<archive_id>.jpg`).
- Record `gates.photos_approved_at = now()` in manifest.

### Stage 4 — Narration TTS
- Run: `python .claude/scripts/tts_generate.py --script content/<dir>/script.json --out content/<dir>/audio/narration.mp3`
- Read the returned stats. If `seam_regens > 0`, log it but continue.
- Update `manifest.json`:
  - `assets.audio.narration_engine = "elevenlabs_v3"`
  - `assets.audio.narration_voice_id = <voice_id>`
  - `costs_usd.elevenlabs_v3 += <estimate>`

### Stage 5 — Assembly
- Run: `python .claude/scripts/ken_burns_assemble.py --audio content/<dir>/audio/narration.mp3 --photos content/<dir>/photos/approved/ --out content/<dir>/silent.mp4`
- Run: `python .claude/scripts/subtitle_burn.py --audio content/<dir>/audio/narration.mp3 --video content/<dir>/silent.mp4 --out content/<dir>/final.mp4`

### ◆ GATE 3: Final approval
- Tell Jude the path: `open content/<dir>/final.mp4`.
- Ask Jude: `Approve for publication? [y / r=revise]`
  - `y` → record `gates.final_approved_at = now()` in manifest. Print upload instructions (Jude uploads to Instagram manually).
  - `r` → ask which gate to revise. Suggest using `/revise-reel --gate {script|photos|video}` (production cut).

### Cleanup
- Print summary: total cost from `manifest.json`, total time, path to `final.mp4`.
- Append to `reference/run-log.jsonl` (one line per run with `reel_id`, `cost_total`, `duration_sec`).

## Working directory layout (per Reel)

```
content/<YYYY-MM-DD>_<slug>/
├── research.md
├── script.json
├── shotlist_candidates.json
├── photos/
│   ├── raw/
│   └── approved/
├── audio/
│   └── narration.mp3
├── silent.mp4               # intermediate, can be cleaned up
├── final.mp4
└── manifest.json
```

## Rules

- **Never skip a gate.** Even if a previous Reel was great, ask every time.
- **Never auto-publish.** Output ends at `final.mp4` + upload instructions. Jude uploads.
- **Never invent photos.** If photo-curator returns insufficient candidates, stop and ask.
- **Log costs as you go.** Update `manifest.json` after every paid API call so a half-run still tells Jude what was spent.
- **If a run exceeds $10** (the production ceiling), halt and ask before continuing.
