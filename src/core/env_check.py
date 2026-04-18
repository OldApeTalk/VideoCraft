"""Environment detection utilities.

Lightweight version checks for Node.js, npm, Slidev, yt-dlp, and Python SDKs.
All public functions return a version/path string on success, or None if
the component is missing. No side effects; safe to call from the UI thread.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_NODE_ENV = os.path.join(_PROJECT_ROOT, "node_env")
_BROWSERS_PATH = os.path.join(_NODE_ENV, "playwright-browsers")

_EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_system_edge() -> str | None:
    """Return path to system Edge (Chromium-based) if available, else None."""
    for p in _EDGE_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def _run_version(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=5)
        if r.returncode == 0:
            return (r.stdout.strip() or r.stderr.strip()) or None
    except Exception:
        pass
    return None


def check_node() -> str | None:
    """Return Node.js version string (e.g. 'v20.11.0') or None."""
    node = shutil.which("node") or shutil.which("node.exe")
    return _run_version([node, "--version"]) if node else None


def check_npm() -> str | None:
    """Return npm version string or None."""
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    return _run_version([npm, "--version"]) if npm else None


def check_slidev() -> str | None:
    """Return Slidev CLI version from node_env, or None if not installed."""
    pkg = os.path.join(_NODE_ENV, "node_modules", "@slidev", "cli", "package.json")
    if not os.path.isfile(pkg):
        return None
    try:
        with open(pkg, "r", encoding="utf-8") as f:
            return json.load(f).get("version")
    except Exception:
        return None


def check_browser() -> str | None:
    """Return 'Chromium (playwright)' if the Playwright-managed Chromium is installed, else None."""
    if os.path.isdir(_BROWSERS_PATH) and any(
        d.startswith("chromium")
        for d in os.listdir(_BROWSERS_PATH)
        if os.path.isdir(os.path.join(_BROWSERS_PATH, d))
    ):
        return "Chromium (playwright)"
    return None


def check_ytdlp() -> str | None:
    """Return yt-dlp version string or None."""
    try:
        from importlib.metadata import version
        return version("yt-dlp")
    except Exception:
        pass
    ytdlp = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    return _run_version([ytdlp, "--version"]) if ytdlp else None


def check_fish_audio_sdk() -> str | None:
    """Return fish-audio-sdk version or None."""
    try:
        from importlib.metadata import version
        return version("fish-audio-sdk")
    except Exception:
        return None


def check_openai_sdk() -> str | None:
    """Return openai package version or None."""
    try:
        from importlib.metadata import version
        return version("openai")
    except Exception:
        return None
