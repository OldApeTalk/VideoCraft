"""
Segment model for the split workbench.

A Segment is just a (start_sec, title) pair. The end of a segment is implicit:
either the next segment's start or the video's total duration. This matches
the `subs.txt` format produced by the AI segment generator.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


_TIME_RE = re.compile(r"^(\d{1,3}):(\d{2})(?::(\d{2}))?$")


@dataclass
class Segment:
    start_sec: float
    title: str


def parse_timestamp(text: str) -> float | None:
    """Parse 'mm:ss' or 'hh:mm:ss' into seconds. Return None if invalid."""
    if not text:
        return None
    m = _TIME_RE.match(text.strip())
    if not m:
        return None
    a, b, c = m.groups()
    if c is None:
        mm, ss = int(a), int(b)
        if ss >= 60:
            return None
        return float(mm * 60 + ss)
    hh, mm, ss = int(a), int(b), int(c)
    if mm >= 60 or ss >= 60:
        return None
    return float(hh * 3600 + mm * 60 + ss)


def format_timestamp(seconds: float) -> str:
    """Format seconds as 'hh:mm:ss' (integer seconds)."""
    s = max(0, int(round(seconds)))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def load_from_file(path: str) -> list[Segment]:
    """Read a subs.txt-style file into a list of Segments.

    Each non-empty line is expected to start with a timestamp followed by a
    title. Lines that don't start with a valid timestamp are ignored.
    """
    segments: list[Segment] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if not parts:
                continue
            ts = parse_timestamp(parts[0])
            if ts is None:
                continue
            title = parts[1].strip() if len(parts) > 1 else ""
            segments.append(Segment(start_sec=ts, title=title))
    segments.sort(key=lambda s: s.start_sec)
    return segments


def save_to_file(path: str, segments: list[Segment]) -> None:
    """Write segments back in 'hh:mm:ss title' format, one per line."""
    ordered = sorted(segments, key=lambda s: s.start_sec)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for seg in ordered:
            f.write(f"{format_timestamp(seg.start_sec)} {seg.title}\n")


def end_of(segments: list[Segment], idx: int, video_duration: float) -> float:
    """Return the implicit end time of segments[idx]."""
    if idx + 1 < len(segments):
        return segments[idx + 1].start_sec
    return video_duration


def duration_of(segments: list[Segment], idx: int, video_duration: float) -> float:
    return max(0.0, end_of(segments, idx, video_duration) - segments[idx].start_sec)


def validate(segments: list[Segment], video_duration: float) -> list[str]:
    """Return a list of human-readable issues. Empty list = OK."""
    issues: list[str] = []
    if not segments:
        issues.append("empty")
        return issues
    for i, seg in enumerate(segments):
        if seg.start_sec < 0:
            issues.append(f"#{i + 1} negative start")
        if video_duration > 0 and seg.start_sec >= video_duration:
            issues.append(f"#{i + 1} start beyond video length")
        if not seg.title.strip():
            issues.append(f"#{i + 1} empty title")
        if i + 1 < len(segments) and seg.start_sec >= segments[i + 1].start_sec:
            issues.append(f"#{i + 1} start >= next segment start")
    return issues


def safe_filename(title: str) -> str:
    """Strip characters that are invalid in file names on Windows."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title).strip()
    return cleaned or "segment"
