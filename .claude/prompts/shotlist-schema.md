# Shotlist Schemas

## `shotlist_candidates.json` (photo-curator output → Gate 2)

```json
{
  "topic": "the Halifax explosion 1917",
  "candidates": [
    {
      "id": "halifax-001",
      "source": "wikimedia",
      "source_url": "https://commons.wikimedia.org/wiki/File:Halifax_Explosion_aftermath_LOC_3a52689u.jpg",
      "archive_id": "LOC_3a52689u",
      "title": "Halifax Explosion aftermath, view from Fort Needham",
      "creator": "unknown",
      "recorded_date_raw": "1917-12-06",
      "date_confidence": "high",
      "date_confidence_reason": "Wikimedia Information template + LoC catalog entry both specify the date",
      "license_tag": "PD-US",
      "license_url": "https://en.wikipedia.org/wiki/Public_domain_in_the_United_States",
      "image_url": "https://upload.wikimedia.org/.../Halifax_Explosion_aftermath_LOC_3a52689u.jpg",
      "dimensions": [2400, 1800],
      "is_natively_color": false,
      "suggested_use": "establish destruction scale after the reversal beat",
      "notes": "wide aftermath shot — pan-left works"
    }
  ]
}
```

**Rules:**
- `license_tag` must be in the allow-list: `PD-US`, `PD-1923`, `PD-Art`, `PD-old`, `CC0`, `NoKnownCopyrightRestrictions`. Reject anything else at this stage.
- `date_confidence` is `high|medium|low` and **must** include `date_confidence_reason` (one sentence).
- `recorded_date_raw` is the archive's date string verbatim. Do NOT normalize or guess.
- `is_natively_color` triggers Topaz skip in the production cut.

## `shotlist.json` (shotlist-director output → assembler input, production cut)

```json
{
  "topic": "the Halifax explosion 1917",
  "duration_sec": 58.4,
  "aspect_ratio": "9:16",
  "shots": [
    {
      "index": 0,
      "photo_id": "halifax-001",
      "photo_path": "photos/approved/halifax-001.jpg",
      "in_sec": 0.0,
      "out_sec": 8.2,
      "ken_burns": {
        "type": "zoom_in",
        "start_scale": 1.00,
        "end_scale": 1.18,
        "focal_x": 0.50,
        "focal_y": 0.50
      },
      "crossfade_in_sec": 0.0,
      "crossfade_out_sec": 0.5,
      "narration_lines": [0, 1]
    }
  ],
  "subtitles": {
    "burn_in": true,
    "position": "bottom_third",
    "style": "white_sans_serif_with_drop_shadow",
    "max_words_per_card": 3
  },
  "music": null
}
```

**MVP default behavior (if no `shotlist.json` exists):**
- Split `duration_sec` evenly across approved photos
- `ken_burns.type` = `zoom_in`, `start_scale` 1.00 → `end_scale` 1.10
- `crossfade_*_sec` = 0.5
- No music bed

## `manifest.json` (provenance trail, written by make-reel skill)

```json
{
  "reel_id": "2026-06-15_halifax-explosion-1917",
  "topic": "the Halifax explosion 1917",
  "created_at": "2026-06-15T03:42:00Z",
  "duration_sec": 58.4,
  "assets": {
    "photos": [
      { "photo_id": "halifax-001", "source_url": "...", "license_tag": "PD-US" }
    ],
    "audio": {
      "narration_engine": "elevenlabs_v3",
      "narration_voice_id": "...",
      "music_source": null,
      "music_license": null
    }
  },
  "costs_usd": {
    "claude_orchestration": 1.07,
    "elevenlabs_v3": 0.16,
    "whisper_transcription": 0.01,
    "topaz_colorize": 0.00,
    "total": 1.24
  },
  "gates": {
    "script_approved_at": "2026-06-15T03:48:00Z",
    "photos_approved_at": "2026-06-15T03:55:00Z",
    "final_approved_at": "2026-06-15T04:05:00Z"
  }
}
```
