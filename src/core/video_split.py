"""Split-mode backend. Unified entry point for all segment-cut operations.

Three cut modes:
- FAST: stream copy with ffmpeg's implicit pre-seek keyframe snap. Fastest, but
  the cut boundary may drift several seconds earlier than requested.
- KEYFRAME_SNAP: probe I-frames via ffprobe, snap each start to the largest
  keyframe <= target, then stream copy. No re-encode, predictable alignment.
- ACCURATE: re-encode each segment. Frame-accurate boundaries at the cost of
  speed and a small quality loss.

The module also exposes probe_keyframes() with a per-(path, mtime) cache so
callers (e.g. split_workbench exporting the same video multiple times in a
session) amortize the ffprobe scan.

Future work: video_tools.auto_split_video / ExtractClipApp should migrate to
split_one() instead of carrying their own ffprobe/ffmpeg implementations.
"""

from __future__ import annotations

import json
import os
import subprocess
from enum import Enum
from typing import Optional

from core.video_concat import reencode_segment, stream_copy_segment


class SplitMode(str, Enum):
    FAST = "fast"
    KEYFRAME_SNAP = "keyframe_snap"
    ACCURATE = "accurate"


# Per-video keyframe cache: {abs_path: (mtime, [kf_seconds...])}
_KEYFRAME_CACHE: dict[str, tuple[float, list[float]]] = {}


def probe_keyframes(video_path: str) -> list[float]:
    """Return sorted I-frame pts_time (seconds) for the video.

    Cached per (abs_path, mtime) in-process; no disk persistence. Raises
    RuntimeError if ffprobe fails or produces unparseable output.
    """
    abs_path = os.path.abspath(video_path)
    try:
        mtime = os.path.getmtime(abs_path)
    except OSError as e:
        raise RuntimeError(f"probe_keyframes: cannot stat {abs_path}: {e}")

    cached = _KEYFRAME_CACHE.get(abs_path)
    if cached and cached[0] == mtime:
        return cached[1]

    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "packet=pts_time,flags",
        "-of", "json",
        abs_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        stderr = (result.stderr or "").strip().splitlines()[-5:]
        raise RuntimeError("ffprobe failed: " + " | ".join(stderr))

    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"ffprobe output not JSON: {e}")

    keyframes: list[float] = []
    for pkt in data.get("packets", []):
        if "K" not in pkt.get("flags", ""):
            continue
        pts = pkt.get("pts_time")
        if pts is None:
            continue
        try:
            keyframes.append(float(pts))
        except (TypeError, ValueError):
            continue
    keyframes.sort()
    _KEYFRAME_CACHE[abs_path] = (mtime, keyframes)
    return keyframes


def snap_to_prior_keyframe(target_sec: float, keyframes: list[float]) -> float:
    """Return the largest keyframe <= target_sec, or target_sec if none exist.

    Uses binary search so the loop over all segments stays O(n log k).
    """
    if not keyframes:
        return target_sec
    lo, hi = 0, len(keyframes)
    while lo < hi:
        mid = (lo + hi) // 2
        if keyframes[mid] <= target_sec:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return target_sec
    return keyframes[lo - 1]


def split_one(
    video_path: str,
    start_sec: float,
    duration_sec: float,
    output: str,
    mode: SplitMode = SplitMode.KEYFRAME_SNAP,
    keyframes: Optional[list[float]] = None,
) -> float:
    """Cut one segment according to `mode`. Returns the ACTUAL start used.

    Under KEYFRAME_SNAP the returned start may be earlier than `start_sec`
    (snapped to the nearest prior I-frame). Callers that need gap-free
    stitching should use the returned value to recompute the next segment's
    duration.

    `keyframes` can be pre-supplied to avoid re-probing; if omitted and mode
    requires them, probe_keyframes(video_path) is called (which will hit the
    cache on repeat calls).
    """
    if mode == SplitMode.KEYFRAME_SNAP:
        kfs = keyframes if keyframes is not None else probe_keyframes(video_path)
        actual_start = snap_to_prior_keyframe(start_sec, kfs)
        # Extend duration by the amount we moved backwards so the end time
        # stays where the caller asked for.
        adjusted_duration = duration_sec + (start_sec - actual_start)
        stream_copy_segment(video_path, actual_start, adjusted_duration, output)
        return actual_start

    if mode == SplitMode.ACCURATE:
        reencode_segment(video_path, start_sec, duration_sec, output)
        return start_sec

    # FAST
    stream_copy_segment(video_path, start_sec, duration_sec, output)
    return start_sec


__all__ = [
    "SplitMode",
    "probe_keyframes",
    "snap_to_prior_keyframe",
    "split_one",
]
