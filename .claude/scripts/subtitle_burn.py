#!/usr/bin/env python3
"""
subtitle_burn.py — Whisper word-level alignment → burned-in 2-3 word cards.

Uses faster-whisper (or openai-whisper as fallback) to get word-level timestamps,
groups them into 2-3 word cards, and burns them into the bottom third of a 9:16
video via FFmpeg's `drawtext` filter.

Usage:
    # Alignment only (no video) — useful for shotlist-director
    python subtitle_burn.py --audio audio/narration.mp3 --align-only --out words.json

    # Burn captions onto a video
    python subtitle_burn.py --audio audio/narration.mp3 --video silent.mp4 --out captioned.mp4
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WORDS_PER_CARD = 3
FONT_SIZE = 110
FONT_COLOR = "white"
SHADOW_COLOR = "black"
BOTTOM_THIRD_Y = "h*0.72"


def transcribe_word_level(audio_path: Path) -> list[dict]:
    """Return list of {word, start, end} dicts.

    Prefers faster-whisper for speed. Falls back to openai-whisper if absent.
    """
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _info = model.transcribe(
            str(audio_path), word_timestamps=True, language="en"
        )
        words = []
        for seg in segments:
            for w in seg.words or []:
                words.append({"word": w.word.strip(), "start": float(w.start), "end": float(w.end)})
        return words
    except ImportError:
        pass

    try:
        import whisper

        model = whisper.load_model("base")
        result = model.transcribe(str(audio_path), word_timestamps=True, language="en")
        words = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                words.append(
                    {"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])}
                )
        return words
    except ImportError as e:
        raise RuntimeError(
            "Neither faster-whisper nor openai-whisper is installed. "
            "Run: pip install faster-whisper"
        ) from e


def group_into_cards(words: list[dict], per_card: int = WORDS_PER_CARD) -> list[dict]:
    """Group word timestamps into 2-3 word caption cards."""
    cards: list[dict] = []
    i = 0
    while i < len(words):
        chunk = words[i : i + per_card]
        if not chunk:
            break
        text = " ".join(w["word"] for w in chunk).strip()
        cards.append(
            {
                "text": text,
                "start": chunk[0]["start"],
                "end": chunk[-1]["end"],
            }
        )
        i += per_card
    return cards


def _seconds_to_ass_time(sec: float) -> str:
    """0:00:00.00 format for ASS files."""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _write_ass(cards: list[dict], out_path: Path, video_w: int = 1080, video_h: int = 1920) -> None:
    """Write an ASS subtitle file with caption cards positioned in the bottom third."""
    # Position cards at vertical center of the bottom third (~72% down)
    margin_v = int(video_h * 0.28)  # margin from BOTTOM
    header = (
        "[Script Info]\n"
        f"PlayResX: {video_w}\nPlayResY: {video_h}\n"
        "ScaledBorderAndShadow: yes\nWrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial Black,{FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        f"-1,0,0,0,100,100,0,0,1,8,4,2,80,80,{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = [header]
    for card in cards:
        start = _seconds_to_ass_time(card["start"])
        end = _seconds_to_ass_time(card["end"])
        text = card["text"].replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")
    out_path.write_text("".join(lines))


def burn_captions(video_in: Path, words: list[dict], video_out: Path) -> None:
    """Burn caption cards into a video by rendering an ASS subtitle file."""
    cards = group_into_cards(words)
    if not cards:
        raise ValueError("No words to burn")

    video_out.parent.mkdir(parents=True, exist_ok=True)
    ass_path = video_out.with_suffix(".ass")
    _write_ass(cards, ass_path)

    # Run FFmpeg from the parent of the ASS file with a basename-only path.
    # The subtitles filter chokes on certain characters in paths (dashes parsed
    # as options, colons as option separators) — staying in cwd avoids all that.
    workdir = ass_path.parent.resolve()
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_in.resolve()),
            "-vf", f"subtitles={ass_path.name}",
            "-c:a", "copy",
            "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            str(video_out.resolve()),
        ],
        check=True,
        cwd=str(workdir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Word-level alignment + caption burn-in")
    parser.add_argument("--audio", required=True, help="Narration MP3")
    parser.add_argument("--align-only", action="store_true", help="Emit word JSON, no video")
    parser.add_argument("--video", help="Input video (required unless --align-only)")
    parser.add_argument("--out", required=True, help="Output path")
    args = parser.parse_args()

    words = transcribe_word_level(Path(args.audio))

    if args.align_only:
        Path(args.out).write_text(json.dumps(words, indent=2))
        print(f"Wrote {len(words)} word-timestamps to {args.out}")
        return 0

    if not args.video:
        print("ERROR: --video required unless --align-only", file=sys.stderr)
        return 2

    burn_captions(Path(args.video), words, Path(args.out))
    print(f"Burned {len(words)} words ({len(group_into_cards(words))} cards) → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
