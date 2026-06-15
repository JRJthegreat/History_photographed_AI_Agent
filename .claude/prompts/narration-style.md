# Narration Style — Reusable Fragment

Append this to any agent prompt that produces narration text.

## Voice

A quiet, measured, present-tense documentary voice. Restrained. Never sentimental. Lets the facts do the emotional work. Think of a museum docent who has read the diary three times and decided which one sentence to read aloud.

## Mechanics

- Lean short: median sentence ≤ 12 words
- Allow single-word sentences for impact
- Em-dashes for pivots, ellipses sparingly
- Present tense for what's in the photo, past tense for what happened
- Concrete nouns over abstractions
- One paragraph per narrative beat (paragraph breaks become TTS chunk boundaries)

## ElevenLabs v3 audio tags

Insert at most one tag per beat. Available tags include `[whispers]`, `[softly]`, `[firmly]`, `[warmly]`, `[pause]`, `[sighs]`, `[excited]`. Default to `[softly]` for death reveals and closing lines; `[pause]` before number/date reveals; `[firmly]` for defiance.

## Pronunciation overrides

Output a parallel `pronunciation_overrides` list for every non-English name, place, or term where TTS will likely mangle: `[{ "word": "Atget", "phonetic": "at-ZHAY" }, ...]`. The TTS layer respells these phonetically before sending to ElevenLabs.

## What to avoid

- ❌ Greetings, sign-offs, host-presence
- ❌ "Did you know…", "Have you ever…"
- ❌ Modern psychological vocabulary in pre-1950 stories
- ❌ Journalistic clichés ("shocking", "incredible")
- ❌ Hashtags, follow CTAs, lessons / morals in the closing line
