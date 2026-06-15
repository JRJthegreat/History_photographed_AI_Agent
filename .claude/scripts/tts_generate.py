#!/usr/bin/env python3
"""
tts_generate.py — ElevenLabs v3 narration with paragraph chunking + seam stitching.

Solves three quality problems verified in the research phase:
1. v3 has a 3,000-char per-generation limit → chunk on paragraph boundaries.
2. Naive concatenation produces audible prosody breaks → pass `previous_text`
   (last ~300 chars of prior chunk) so v3 conditions on prior prosody.
3. Historical names mangle in TTS → respell phonetically before the call using
   `pronunciation_overrides` from the scriptwriter.

Usage:
    python tts_generate.py --script script.json --out audio/narration.mp3
    python tts_generate.py --text "Test. [whispers] Quiet one." --out /tmp/t.mp3

`script.json` shape (from scriptwriter agent):
    {
      "tagged_script": "Para 1...\\n\\nPara 2...",
      "pronunciation_overrides": [{"word": "Atget", "phonetic": "at-ZHAY"}],
      "voice_id": "..."           # optional; defaults to ELEVENLABS_DEFAULT_VOICE
    }
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv

ELEVENLABS_API = "https://api.elevenlabs.io/v1"
MODEL_ID = "eleven_v3"
CHUNK_CHAR_CEILING = 2800  # safety margin under 3000
PREVIOUS_TEXT_TAIL = 300
SEAM_GAP_THRESHOLD_MS = 400



def _apply_pronunciation_overrides(text: str, overrides: list[dict]) -> str:
    """Respell overridden words phonetically (case-insensitive, word-boundary)."""
    for o in overrides:
        word = o["word"]
        phonetic = o["phonetic"]
        text = re.sub(
            rf"\b{re.escape(word)}\b", phonetic, text, flags=re.IGNORECASE
        )
    return text


def _chunk_on_paragraphs(text: str, ceiling: int = CHUNK_CHAR_CEILING) -> list[str]:
    """Split into chunks ≤ ceiling chars, breaking only on paragraph boundaries.

    Falls back to sentence boundary only if a single paragraph exceeds the ceiling.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        candidate = f"{buf}\n\n{p}" if buf else p
        if len(candidate) <= ceiling:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        if len(p) <= ceiling:
            buf = p
            continue
        # Single oversized paragraph — split on sentences as a last resort.
        sentences = re.split(r"(?<=[.!?])\s+", p)
        sbuf = ""
        for s in sentences:
            cand = f"{sbuf} {s}".strip() if sbuf else s
            if len(cand) <= ceiling:
                sbuf = cand
            else:
                if sbuf:
                    chunks.append(sbuf)
                sbuf = s
        if sbuf:
            buf = sbuf
    if buf:
        chunks.append(buf)
    return chunks


def _synthesize_chunk(
    text: str,
    voice_id: str,
    api_key: str,
    previous_text: str = "",
) -> bytes:
    """Call ElevenLabs v3 TTS for one chunk, returning MP3 bytes."""
    url = f"{ELEVENLABS_API}/text-to-speech/{voice_id}"
    payload = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }
    if previous_text:
        payload["previous_text"] = previous_text[-PREVIOUS_TEXT_TAIL:]

    r = requests.post(
        url,
        headers={
            "xi-api-key": api_key,
            "accept": "audio/mpeg",
            "content-type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs TTS failed [{r.status_code}]: {r.text}")
    return r.content


def _concat_mp3s(chunk_paths: list[Path], out_path: Path) -> None:
    """Concatenate MP3 chunks losslessly via FFmpeg concat demuxer."""
    if len(chunk_paths) == 1:
        out_path.write_bytes(chunk_paths[0].read_bytes())
        return
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for cp in chunk_paths:
            f.write(f"file '{cp.resolve()}'\n")
        listfile = f.name
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", listfile, "-c", "copy", str(out_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    finally:
        os.unlink(listfile)


def _seam_gap_ms(mp3_a: Path, mp3_b: Path) -> int:
    """Return the silence gap (ms) at the seam between two MP3s.

    Computes trailing silence of A + leading silence of B using ffmpeg silencedetect.
    """
    def trailing_silence(p: Path) -> float:
        result = subprocess.run(
            ["ffmpeg", "-i", str(p),
             "-af", "silencedetect=noise=-40dB:d=0.1",
             "-f", "null", "-"],
            capture_output=True, text=True,
        )
        # Parse the LAST "silence_start" / "silence_end" near the end.
        lines = result.stderr.splitlines()
        last_start = None
        for line in reversed(lines):
            if "silence_start" in line:
                try:
                    last_start = float(line.split("silence_start:")[1].strip().split()[0])
                except (IndexError, ValueError):
                    pass
                break
        # Duration of file
        dur_result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
            capture_output=True, text=True,
        )
        try:
            dur = float(dur_result.stdout.strip())
        except ValueError:
            return 0.0
        return max(0.0, dur - last_start) if last_start is not None else 0.0

    def leading_silence(p: Path) -> float:
        result = subprocess.run(
            ["ffmpeg", "-i", str(p),
             "-af", "silencedetect=noise=-40dB:d=0.1",
             "-f", "null", "-"],
            capture_output=True, text=True,
        )
        for line in result.stderr.splitlines():
            if "silence_start" in line and "silence_start: 0" in line.replace(" ", ""):
                for line2 in result.stderr.splitlines():
                    if "silence_end" in line2:
                        try:
                            return float(line2.split("silence_end:")[1].strip().split()[0])
                        except (IndexError, ValueError):
                            return 0.0
        return 0.0

    return int((trailing_silence(mp3_a) + leading_silence(mp3_b)) * 1000)


def generate(
    tagged_script: str,
    out_path: Path,
    voice_id: str,
    api_key: str,
    pronunciation_overrides: list[dict] | None = None,
) -> dict:
    """Generate stitched narration MP3. Returns a stats dict."""
    overrides = pronunciation_overrides or []
    prepared = _apply_pronunciation_overrides(tagged_script, overrides)
    chunks = _chunk_on_paragraphs(prepared)
    if not chunks:
        raise ValueError("Empty script after preparation")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_paths: list[Path] = []
    workdir = Path(tempfile.mkdtemp(prefix="tts_"))
    seam_regens = 0

    for i, chunk in enumerate(chunks):
        prev = chunks[i - 1] if i > 0 else ""
        audio = _synthesize_chunk(chunk, voice_id, api_key, previous_text=prev)
        cp = workdir / f"chunk_{i:03d}.mp3"
        cp.write_bytes(audio)
        chunk_paths.append(cp)

        if i > 0:
            gap_ms = _seam_gap_ms(chunk_paths[i - 1], cp)
            if gap_ms > SEAM_GAP_THRESHOLD_MS:
                extended_prev = (chunks[i - 1] + " " + chunk[: PREVIOUS_TEXT_TAIL // 2])
                audio = _synthesize_chunk(
                    chunk, voice_id, api_key, previous_text=extended_prev
                )
                cp.write_bytes(audio)
                seam_regens += 1

    _concat_mp3s(chunk_paths, out_path)
    return {
        "chunks": len(chunks),
        "seam_regens": seam_regens,
        "output": str(out_path),
        "voice_id": voice_id,
        "model": MODEL_ID,
    }


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    parser = argparse.ArgumentParser(description="Generate TTS narration via ElevenLabs v3")
    parser.add_argument("--script", help="Path to script.json")
    parser.add_argument("--text", help="Raw tagged text (skips script.json loading)")
    parser.add_argument("--out", required=True, help="Output MP3 path")
    parser.add_argument("--voice", help="Override voice_id")
    args = parser.parse_args()

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY not set in .env", file=sys.stderr)
        return 2

    default_voice = os.getenv("ELEVENLABS_DEFAULT_VOICE", "")

    if args.text:
        tagged_script = args.text
        overrides: list[dict] = []
        voice_id = args.voice or default_voice
    elif args.script:
        data = json.loads(Path(args.script).read_text())
        tagged_script = data["tagged_script"]
        overrides = data.get("pronunciation_overrides", [])
        voice_id = args.voice or data.get("voice_id") or default_voice
    else:
        print("ERROR: Pass either --script or --text", file=sys.stderr)
        return 2

    if not voice_id:
        print(
            "ERROR: No voice_id. Set ELEVENLABS_DEFAULT_VOICE in .env, pass --voice, "
            "or include voice_id in script.json",
            file=sys.stderr,
        )
        return 2

    stats = generate(
        tagged_script,
        Path(args.out),
        voice_id=voice_id,
        api_key=api_key,
        pronunciation_overrides=overrides,
    )
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
