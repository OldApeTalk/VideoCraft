"""
core/subtitle_ops.py - 字幕分割与样式工具函数

无任何 UI 依赖，供 SubtitleTool、text2Video 等模块共用。
"""

import os
import re
import srt
from datetime import timedelta

# ── 布局默认参数（16:9 / 9:16）──────────────────────────────────────────────

LAYOUT_DEFAULTS = {
    "horizontal": {          # 16:9
        "max_chars_zh": 20,
        "max_chars_en": 50,
        "fontsize":     28,
        "margin_v":     80,
    },
    "vertical": {            # 9:16
        "max_chars_zh": 10,
        "max_chars_en": 25,
        "fontsize":     20,
        "margin_v":     60,
    },
}


# ── 字幕分割 ─────────────────────────────────────────────────────────────────

def split_subtitle(sub, max_chars: int, is_chinese: bool = False):
    """
    将单条字幕按 max_chars 分割为多条。
    - 优先在标点处断开
    - 英文额外在空格处断开
    - 按字符比例分配时间轴
    """
    content = sub.content.strip()
    if len(content) <= max_chars:
        return [sub]

    new_subs = []
    start = sub.start
    end = sub.end
    total_duration = (end - start).total_seconds()

    if is_chinese:
        breaks = [m.start() for m in re.finditer(r'[，。？！；]', content)] + [len(content)]
    else:
        breaks = [m.start() for m in re.finditer(r'[.?!,]', content)] + [len(content)]

    current_pos = 0
    while current_pos < len(content):
        split_pos = current_pos + max_chars
        if split_pos >= len(content):
            split_pos = len(content)
        else:
            candidates = [b + 1 for b in breaks if current_pos < b + 1 <= split_pos]
            if candidates:
                split_pos = max(candidates)
            elif not is_chinese:
                last_space = content.rfind(' ', current_pos, split_pos)
                if last_space > current_pos:
                    split_pos = last_space + 1

        part = content[current_pos:split_pos].strip()
        if not part:
            break

        part_dur = (len(part) / len(content)) * total_duration
        part_end = start + timedelta(seconds=part_dur)
        new_subs.append(srt.Subtitle(
            index=len(new_subs) + 1,
            start=start,
            end=part_end,
            content=part,
        ))
        start = part_end
        current_pos = split_pos

    if new_subs:
        new_subs[-1].end = end
    return new_subs


def process_srt_split(input_path: str, max_chars: int,
                      is_chinese: bool = False) -> list:
    """
    读取 SRT 文件，对每条字幕执行分割，重新编号后返回字幕列表。
    """
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        subs = list(srt.parse(f.read()))
    result = []
    for sub in subs:
        result.extend(split_subtitle(sub, max_chars, is_chinese))
    for i, sub in enumerate(result, 1):
        sub.index = i
    return result


def split_srt_to_file(input_path: str, max_chars: int,
                      is_chinese: bool = False,
                      output_path: str = None) -> str:
    """
    分割 SRT 并写出文件。output_path 为 None 时写到同目录 _split.srt。
    返回输出文件路径。
    """
    subs = process_srt_split(input_path, max_chars, is_chinese)
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = base + "_split" + ext
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(srt.compose(subs))
    return output_path


# ── 颜色转换 ─────────────────────────────────────────────────────────────────

def hex_color_to_ass(color: str) -> str:
    """#RRGGBB → ASS 格式 &H00BBGGRR&"""
    color = color.lstrip('#')
    if len(color) != 6:
        color = "FFFFFF"
    r, g, b = color[0:2], color[2:4], color[4:6]
    return f"&H00{b}{g}{r}&"


def hex_color_to_drawtext(color: str) -> str:
    """#RRGGBB → drawtext 格式 #RRGGBB"""
    color = color.lstrip('#')
    if len(color) != 6:
        color = "FFFFFF"
    return f"#{color}"


# ── FFmpeg 路径转义 ───────────────────────────────────────────────────────────

def escape_ffmpeg_path(path: str) -> str:
    """将文件路径转为 ffmpeg 滤镜参数可用的格式（正斜杠 + 转义冒号）"""
    path = os.path.abspath(path).replace("\\", "/")
    path = path.replace(":", "\\:")
    return path


# ── 字幕样式构建 ──────────────────────────────────────────────────────────────

def build_subtitle_style(orientation: str,
                         fontsize: int = None,
                         color: str = "#FFFFFF",
                         margin_v: int = None,
                         bold: bool = False) -> str:
    """
    构建 ffmpeg subtitles 滤镜的 force_style 字符串。

    Args:
        orientation: "horizontal" | "vertical"
        fontsize:    字号（None 时按方向取默认值）
        color:       十六进制颜色 "#RRGGBB"
        margin_v:    距底部边距（None 时按方向取默认值）
        bold:        是否粗体
    """
    defaults = LAYOUT_DEFAULTS.get(orientation, LAYOUT_DEFAULTS["horizontal"])
    fs = fontsize if fontsize is not None else defaults["fontsize"]
    mv = margin_v if margin_v is not None else defaults["margin_v"]
    ass_color = hex_color_to_ass(color)
    return (
        f"Fontname=Microsoft YaHei,"
        f"Fontsize={fs},"
        f"PrimaryColour={ass_color},"
        f"OutlineColour=&H00000000&,"
        f"BorderStyle=1,Outline=2,Shadow=0,"
        f"Bold={1 if bold else 0},"
        f"Alignment=2,"
        f"MarginV={mv}"
    )
