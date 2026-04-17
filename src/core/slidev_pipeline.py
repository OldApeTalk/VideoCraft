"""Slidev pipeline — process Slidev .md files into per-page PNG + notes.

Relies on Node.js + Slidev CLI for rendering. Notes are extracted from HTML
comments (<!-- ... -->) in the Markdown source using Python regex.

Node.js environment is managed in <project_root>/node_env/:
  - node_env/package.json   — checked in, declares @slidev/cli + playwright
  - node_env/node_modules/  — auto-installed on first use (gitignored)
  - node_env/playwright-browsers/ — Chromium binary (gitignored, ~130 MB)

Call ensure_node_env() to install dependencies before first export.
"""

from __future__ import annotations

import os
import re
import subprocess
import shutil
from typing import Callable


ProgressCallback = Callable[[int, int, str], None]  # (done, total, msg)

# Resolve project root relative to this file (src/core/ → project root)
_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_NODE_ENV = os.path.join(_PROJECT_ROOT, "node_env")
_BROWSERS_PATH = os.path.join(_NODE_ENV, "playwright-browsers")


# ── Node.js environment setup ────────────────────────────────────────────────

def _find_node() -> str:
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        raise RuntimeError(
            "Node.js not detected. Please install Node.js from "
            "https://nodejs.org and ensure it is on your PATH."
        )
    return node


def _find_npm() -> str:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        node = _find_node()
        node_dir = os.path.dirname(node)
        for name in ("npm.cmd", "npm"):
            candidate = os.path.join(node_dir, name)
            if os.path.isfile(candidate):
                return candidate
        raise RuntimeError("npm not found. Reinstall Node.js.")
    return npm


_SLIDEV_MJS = os.path.join(
    _NODE_ENV, "node_modules", "@slidev", "cli", "bin", "slidev.mjs"
)


def _slidev_bin() -> str | None:
    """Return path to local slidev binary if installed, else None."""
    # Prefer the .mjs entry directly — avoids cmd /c argument-dropping bug
    # where Windows cmd.exe ignores args after a quoted .cmd path.
    if os.path.isfile(_SLIDEV_MJS):
        return _SLIDEV_MJS
    for name in ("slidev.cmd", "slidev"):
        p = os.path.join(_NODE_ENV, "node_modules", ".bin", name)
        if os.path.isfile(p):
            return p
    return None


def _playwright_bin() -> str | None:
    for name in ("playwright.cmd", "playwright"):
        p = os.path.join(_NODE_ENV, "node_modules", ".bin", name)
        if os.path.isfile(p):
            return p
    return None


def _playwright_chromium_pkg() -> bool:
    """True if playwright-chromium npm package is installed (Slidev requires it)."""
    return os.path.isdir(
        os.path.join(_NODE_ENV, "node_modules", "playwright-chromium")
    )


def _chromium_installed() -> bool:
    """True if our own Playwright Chromium download exists."""
    return os.path.isdir(_BROWSERS_PATH) and any(
        d.startswith("chromium") for d in os.listdir(_BROWSERS_PATH)
        if os.path.isdir(os.path.join(_BROWSERS_PATH, d))
    )


def _wrap_cmd(cmd: list[str]) -> list[str]:
    """Resolve the correct executable for .cmd/.mjs scripts on Windows."""
    if not cmd:
        return cmd
    first = cmd[0]
    if first.lower().endswith(".mjs"):
        # Invoke .mjs via node.exe — avoids cmd /c argument-dropping bug.
        return [_find_node()] + cmd
    if os.name == "nt" and first.lower().endswith(".cmd"):
        # Fallback for other .cmd tools (e.g. npm, playwright).
        return ["cmd", "/c"] + cmd
    return cmd


def _run_logged(cmd: list[str], cwd: str, env: dict,
                on_log: Callable[[str], None] | None) -> None:
    """Run a subprocess, streaming stdout/stderr lines to on_log."""
    cmd = _wrap_cmd(cmd)
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    for line in proc.stdout:
        if on_log:
            on_log(line.rstrip())
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed (exit {proc.returncode}): {' '.join(cmd)}"
        )


def ensure_node_env(
    on_log: Callable[[str], None] | None = None,
) -> None:
    """Install Slidev + Playwright + Chromium into node_env/ if needed.

    Safe to call every time — skips steps that are already done.
    on_log receives status lines for UI display.
    """
    _find_node()  # raises if Node.js missing
    npm = _find_npm()

    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = _BROWSERS_PATH

    # Step 1: npm install — also re-runs if playwright-chromium is missing,
    # since Slidev's importPlaywright() requires that specific package.
    if _slidev_bin() is None or not _playwright_chromium_pkg():
        if on_log:
            on_log("Installing @slidev/cli + playwright (npm install)...")
        _run_logged(
            [npm, "install", "--prefer-offline"],
            cwd=_NODE_ENV,
            env=env,
            on_log=on_log,
        )
    else:
        if on_log:
            on_log("node_modules already installed, skipping npm install.")

    # Step 2: install Playwright Chromium into node_env/playwright-browsers/
    if not _chromium_installed():
        pw = _playwright_bin()
        if pw is None:
            raise RuntimeError(
                "playwright binary not found after npm install. "
                "Try deleting node_env/node_modules and retrying."
            )
        if on_log:
            on_log("Downloading Playwright Chromium (~130 MB, one-time)...")
        _run_logged(
            [pw, "install", "chromium"],
            cwd=_NODE_ENV,
            env=env,
            on_log=on_log,
        )
    else:
        if on_log:
            on_log("Chromium already installed, skipping.")


# ── Notes extraction ─────────────────────────────────────────────────────────

def extract_slidev_notes(md_path: str, notes_dir: str) -> list[str]:
    """Parse speaker notes from a Slidev .md file.

    Notes live inside <!-- ... --> HTML comments within each slide block.
    Slides are separated by `---` on its own line.
    Returns list of written note file paths.
    """
    os.makedirs(notes_dir, exist_ok=True)

    text = open(md_path, "r", encoding="utf-8").read()

    # Split on --- slide separators
    slide_blocks = re.split(r'\n---+\n', text)

    # Skip leading frontmatter block (no heading, looks like YAML key:value)
    if slide_blocks and not re.search(r'^\s*#', slide_blocks[0], re.MULTILINE):
        slide_blocks = slide_blocks[1:]

    paths: list[str] = []
    for i, block in enumerate(slide_blocks, 1):
        comments = re.findall(r'<!--(.*?)-->', block, re.DOTALL)
        note_text = "\n".join(c.strip() for c in comments if c.strip())
        out_path = os.path.join(notes_dir, f"page_{i:02d}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(note_text)
        paths.append(out_path)

    return paths


# ── PNG export ───────────────────────────────────────────────────────────────

def export_slidev_to_png(
    md_path: str,
    pages_dir: str,
    *,
    on_progress: ProgressCallback | None = None,
) -> list[str]:
    """Export Slidev .md slides to per-page PNG files in pages_dir.

    Expects ensure_node_env() to have been called first.
    Renames Slidev's default 001.png/002.png output to page_01.png/page_02.png.
    Returns sorted list of final PNG paths.
    """
    os.makedirs(pages_dir, exist_ok=True)

    slidev = _slidev_bin()
    if slidev is None:
        raise RuntimeError(
            "Slidev not installed. Run setup first (node_env is not ready)."
        )

    md_abs = os.path.abspath(md_path)
    pages_abs = os.path.abspath(pages_dir)
    md_dir = os.path.dirname(md_abs)

    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = _BROWSERS_PATH

    # Use a relative output path (relative to cwd = md_dir) to avoid Windows
    # cmd /c absolute-path quoting issues that can silently drop --output.
    pages_rel = os.path.relpath(pages_abs, start=md_dir)

    cmd = [
        slidev, "export",
        "--format", "png",
        "--per-slide",          # navigate each slide individually; avoids
                                # .print-slide-container selector issues
        "--output", pages_rel,
        "--timeout", "60000",   # 60 s per slide; prevents silent hangs
        os.path.basename(md_abs),   # relative md path; cwd is md_dir
    ]

    if on_progress:
        on_progress(0, 1, "starting slidev export (launching browser)...")

    # Use streaming Popen so log lines surface to the UI in real time.
    last_lines: list[str] = []

    def _log(line: str):
        last_lines.append(line)
        if on_progress:
            on_progress(0, 1, line[:80] or "running slidev export...")

    try:
        _run_logged(
            cmd,
            cwd=os.path.dirname(md_abs),
            env=env,
            on_log=_log,
        )
    except RuntimeError as e:
        tail = "\n".join(last_lines[-10:])
        raise RuntimeError(
            f"slidev export failed.\nLast output:\n{tail}"
        ) from e

    # Rename whatever PNGs Slidev produced → page_01.png, page_02.png ...
    # --per-slide produces 01.png/02.png; onePiece produces 1.png/2.png.
    # Accept any .png file; sort naturally so slide order is preserved.
    raw_pngs = sorted(
        f for f in os.listdir(pages_abs)
        if f.lower().endswith(".png")
    )
    final_paths: list[str] = []
    for idx, fname in enumerate(raw_pngs, 1):
        src = os.path.join(pages_abs, fname)
        dst = os.path.join(pages_abs, f"page_{idx:02d}.png")
        if src != dst:
            os.replace(src, dst)
        final_paths.append(dst)

    if on_progress:
        on_progress(1, 1, f"exported {len(final_paths)} slides")

    return final_paths


# ── Combined step-2 entry point ──────────────────────────────────────────────

def run_step2_slidev(
    md_path: str,
    workdir: str,
    *,
    on_progress: ProgressCallback | None = None,
) -> tuple[list[str], list[str]]:
    """Extract notes + export PNGs from a Slidev .md file.

    Calls ensure_node_env() automatically on first use.
    Returns (page_paths, note_paths).
    """
    pages_dir = os.path.join(workdir, "pages")
    notes_dir = os.path.join(workdir, "notes")

    if _slidev_bin() is None or not _playwright_chromium_pkg():
        raise RuntimeError(
            "Slidev CLI or playwright-chromium is not installed. "
            "Go to File \u2192 Settings \u2192 Environment and click Install."
        )

    if not _chromium_installed():
        raise RuntimeError(
            "Playwright Chromium browser is not installed. "
            "Go to File \u2192 Settings \u2192 Environment and click Install."
        )

    # Notes extracted from .md (no Node needed)
    note_paths = extract_slidev_notes(md_path, notes_dir)

    # PNG export via Slidev CLI
    page_paths = export_slidev_to_png(md_path, pages_dir, on_progress=on_progress)

    # Pad note list to match page count if Slidev produced more slides than notes
    while len(note_paths) < len(page_paths):
        i = len(note_paths) + 1
        empty = os.path.join(notes_dir, f"page_{i:02d}.txt")
        open(empty, "w").close()
        note_paths.append(empty)

    return page_paths, note_paths
