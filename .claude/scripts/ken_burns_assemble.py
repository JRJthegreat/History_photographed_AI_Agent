#!/usr/bin/env python3
"""
ken_burns_assemble.py — 9:16 Reel assembly with Ken Burns motion.

Inputs:
    - audio narration (mp3)
    - directory of approved photos
    - optional shotlist.json (production cut) — see prompts/shotlist-schema.md

Without a shotlist (MVP default):
    - Audio duration is split evenly across photos
    - Each photo gets a slow zoom-in (1.00 → 1.10) over its dwell
    - 0.5s crossfade between shots

Output: 1080×1920 (9:16) silent video. Subtitles are burned in afterward by
subtitle_burn.py, which also muxes the audio.

Usage:
    python ken_burns_assemble.py \\
        --audio audio/narration.mp3 \\
        --photos photos/approved/ \\
        --out silent.mp4

    python ken_burns_assemble.py \\
        --audio audio/narration.mp3 \\
        --photos photos/approved/ \\
        --shotlist shotlist.json \\
        --out silent.mp4
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

TARGET_W = 1080
TARGET_H = 1920
FPS = 30
CROSSFADE_SEC = 0.5
DEFAULT_KEN_BURNS = {
    "type": "zoom_in",
    "start_scale": 1.00,
    "end_scale": 1.10,
    "focal_x": 0.5,
    "focal_y": 0.5,
}


def _audio_duration_sec(audio: Path) -> float:
    r = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def _build_default_shotlist(photos: list[Path], duration_sec: float) -> list[dict]:
    """Equal-dwell, zoom-in default when no shotlist.json is supplied."""
    n = len(photos)
    if n == 0:
        raise ValueError("No photos to assemble")
    # Equal dwell, but overlap by CROSSFADE_SEC on every cut
    overlap_total = CROSSFADE_SEC * (n - 1)
    visible = duration_sec + overlap_total
    dwell = visible / n
    shots = []
    for i, p in enumerate(photos):
        shots.append(
            {
                "index": i,
                "photo_path": str(p),
                "dwell_sec": dwell,
                "ken_burns": dict(DEFAULT_KEN_BURNS),
                "crossfade_out_sec": CROSSFADE_SEC if i < n - 1 else 0.0,
            }
        )
    return shots


def _zoompan_filter(shot: dict) -> str:
    """Build an FFmpeg zoompan filter expression for one shot.

    zoompan operates on a single input image stretched into a video segment.
    """
    dwell = float(shot["dwell_sec"])
    frames = max(int(round(dwell * FPS)), 1)
    kb = shot.get("ken_burns") or DEFAULT_KEN_BURNS
    start = float(kb.get("start_scale", 1.0))
    end = float(kb.get("end_scale", 1.1))
    if kb.get("type") == "zoom_out":
        start, end = max(start, end), min(start, end)
    # Linear interpolation across frames
    step = (end - start) / max(frames - 1, 1)
    z_expr = f"'{start}+{step}*on'"
    # Pan: keep focal point centered as we zoom
    fx = float(kb.get("focal_x", 0.5))
    fy = float(kb.get("focal_y", 0.5))
    x_expr = f"'iw*{fx}-(iw/zoom/2)'"
    y_expr = f"'ih*{fy}-(ih/zoom/2)'"
    return (
        f"scale=8000:-1,"
        f"zoompan=z={z_expr}:x={x_expr}:y={y_expr}:"
        f"d={frames}:s={TARGET_W}x{TARGET_H}:fps={FPS}"
    )


def _render_shot(shot: dict, out_path: Path) -> None:
    """Render a single photo into a Ken-Burns video segment."""
    zp = _zoompan_filter(shot)
    filter_complex = (
        f"[0:v]scale=w='if(gt(a,9/16),-2,{TARGET_W})':h='if(gt(a,9/16),{TARGET_H},-2)',"
        f"crop={TARGET_W}:{TARGET_H},{zp}[v]"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", str(FPS),
            "-i", shot["photo_path"],
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-t", str(shot["dwell_sec"]),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
            str(out_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def _render_video_clip(shot: dict, out_path: Path) -> None:
    """Convert an archival video clip to 9:16 MP4, trimmed to dwell_sec.

    Handles 640x480 (4:3) archival webm by cover-cropping to 9:16 with a
    slight slow-motion effect (0.9x speed) for gravitas, plus a slight
    zoom-in to hide the black edges from the 4:3 → 9:16 crop.
    """
    dwell = float(shot["dwell_sec"])
    clip_path = shot["clip_path"]
    # trim_start lets you pick which part of a long archival clip to use
    trim_start = float(shot.get("trim_start", 0.0))

    # Scale to cover 9:16 (archival 4:3 needs pillarbox removal via crop)
    # 640×480 → scale height to 1920 → width = 2560 → crop center 1080
    filter_v = (
        f"[0:v]trim=start={trim_start}:duration={dwell},"
        f"setpts=PTS-STARTPTS,"
        f"scale=-2:{TARGET_H},"
        f"crop={TARGET_W}:{TARGET_H},"
        f"zoompan=z='1.05+0.001*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={int(dwell*FPS)}:s={TARGET_W}x{TARGET_H}:fps={FPS}[v]"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(clip_path),
            "-filter_complex", filter_v,
            "-map", "[v]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
            str(out_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def _crossfade_concat(segments: list[Path], crossfade_sec: float, out_path: Path) -> None:
    """Concatenate segments with xfade transitions."""
    if len(segments) == 1:
        out_path.write_bytes(segments[0].read_bytes())
        return

    inputs: list[str] = []
    for s in segments:
        inputs.extend(["-i", str(s)])

    # Build cumulative xfade graph
    durations: list[float] = []
    for s in segments:
        r = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(s),
            ],
            capture_output=True, text=True, check=True,
        )
        durations.append(float(r.stdout.strip()))

    filter_parts: list[str] = []
    prev_label = "0:v"
    offset = durations[0] - crossfade_sec
    for i in range(1, len(segments)):
        out_label = f"v{i}"
        filter_parts.append(
            f"[{prev_label}][{i}:v]xfade=transition=fade:duration={crossfade_sec}:"
            f"offset={offset:.3f}[{out_label}]"
        )
        prev_label = out_label
        offset += durations[i] - crossfade_sec

    filter_complex = ";".join(filter_parts)
    subprocess.run(
        [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{prev_label}]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
            str(out_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def _mux_audio(video_in: Path, audio: Path, duration_sec: float, out_path: Path) -> None:
    """Mux narration audio onto the silent video, truncating to audio length."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_in),
            "-i", str(audio),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-t", f"{duration_sec:.3f}",
            str(out_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def assemble(audio: Path, photo_dir: Path, out: Path, shotlist_path: Path | None) -> dict:
    photos = sorted(
        [p for p in photo_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    )
    if not photos:
        raise ValueError(f"No photos found in {photo_dir}")

    duration_sec = _audio_duration_sec(audio)

    if shotlist_path and shotlist_path.exists():
        shotlist = json.loads(shotlist_path.read_text())
        shots = shotlist["shots"]
        for s in shots:
            if "dwell_sec" not in s:
                s["dwell_sec"] = float(s["out_sec"]) - float(s["in_sec"])
    else:
        shots = _build_default_shotlist(photos, duration_sec)

    workdir = out.parent / ".cache" / out.stem
    workdir.mkdir(parents=True, exist_ok=True)

    segments: list[Path] = []
    for shot in shots:
        seg = workdir / f"shot_{shot['index']:03d}.mp4"
        if shot.get("clip_path"):
            _render_video_clip(shot, seg)
        else:
            _render_shot(shot, seg)
        segments.append(seg)

    silent = workdir / "silent_concat.mp4"
    _crossfade_concat(segments, CROSSFADE_SEC, silent)

    _mux_audio(silent, audio, duration_sec, out)

    return {
        "output": str(out),
        "duration_sec": duration_sec,
        "shots": len(shots),
        "photos_used": [str(p) for p in photos[: len(shots)]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble a 9:16 Reel from photos + narration")
    parser.add_argument("--audio", required=True, help="Narration MP3")
    parser.add_argument("--photos", required=True, help="Directory of approved photos")
    parser.add_argument("--shotlist", help="Optional shotlist.json")
    parser.add_argument("--out", required=True, help="Output MP4")
    args = parser.parse_args()

    stats = assemble(
        Path(args.audio),
        Path(args.photos),
        Path(args.out),
        Path(args.shotlist) if args.shotlist else None,
    )
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
