# History Photographed — AI Reel Pipeline

An AI-orchestrated pipeline that takes a historical topic and produces a publish-ready Instagram Reel (9:16, 30–90s) in the storytelling style of [@historyphotographed](https://instagram.com/historyphotographed).

Built with Claude Code, ElevenLabs v3, and real public-domain archival footage.

---

## What it does

You type a topic. The system:

1. **Researches** the story — verified facts, primary sources, no hallucination
2. **Writes a script** — in the page's empirically-derived style (hooks, cadence, DM-shareable endings)
3. **You approve the script** ← Gate 1
4. **Finds photos** — public-domain archives only (Wikimedia Commons, Library of Congress, NARA, Europeana)
5. **You approve the photos** ← Gate 2
6. **Narrates** — ElevenLabs v3 with emotion tags (`[whispers]`, `[softly]`, `[pause]`)
7. **Assembles** — 9:16 Ken Burns video with real archival footage where available
8. **Burns captions** — Whisper word-level alignment, 2–3 word cards
9. **You approve the final video** ← Gate 3

Output: a finished MP4 ready to upload to Instagram. Nothing auto-publishes.

---

## Example output

**Topic:** "The Halifax explosion 1917 — Vince Coleman's last telegram"

> *Halifax, December sixth, 1917. The harbor is on fire.*
>
> *Thousands of people stop to watch. They press their faces to windows.*
>
> *A telegraph operator named Vince Coleman knows. He goes back. Alone.*
>
> *Hold up the train. Ammunition ship afire in harbor. Guess this will be my last message. Good-bye boys.*
>
> *Twenty seconds later, two thousand tons of TNT detonate. The largest man-made explosion in history until Hiroshima.*
>
> *Eighteen hundred die. Three hundred live. He never knows.*

86 seconds. 5 public-domain photos + 4 real W.G. MacLaughlan 1917 archival film clips. All verifiable, all licensed.

---

## How to use it

### 1. Clone and install

```bash
git clone https://github.com/yourusername/history-photographed-ai-agent
cd History_photographed_AI_Agent

brew install ffmpeg
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Set up API keys

```bash
cp .env.example .env
```

Edit `.env`:

```
ANTHROPIC_API_KEY=       # Claude orchestration
ELEVENLABS_API_KEY=      # TTS narration
ELEVENLABS_DEFAULT_VOICE=pNInz6obpgDQGcFmaJgB   # Adam (free tier)
APIFY_API_TOKEN=         # Instagram scraping for /analyze-formula
```

### 3. Run

```bash
/make-reel "the Halifax explosion 1917"
```

The skill walks you through three approval gates. Each one stops and asks before spending money or rendering video.

### 4. (Optional) Extract the storytelling formula

Run once to scrape @historyphotographed's top Reels via Apify and derive empirical hook patterns, cadence, and ending styles:

```bash
/analyze-formula
```

This populates `reference/formula.md`, which the scriptwriter loads as its system prompt.

---

## Project structure

```
.claude/
├── agents/
│   ├── researcher.md          # Fact-checks via Wikipedia + primary sources
│   ├── scriptwriter.md        # Writes Reel script using formula.md
│   ├── photo-curator.md       # Searches public-domain archives
│   ├── formula-analyst.md     # Extracts viral patterns from corpus
│   ├── shotlist-director.md   # Maps photos/clips to narration timing
│   └── qc-reviewer.md         # Adversarial fact + tone + IP check
├── skills/
│   ├── make-reel/             # /make-reel "topic"
│   ├── analyze-formula/       # /analyze-formula
│   └── revise-reel/           # /revise-reel --gate {script|photos|video}
├── scripts/
│   ├── archive_search.py      # Wikimedia / LoC / Europeana / NARA search
│   ├── tts_generate.py        # ElevenLabs v3 with chunking + seam stitching
│   ├── ken_burns_assemble.py  # 9:16 video assembly (photos + archival clips)
│   └── subtitle_burn.py       # Whisper alignment + caption burn-in
└── prompts/
    ├── narration-style.md
    └── shotlist-schema.md

reference/
├── formula.md                 # Extracted storytelling formula (10 sections)
└── top-reels.json             # Apify scrape output

content/
└── YYYY-MM-DD_slug/           # Per-Reel working dir
    ├── research.md
    ├── script.json
    ├── shotlist_candidates.json
    ├── photos/approved/
    ├── video/                 # Archival film clips (webm)
    ├── audio/narration.mp3
    ├── final.mp4
    └── manifest.json          # Full provenance trail + costs
```

---

## Cost

| Item | Per Reel |
|---|---|
| Claude orchestration | ~$1.10 |
| ElevenLabs v3 narration | ~$0.16 |
| Whisper transcription | ~$0.01 |
| Archive APIs (Wikimedia, LoC, NARA) | Free |
| Archival footage (Wikimedia) | Free |
| FFmpeg render (local) | Free |
| **Total** | **~$1.30 MVP / ~$3–5 production** |

---

## Hard rules

1. **Public domain only.** No licensed stock, no AI-generated fake historical photos.
2. **No fabricated history.** Every claim in the script is cited in `research.md`.
3. **No influencer cloning.** TTS only — ElevenLabs v3 primary, Hume Octave for drama, OpenAI gpt-4o-mini-tts as budget fallback.
4. **Three gates always.** The system never publishes anything. You approve script, photos, and final video before anything gets uploaded.
5. **Cost ceiling $10/Reel.** If a run is about to exceed this, it halts and asks.

---

## Stack

| Layer | Tool |
|---|---|
| Orchestration | Claude Opus 4.7 (via Claude Code) |
| Sub-agents | Claude Sonnet 4.6 |
| TTS | ElevenLabs v3 (primary), Hume Octave (drama), OpenAI gpt-4o-mini-tts (budget) |
| Transcription | faster-whisper (local, no API cost) |
| Photo archives | Wikimedia Commons, Library of Congress, Europeana, NARA |
| Video assembly | FFmpeg + moviepy |
| Instagram scraping | Apify Instagram Reel Analyzer |
| Colorization | Topaz Labs (production cut) |

---

## Roadmap

**MVP (built)**
- [x] Wikimedia Commons archive search
- [x] ElevenLabs v3 narration with chunk stitching + pronunciation overrides
- [x] Ken Burns photo assembly (9:16, crossfades)
- [x] Real archival video clip support (mixed photo + footage)
- [x] Whisper caption burn-in
- [x] Three approval gates

**Production cut (next)**
- [ ] `/analyze-formula` — Apify scrape → empirical formula extraction
- [ ] Multi-archive search (LoC, Europeana, NARA, Getty Open Content)
- [ ] Topaz photo colorization
- [ ] `qc-reviewer` adversarial pass at all three gates
- [ ] `/revise-reel --gate` re-entry
- [ ] Music bed (Epidemic Sound)
- [ ] Hume Octave / OpenAI TTS fallbacks

---

## License

Code: MIT

Content produced by the pipeline: all photos and footage are public domain. Scripts and narration are original works. Always verify license tags in `manifest.json` before publishing.
