"""Prompt hub — central storage for all AI prompts used by feature layer.

Every prompt is a markdown file under `<repo>/prompts/<task_id>.md`. The
file content IS the prompt template, with `{placeholder}` substitution
done by the caller via `str.format(**vars)`.

Per architecture principle 4 (see docs/design/04-ai-router.md):
prompts MUST NOT live in tool UIs. Feature layer (core/srt_ops, core/
translate, ...) calls `prompts.get(task_id)` to fetch the template, then
fills placeholders before passing to ai.complete().

Reset path: each task has a built-in default constant in this module
(used both as the initial seeded file AND as the "Reset to default"
target in the AI Console UI).

Phase 1 limitations (intentional):
  - Single prompt per task. Per-(task, provider) variants are
    deferred (Phase 2; see design doc).
  - Storage path is `<repo>/prompts/`; user override layer in
    `<repo>/user_data/prompts/` will land with BACKLOG L17 portable
    refactor. For now, edits write directly to the shipped path.
"""

from __future__ import annotations

import os
from typing import Iterable


# ── Path resolution ─────────────────────────────────────────────────────────

def prompts_dir() -> str:
    """Return absolute path to the repo's prompts/ directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    # src/core -> src -> <repo root>
    return os.path.normpath(os.path.join(here, "..", "..", "prompts"))


def _path(task_id: str) -> str:
    return os.path.join(prompts_dir(), f"{task_id}.md")


# ── Built-in defaults ───────────────────────────────────────────────────────
# Single source of truth for "Reset to default" and for first-run seeding
# when prompts/*.md is missing. These are duplicated as files in
# `<repo>/prompts/` at install time so users can edit without code edits.

DEFAULTS: dict[str, str] = {

    "translate": (
        "You are a professional SRT subtitle translator. Translate the "
        "following subtitles from {source_lang_name} to {target_lang_name}.\n"
        "\n"
        "The input is a batch of {batch_size} subtitles, each prefixed "
        "with a 【number】 marker to identify its position. Use the marker's "
        "number as the `index` in your response.\n"
        "\n"
        "Rules:\n"
        "1. Translate each subtitle independently. Do NOT merge, split, "
        "add, or remove subtitles — return exactly {batch_size} items.\n"
        "2. Preserve line breaks and punctuation within each subtitle.\n"
        "3. Do not wrap translations in quotation marks unless quotes are "
        "part of the original meaning.\n"
        "4. Ensure natural, fluent {target_lang_name}.\n"
        "\n"
        "Input subtitles (batch size = {batch_size}):\n"
        "{numbered_input}\n"
    ),

    "subtitle.segments": (
        "# 生成时间戳分段\n"
        "\n"
        "【\n"
        "\n"
        "1、你知道youtube的视频分段的格式吧？请学习这种分段格式：\n"
        "\n"
        "xx:xx 标题\n"
        "\n"
        "xx:xx 标题\n"
        "\n"
        "xx:xx 标题\n"
        "\n"
        "2、请根据srt字幕内容，生成youtube分段描述（中文）\n"
        "\n"
        "3、如有记者提问，优先以记者提问内容作为标题\n"
        "\n"
        "4、时:分:秒，这是时间戳的基本格式，不要弄错了\n"
        "\n"
        "】\n"
        "\n"
        "以下是SRT字幕内容：\n"
        "\n"
        "{subtitle_content}\n"
        "\n"
        "请根据以上字幕内容生成YouTube分段描述，格式为每行一个分段，"
        "格式为：时:分:秒 标题"
    ),

    "subtitle.refine": (
        "## 精炼全部分段\n"
        "\n"
        "【\n"
        "请一次性对全部分段内容进行总结提炼，每个段落提炼后不超过128个字。\n"
        "对于问答段落，保留精炼后的问题和回答，保持问答说话人的视角，"
        "不要改为第三方转述。\n"
        "输出格式为：\n"
        "时间戳 标题\n"
        "精炼内容\n"
        "\n"
        "分段之间空一行，不要添加解释。\n"
        "】\n"
        "\n"
        "以下是全部分段内容：\n"
        "{all_segments_content}\n"
    ),

    "subtitle.titles": (
        "## 生成标题\n"
        "\n"
        "【\n"
        "给这个视频起个合适的名字，新闻性十足、概括核心焦点，"
        "稍微长些没关系\n"
        "\n"
        "】"
    ),
}


# Placeholder catalog for UI display ("which {variables} this prompt uses").
# Feature layer is the contract owner — these strings are documentary.
PLACEHOLDERS: dict[str, list[str]] = {
    "translate": ["{source_lang_name}", "{target_lang_name}",
                  "{batch_size}", "{numbered_input}"],
    "subtitle.segments": ["{subtitle_content}"],
    "subtitle.refine":   ["{all_segments_content}"],
    "subtitle.titles":   [],
}


# ── Public API ──────────────────────────────────────────────────────────────

def get(task_id: str) -> str:
    """Return the prompt template for `task_id`.

    Reads `<prompts_dir>/<task_id>.md` if present, else falls back to the
    built-in DEFAULTS. Returns empty string if neither has the task.
    """
    path = _path(task_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            pass
    return DEFAULTS.get(task_id, "")


def set(task_id: str, content: str) -> None:
    """Write a new prompt template for `task_id` (overwrites any prior file)."""
    if task_id not in DEFAULTS:
        raise ValueError(f"Unknown task_id: {task_id!r}")
    os.makedirs(prompts_dir(), exist_ok=True)
    with open(_path(task_id), "w", encoding="utf-8", newline="") as f:
        f.write(content)


def reset(task_id: str) -> str:
    """Restore the built-in default prompt for `task_id`. Returns the
    default text that was written."""
    if task_id not in DEFAULTS:
        raise ValueError(f"Unknown task_id: {task_id!r}")
    default = DEFAULTS[task_id]
    set(task_id, default)
    return default


def is_overridden(task_id: str) -> bool:
    """True if the on-disk prompt differs from the built-in default."""
    if task_id not in DEFAULTS:
        return False
    return get(task_id) != DEFAULTS[task_id]


def list_tasks() -> Iterable[str]:
    """Iterate task ids with built-in defaults (canonical prompt set)."""
    return DEFAULTS.keys()


def placeholders(task_id: str) -> list[str]:
    """Return the documented placeholder list for `task_id`."""
    return list(PLACEHOLDERS.get(task_id, []))


def ensure_files_exist() -> None:
    """First-run helper: write any missing prompts/<task>.md from defaults
    so the prompts/ folder is fully seeded for the user to browse / edit."""
    os.makedirs(prompts_dir(), exist_ok=True)
    for task_id, default in DEFAULTS.items():
        path = _path(task_id)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(default)
