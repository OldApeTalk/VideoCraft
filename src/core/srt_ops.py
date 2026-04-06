"""
core/srt_ops.py - SRT 字幕纯逻辑操作

无任何 UI 依赖，失败 raise，进度通过 callback 传出。
"""

import os
import re
import srt
from core.subtitle_ops import read_srt


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

    content = read_srt(srt_path)

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
    content = read_srt(srt_path)

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


# ── SRT 后处理业务逻辑 ─────────────────────────────────────────────────────────

def generate_youtube_segments(srt_path, prompt=None, tier=None):
    """根据SRT字幕文件生成YouTube分段描述，返回 AI 生成的文本。"""
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f'SRT文件 \'{srt_path}\' 不存在')

    subs = list(srt.parse(read_srt(srt_path)))

    if not subs:
        raise ValueError('SRT文件为空或格式错误')

    subtitle_content = ''
    for sub in subs:
        time_str = str(sub.start)[:8]
        content = sub.content.replace('\n', ' ')
        subtitle_content += f'[{time_str}] {content}\n'

    if prompt is None:
        prompt = f'''# 生成时间戳分段

【

1、你知道youtube的视频分段的格式吧？请学习这种分段格式：

xx:xx 标题

xx:xx 标题

xx:xx 标题

2、请根据srt字幕内容，生成youtube分段描述（中文）

3、如有记者提问，优先以记者提问内容作为标题

4、时:分:秒，这是时间戳的基本格式，不要弄错了

】

以下是SRT字幕内容：

{subtitle_content}

请根据以上字幕内容生成YouTube分段描述，格式为每行一个分段，格式为：时:分:秒 标题'''
    else:
        prompt = prompt.replace("{subtitle_content}", subtitle_content)

    from ai_router import router, TIER_PREMIUM
    _tier = tier or TIER_PREMIUM
    try:
        return router.complete(prompt, tier=_tier)
    except Exception as e:
        raise RuntimeError(f'调用AI生成失败 (tier={_tier}): {e}')


def extract_paragraphs_from_segments(srt_path, segments_path):
    """根据时间戳分割文件从SRT字幕中提取段落内容，返回格式化文本。"""
    subs = list(srt.parse(read_srt(srt_path)))

    segments_lines = read_srt(segments_path).splitlines(keepends=True)

    segments = []
    for line in segments_lines:
        line = line.strip()
        if line and ' ' in line:
            time_str, title = line.split(' ', 1)
            try:
                time_parts = list(map(int, time_str.split(':')))
                if len(time_parts) == 2:
                    m, s = time_parts
                    timestamp = m * 60 + s
                elif len(time_parts) == 3:
                    h, m, s = time_parts
                    timestamp = h * 3600 + m * 60 + s
                else:
                    continue
                segments.append({'timestamp': timestamp, 'time_str': time_str,
                                  'title': title, 'content': []})
            except ValueError:
                continue

    if not segments:
        raise ValueError("时间戳分割文件中没有找到有效的时间戳")

    current_segment_idx = 0
    for sub in subs:
        sub_start = sub.start.total_seconds()
        content = sub.content.replace('\n', ' ')
        while current_segment_idx < len(segments) - 1:
            if sub_start < segments[current_segment_idx + 1]['timestamp']:
                break
            current_segment_idx += 1
        if current_segment_idx < len(segments) - 1:
            if sub_start < segments[current_segment_idx + 1]['timestamp']:
                segments[current_segment_idx]['content'].append(content)
        else:
            segments[current_segment_idx]['content'].append(content)

    output = ""
    for segment in segments:
        output += f"{segment['time_str']} {segment['title']}\n"
        if segment['content']:
            output += f"{' '.join(segment['content'])}\n\n"
        else:
            output += "(此时间段内无字幕内容)\n\n"

    return output.strip()


def generate_video_titles(subs_path, prompt, tier=None):
    """根据subs文件内容生成视频标题，返回 AI 生成的文本。"""
    subs_content = read_srt(subs_path)

    full_prompt = f"{prompt}\n\n以下是视频的分段描述内容：\n\n{subs_content}\n\n请根据以上内容生成合适的视频标题。"

    from ai_router import router, TIER_PREMIUM
    _tier = tier or TIER_PREMIUM
    try:
        return router.complete(full_prompt, tier=_tier)
    except Exception as e:
        raise RuntimeError(f'调用AI生成失败 (tier={_tier}): {e}')


def _is_valid_segment_timestamp(time_str):
    """验证时间戳是否为 mm:ss 或 hh:mm:ss 格式。"""
    return re.match(r'^\d{1,2}:\d{2}(?::\d{2})?$', time_str) is not None


def parse_segments_paragraphs_content(content):
    """将"提取段落内容"的输出文本解析为结构化分段列表。"""
    segments = []
    current_segment = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(' ', 1)
        if len(parts) == 2 and _is_valid_segment_timestamp(parts[0]):
            if current_segment:
                current_segment['content'] = ' '.join(current_segment['content']).strip()
                segments.append(current_segment)
            current_segment = {'time_str': parts[0], 'title': parts[1].strip(), 'content': []}
        elif current_segment is not None:
            current_segment['content'].append(line)
    if current_segment:
        current_segment['content'] = ' '.join(current_segment['content']).strip()
        segments.append(current_segment)
    return segments


def refine_segment_descriptions(paragraphs_path, prompt, tier=None):
    """对"提取段落内容"的输出进行 AI 精炼，返回精炼后文本。"""
    if not os.path.exists(paragraphs_path):
        raise FileNotFoundError(f'段落内容文件 \'{paragraphs_path}\' 不存在')

    paragraphs_content = read_srt(paragraphs_path)

    segments = parse_segments_paragraphs_content(paragraphs_content)
    if not segments:
        raise ValueError('未能从输入文件中解析到有效分段，请确认文件为"提取段落内容"标签页输出格式')

    combined_segments = []
    for idx, segment in enumerate(segments, start=1):
        segment_content = segment['content'] or '(此时间段内无字幕内容)'
        combined_segments.append(
            f"[分段{idx}]\n分段时间戳：{segment['time_str']}\n"
            f"分段标题：{segment['title']}\n分段内容：\n{segment_content}\n"
        )
    all_segments_content = '\n'.join(combined_segments).strip()

    full_prompt = prompt
    full_prompt = full_prompt.replace('{all_segments_content}', all_segments_content)
    full_prompt = full_prompt.replace('{segments_content}', all_segments_content)

    if any(t in full_prompt for t in ('{segment_time}', '{segment_title}', '{segment_content}')):
        full_prompt = (
            "请一次性精炼以下全部分段内容。\n"
            "要求：每个分段不超过128字；问答段落保留问答视角；\n"
            "输出格式为：\"时间戳 标题\\n精炼内容\"，分段之间空一行，不要额外解释。\n\n"
            f"{all_segments_content}"
        )
    elif all_segments_content not in full_prompt:
        full_prompt = f"{full_prompt}\n\n以下是全部分段内容：\n{all_segments_content}"

    from ai_router import router, TIER_PREMIUM
    _tier = tier or TIER_PREMIUM
    refined_text = router.complete(full_prompt, tier=_tier)
    if not refined_text:
        raise RuntimeError('AI返回为空，未生成精炼结果')
    return refined_text
