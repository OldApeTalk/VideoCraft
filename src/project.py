"""
project.py - VideoCraft Project 模型

Project = 文件夹。打开任意文件夹即为打开工程，自动生成 videocraft.json。
"""

import json
import os
from datetime import date

# ── 版本迁移 ──────────────────────────────────────────────────────────────────

CURRENT_VERSION = 1

MIGRATIONS = {
    # 示例：1: _migrate_v1_to_v2,
}

def _load_and_migrate(data: dict) -> dict:
    version = data.get("version", 1)
    while version < CURRENT_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
    data["version"] = CURRENT_VERSION
    return data

# ── 文件图标映射 ──────────────────────────────────────────────────────────────

_ICONS = {
    frozenset({".mp4", ".mkv", ".avi", ".mov", ".webm"}): "🎬",
    frozenset({".srt", ".ass", ".vtt"}):                  "📄",
    frozenset({".mp3", ".wav", ".aac", ".m4a", ".flac"}): "🎵",
    frozenset({".json"}):                                  "⚙️",
}

def file_icon(name: str, is_dir: bool = False) -> str:
    if is_dir:
        return "📁"
    ext = os.path.splitext(name)[1].lower()
    for exts, icon in _ICONS.items():
        if ext in exts:
            return icon
    return "📎"

# ── Project 类 ────────────────────────────────────────────────────────────────

class Project:
    MARKER = "videocraft.json"

    def __init__(self, folder: str, data: dict):
        self.folder = os.path.abspath(folder)
        self.data   = data

    # -- 工厂方法 ---------------------------------------------------------------

    @staticmethod
    def open(folder_path: str) -> "Project":
        """打开文件夹作为工程。若无 videocraft.json，自动创建。"""
        folder = os.path.abspath(folder_path)
        json_path = os.path.join(folder, Project.MARKER)

        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                data = _load_and_migrate(raw)
            except (json.JSONDecodeError, KeyError):
                data = Project._default_data()
        else:
            data = Project._default_data()

        project = Project(folder, data)
        project.save()   # 确保 json 写入（新建 or 迁移后写回）
        return project

    @staticmethod
    def _default_data() -> dict:
        return {
            "version": CURRENT_VERSION,
            "created": date.today().isoformat(),
        }

    # -- 文件列表 ---------------------------------------------------------------

    def get_files(self) -> list:
        """
        返回工程文件夹内的条目列表（单层，不递归），
        格式：[{"name": str, "path": str, "ext": str, "icon": str, "is_dir": bool}]
        videocraft.json 排在最后。
        """
        entries = []
        try:
            names = sorted(os.listdir(self.folder), key=lambda s: s.lower())
        except OSError:
            return []

        for name in names:
            full = os.path.join(self.folder, name)
            is_dir = os.path.isdir(full)
            ext = "" if is_dir else os.path.splitext(name)[1].lower()
            entries.append({
                "name":   name,
                "path":   full,
                "ext":    ext,
                "icon":   file_icon(name, is_dir),
                "is_dir": is_dir,
            })

        # videocraft.json 排到末尾
        entries.sort(key=lambda e: (e["name"] == Project.MARKER, not e["is_dir"], e["name"].lower()))
        return entries

    # -- 持久化 -----------------------------------------------------------------

    def save(self):
        """将 data 写回 videocraft.json。"""
        json_path = os.path.join(self.folder, Project.MARKER)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # -- 便捷属性 ---------------------------------------------------------------

    @property
    def name(self) -> str:
        return os.path.basename(self.folder)

# ── 最近工程 ──────────────────────────────────────────────────────────────────

_RECENT_MAX = 10

def _recent_path() -> str:
    config_dir = os.path.join(os.path.expanduser("~"), ".videocraft")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "recent.json")

def get_recent_projects() -> list:
    """返回最近工程路径列表（最新在前）。"""
    path = _recent_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 过滤掉已不存在的文件夹
        return [p for p in data.get("recent", []) if os.path.isdir(p)]
    except (json.JSONDecodeError, OSError):
        return []

def add_recent_project(folder_path: str):
    """将 folder_path 加入最近列表（去重，保留最新，最多 _RECENT_MAX 条）。"""
    folder = os.path.abspath(folder_path)
    recents = get_recent_projects()
    recents = [p for p in recents if p != folder]   # 去重
    recents.insert(0, folder)
    recents = recents[:_RECENT_MAX]
    path = _recent_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"recent": recents}, f, ensure_ascii=False, indent=2)
