"""
core/srt_ops.py - SRT 字幕纯逻辑操作

无任何 UI 依赖，失败 raise，进度通过 callback 传出。
"""

import os
import re


def extract_text(srt_path: str, output_path: str = None,
                 progress_callback=None) -> str:
    """
    提取 SRT 字幕的纯文本内容，保存为 .txt。
    返回输出文件路径。
    """
    if output_path is None:
        base = os.path.splitext(srt_path)[0]
        output_path = base + ".txt"

    if progress_callback:
        progress_callback("读取字幕文件...")

    with open(srt_path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    # 去除序号行（纯数字）、时间轴行（含 --> ）、空行
    lines = content.splitlines()
    text_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        if "-->" in line:
            continue
        text_lines.append(line)

    output_text = "\n".join(text_lines)

    if progress_callback:
        progress_callback(f"写入文本文件...")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output_text)

    if progress_callback:
        progress_callback(f"完成")

    return output_path


def get_stats(srt_path: str) -> dict:
    """
    返回字幕统计信息：
    {"count": int, "duration_sec": float, "has_chinese": bool}
    """
    with open(srt_path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    lines = content.splitlines()
    count = 0
    last_end_sec = 0.0
    has_chinese = False

    for line in lines:
        line = line.strip()
        if line.isdigit():
            count += 1
        elif "-->" in line:
            # 解析结束时间
            m = re.search(r"-->\\s*(\\d+):(\\d+):(\\d+)[,\\.](\\d+)", line)
            if not m:
                m = re.search(r"-->\s*(\d+):(\d+):(\d+)[,\.](\d+)", line)
            if m:
                h, mn, s, ms = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                last_end_sec = h * 3600 + mn * 60 + s + ms / 1000
        elif line and not line.isdigit() and "-->" not in line:
            if re.search(r"[\u4e00-\u9fff]", line):
                has_chinese = True

    return {
        "count": count,
        "duration_sec": last_end_sec,
        "has_chinese": has_chinese,
    }
