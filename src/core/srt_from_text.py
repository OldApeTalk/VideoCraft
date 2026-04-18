"""Generate SRT subtitles from text + audio using character-ratio timing.

Extracted from tools/text2video/text2video.py SRTFromTextApp.
UI layer calls generate_srt_from_text(); this module has no Tk dependency.
"""

from __future__ import annotations

import os
import re
import subprocess


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds via ffprobe."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
            capture_output=True, encoding="utf-8", errors="replace", check=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def split_text_to_segments(raw: str, max_chars: int = 30) -> list[str]:
    """Split text into subtitle segments, stripping role prefixes."""
    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^.{1,15}[：:](.+)', line)
        if m:
            line = m.group(1).strip()
        sentences = re.split(r'(?<=[。！？!?\.…])', line)
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            while len(s) > max_chars:
                lines.append(s[:max_chars])
                s = s[max_chars:]
            if s:
                lines.append(s)
    return [l for l in lines if l]


def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt_content(
    segments: list[str],
    total_duration: float,
    gap: float = 0.3,
) -> str:
    """Build SRT string with timestamps proportional to character count."""
    if not segments:
        return ""
    total_chars = sum(len(s) for s in segments)
    total_gap = gap * (len(segments) - 1)
    speech_time = max(total_duration - total_gap, total_duration * 0.8)

    srt_lines: list[str] = []
    cursor = 0.0
    for i, seg in enumerate(segments):
        seg_dur = (len(seg) / total_chars) * speech_time
        start = cursor
        end = cursor + seg_dur
        srt_lines.append(f"{i+1}")
        srt_lines.append(f"{_fmt_time(start)} --> {_fmt_time(end)}")
        srt_lines.append(seg)
        srt_lines.append("")
        cursor = end + gap
    return "\n".join(srt_lines)


def generate_srt_from_text(
    text: str,
    audio_path: str,
    srt_path: str,
    *,
    max_chars: int = 30,
    gap: float = 0.3,
) -> None:
    """Generate an SRT subtitle file from text and audio duration.

    Splits text into segments, reads audio duration via ffprobe,
    then assigns timestamps proportional to character count.
    """
    duration = get_audio_duration(audio_path)
    if duration <= 0:
        raise RuntimeError(f"Cannot read audio duration: {audio_path}")

    segments = split_text_to_segments(text, max_chars)
    if not segments:
        raise RuntimeError("No text segments to generate subtitles from")

    srt_content = build_srt_content(segments, duration, gap)

    os.makedirs(os.path.dirname(srt_path) or ".", exist_ok=True)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
