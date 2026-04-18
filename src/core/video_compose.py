"""Compose a single video chapter from image + audio + optional subtitle.

Extracted from tools/text2video/text2video.py AudioVideoApp._build_chapter_cmd().
"""

from __future__ import annotations

import os
import subprocess

from core.srt_from_text import get_audio_duration
from core.subtitle_ops import escape_ffmpeg_path


def compose_chapter(
    image: str,
    audio: str,
    srt: str | None,
    output: str,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    codec: str = "libx264",
    bg_color: str = "000000",
) -> None:
    """Compose one chapter: static image + audio + optional burned-in subtitle.

    The image is scaled to fit width x height (letterboxed), looped for the
    duration of the audio track, and encoded with the subtitle overlay.
    """
    duration = get_audio_duration(audio)
    if duration <= 0:
        raise RuntimeError(f"Cannot read audio duration: {audio}")

    scale_pad = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#{bg_color}"
    )

    vf_parts = [scale_pad]
    if srt and os.path.isfile(srt):
        srt_ff = escape_ffmpeg_path(srt)
        style = "FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,MarginV=30"
        vf_parts.append(f"subtitles='{srt_ff}':force_style='{style}'")

    cmd = [
        "ffmpeg",
        "-loop", "1", "-t", str(duration), "-i", image,
        "-i", audio,
        "-vf", ",".join(vf_parts),
        "-map", "0:v", "-map", "1:a",
        "-c:v", codec, "-c:a", "aac", "-b:a", "192k",
        "-r", str(fps), "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-shortest",
        "-y", output,
    ]

    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")
