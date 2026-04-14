from tools.base import ToolBase
import os
import re
import srt
import sys
import tkinter as tk
from tkinter import filedialog, ttk
import threading
from datetime import datetime
from hub_logger import logger

# Hub 内嵌时 core 包在 src/ 下，独立运行时也在同一目录
_SRC = os.path.dirname(os.path.abspath(__file__))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
from core import srt_ops
from core.subtitle_ops import read_srt

# ===================== AI Router (统一路由) =====================
# AI 调用统一由 ai_router.router 处理，档位配置见 AI Router 管理界面

# ===================== Business Logic Functions =====================

def generate_youtube_segments(srt_path, prompt=None, tier=None):
    '''
    根据SRT字幕文件生成YouTube分段描述

    Args:
        srt_path (str): SRT文件路径
        provider_name (str): AI提供商名称
        model_name (str): 模型名称
        prompt (str): 自定义提示语，如果为None则使用默认提示语

    Returns:
        str: 生成的YouTube分段描述
    '''
    # 读取并解析SRT文件
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f'SRT文件 \'{srt_path}\' 不存在')

    subs = list(srt.parse(read_srt(srt_path)))

    if not subs:
        raise ValueError('SRT文件为空或格式错误')

    # 提取字幕内容
    subtitle_content = ''
    for sub in subs:
        # 格式化时间戳为 hh:mm:ss
        time_str = str(sub.start)[:8]  # 取前8个字符，格式为 hh:mm:ss
        content = sub.content.replace('\n', ' ')
        subtitle_content += f'[{time_str}] {content}\n'

    # 构建prompt
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
        # 使用自定义prompt，替换占位符
        full_prompt = prompt.replace("{subtitle_content}", subtitle_content)
        prompt = full_prompt

    # 调用AI生成
    from ai_router import router, TIER_PREMIUM
    _tier = tier or TIER_PREMIUM
    try:
        return router.complete(prompt, tier=_tier)
    except Exception as e:
        raise RuntimeError(f'调用AI生成失败 (tier={_tier}): {e}')

def extract_paragraphs_from_segments(srt_path, segments_path):
    """
    根据时间戳分割文件从SRT字幕中提取段落内容

    Args:
        srt_path (str): SRT文件路径
        segments_path (str): 时间戳分割文件路径

    Returns:
        str: 提取的段落内容
    """
    # 读取并解析SRT文件
    subs = list(srt.parse(read_srt(srt_path)))

    # 读取时间戳分割文件
    with open(segments_path, 'r', encoding='utf-8', errors='replace') as f:
        segments_lines = f.readlines()

    # 解析时间戳分割
    segments = []
    for line in segments_lines:
        line = line.strip()
        if line and ' ' in line:
            time_str, title = line.split(' ', 1)
            try:
                # 解析时间戳 (支持 mm:ss 或 hh:mm:ss 格式)
                time_parts = list(map(int, time_str.split(':')))
                if len(time_parts) == 2:
                    # mm:ss 格式
                    m, s = time_parts
                    timestamp = m * 60 + s
                elif len(time_parts) == 3:
                    # hh:mm:ss 格式
                    h, m, s = time_parts
                    timestamp = h * 3600 + m * 60 + s
                else:
                    continue  # 格式不正确，跳过
                segments.append({
                    'timestamp': timestamp,
                    'time_str': time_str,
                    'title': title,
                    'content': []
                })
            except ValueError:
                continue  # 跳过格式错误的行

    if not segments:
        raise ValueError("时间戳分割文件中没有找到有效的时间戳")

    # 为每个段落分配字幕内容
    current_segment_idx = 0
    for sub in subs:
        sub_start = sub.start.total_seconds()
        sub_end = sub.end.total_seconds()
        content = sub.content.replace('\n', ' ')

        # 找到这个字幕所属的段落
        while current_segment_idx < len(segments) - 1:
            if sub_start < segments[current_segment_idx + 1]['timestamp']:
                break
            current_segment_idx += 1

        # 如果还有下一个段落，检查字幕是否跨越段落边界
        if current_segment_idx < len(segments) - 1:
            next_timestamp = segments[current_segment_idx + 1]['timestamp']
            if sub_start < next_timestamp:
                segments[current_segment_idx]['content'].append(content)
        else:
            # 最后一个段落
            segments[current_segment_idx]['content'].append(content)

    # 生成输出
    output = ""
    for segment in segments:
        output += f"{segment['time_str']} {segment['title']}\n"
        if segment['content']:
            paragraph = ' '.join(segment['content'])
            output += f"{paragraph}\n\n"
        else:
            output += "(此时间段内无字幕内容)\n\n"

    return output.strip()

def generate_video_titles(subs_path, prompt, tier=None):
    """
    根据subs文件内容生成视频标题

    Args:
        subs_path (str): Subs文件路径
        prompt (str): 生成标题的prompt
        provider_name (str): AI提供商名称
        model_name (str): 模型名称

    Returns:
        str: 生成的标题内容
    """
    # 读取subs文件内容
    with open(subs_path, 'r', encoding='utf-8', errors='replace') as f:
        subs_content = f.read()

    # 构建完整的prompt
    full_prompt = f"{prompt}\n\n以下是视频的分段描述内容：\n\n{subs_content}\n\n请根据以上内容生成合适的视频标题。"

    # 调用AI生成
    from ai_router import router, TIER_PREMIUM
    _tier = tier or TIER_PREMIUM
    try:
        return router.complete(full_prompt, tier=_tier)
    except Exception as e:
        raise RuntimeError(f'调用AI生成失败 (tier={_tier}): {e}')

def extract_all_subtitles(srt_path):
    """
    从SRT文件中提取所有字幕文字，每条字幕一行

    Args:
        srt_path (str): SRT文件路径

    Returns:
        str: 提取的字幕文字，每行一条
    """
    # 读取并解析SRT文件
    subs = list(srt.parse(read_srt(srt_path)))

    # 提取所有字幕文字
    subtitles_text = ""
    for sub in subs:
        # 清理字幕文字，移除多余的换行符
        content = sub.content.replace('\n', ' ').strip()
        if content:  # 只添加非空的字幕
            subtitles_text += content + '\n'

    return subtitles_text.strip()

def _is_valid_segment_timestamp(time_str):
    """Validate whether segment timestamp is in mm:ss or hh:mm:ss format."""
    return re.match(r'^\d{1,2}:\d{2}(?::\d{2})?$', time_str) is not None

def parse_segments_paragraphs_content(content):
    """Parse text generated by Tab 3 (paragraph extraction) into structured segments."""
    segments = []
    current_segment = None

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split(' ', 1)
        # A segment header line is expected as: "timestamp title"
        if len(parts) == 2 and _is_valid_segment_timestamp(parts[0]):
            if current_segment:
                current_segment['content'] = ' '.join(current_segment['content']).strip()
                segments.append(current_segment)

            current_segment = {
                'time_str': parts[0],
                'title': parts[1].strip(),
                'content': []
            }
        elif current_segment is not None:
            current_segment['content'].append(line)

    if current_segment:
        current_segment['content'] = ' '.join(current_segment['content']).strip()
        segments.append(current_segment)

    return segments

def refine_segment_descriptions(paragraphs_path, prompt, tier=None):
    """
    Refine all segments generated by Tab 3 in one AI request.

    Args:
        paragraphs_path (str): Input paragraph file path (output from Tab 3).
        prompt (str): Refinement prompt. Recommended placeholder: {all_segments_content}.
            Also supports {segments_content}. Legacy placeholders
            ({segment_time}/{segment_title}/{segment_content}) are auto-adapted.
        tier (str): AI 档位，默认 "premium"（高档）。
        model_name (str): Model name for the provider.

    Returns:
        str: Refined segment text generated by the model.
    """
    # NOTE: This feature has not been fully end-to-end tested yet.
    # We will continue to iterate and fix issues found in real usage.

    # 检查输入文件
    if not os.path.exists(paragraphs_path):
        raise FileNotFoundError(f'段落内容文件 \'{paragraphs_path}\' 不存在')

    with open(paragraphs_path, 'r', encoding='utf-8') as f:
        paragraphs_content = f.read()

    segments = parse_segments_paragraphs_content(paragraphs_content)
    if not segments:
        raise ValueError('未能从输入文件中解析到有效分段，请确认文件为"提取段落内容"标签页输出格式')

    # Build one combined input so AI can refine all segments in a single request.
    combined_segments = []
    for idx, segment in enumerate(segments, start=1):
        segment_content = segment['content'] or '(此时间段内无字幕内容)'
        combined_segments.append(
            f"[分段{idx}]\n"
            f"分段时间戳：{segment['time_str']}\n"
            f"分段标题：{segment['title']}\n"
            f"分段内容：\n{segment_content}\n"
        )
    all_segments_content = '\n'.join(combined_segments).strip()

    full_prompt = prompt
    full_prompt = full_prompt.replace('{all_segments_content}', all_segments_content)
    full_prompt = full_prompt.replace('{segments_content}', all_segments_content)

    # Backward compatibility: if old per-segment placeholders are still used,
    # fall back to one-shot input with a safe default instruction.
    if any(token in full_prompt for token in ('{segment_time}', '{segment_title}', '{segment_content}')):
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
# ===================== 独立操作窗口（每个 Tab 拆为单窗口）=====================

def _open_router_manager_for(master):
    from router_manager import open_router_manager
    open_router_manager(master)

def _resolve_output(input_path, output_var, default_name):
    """若输出路径为相对路径，解析为与输入文件同目录的绝对路径并写回 StringVar。"""
    output_path = output_var.get()
    if not os.path.isabs(output_path):
        output_path = os.path.join(os.path.dirname(input_path), output_path)
        output_var.set(output_path)
    return output_path

def _ensure_dir(path):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d)


class SrtExtractSubtitlesApp(ToolBase):
    """Tab 1：提取字幕文字 — 独立窗口版。"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("提取字幕文字")
        master.geometry("800x500")

        self.srt_var = tk.StringVar()
        self.output_var = tk.StringVar(value="AllSubtitles.txt")
        self.status_var = tk.StringVar()

        if initial_file:
            self.srt_var.set(initial_file)
            self.output_var.set(os.path.join(os.path.dirname(initial_file), "AllSubtitles.txt"))

        self._build_ui()

    def _build_ui(self):
        master = self.master

        # 左右分栏
        left = tk.Frame(master)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=10, pady=10)
        right = tk.Frame(master)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(0, 10), pady=10)

        # 左侧控件
        tk.Label(left, text="SRT字幕文件:").grid(row=0, column=0, padx=5, pady=10, sticky="e")
        tk.Entry(left, textvariable=self.srt_var, width=40).grid(row=0, column=1, sticky="w")
        tk.Button(left, text="浏览", command=self._select_srt).grid(row=0, column=2, padx=10)

        tk.Label(left, text="输出文件:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(left, textvariable=self.output_var, width=40).grid(row=1, column=1, sticky="w")
        tk.Button(left, text="浏览", command=self._select_output).grid(row=1, column=2, padx=10)

        self._btn = tk.Button(left, text="提取字幕文字", command=self._run, width=20)
        self._btn.grid(row=2, column=1, pady=25)

        tk.Label(left, textvariable=self.status_var, fg="blue").grid(row=3, column=0, columnspan=3, pady=10)

        # 右侧预览
        hdr = tk.Frame(right)
        hdr.pack(fill=tk.X, pady=(0, 5))
        tk.Label(hdr, text="提取的字幕内容:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Button(hdr, text="拷贝内容", command=self._copy, width=12).pack(side=tk.RIGHT, padx=5)

        tf = tk.Frame(right)
        tf.pack(fill=tk.BOTH, expand=True)
        sy = tk.Scrollbar(tf)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        sx = tk.Scrollbar(tf, orient=tk.HORIZONTAL)
        sx.pack(side=tk.BOTTOM, fill=tk.X)
        self._text = tk.Text(tf, wrap=tk.WORD, yscrollcommand=sy.set,
                             xscrollcommand=sx.set, font=("Consolas", 10))
        self._text.pack(fill=tk.BOTH, expand=True)
        sy.config(command=self._text.yview)
        sx.config(command=self._text.xview)

    def _select_srt(self):
        path = filedialog.askopenfilename(title="选择SRT文件", filetypes=[("SRT files", "*.srt")])
        if path:
            self.srt_var.set(path)
            self.output_var.set(os.path.join(os.path.dirname(path), "AllSubtitles.txt"))

    def _select_output(self):
        path = filedialog.asksaveasfilename(title="选择输出文件", defaultextension=".txt",
                                            filetypes=[("Text files", "*.txt")])
        if path:
            self.output_var.set(path)

    def _run(self):
        srt_path = self.srt_var.get()
        if not srt_path or not os.path.exists(srt_path):
            self.status_var.set("⚠ 请选择有效的SRT文件")
            return
        output_path = _resolve_output(srt_path, self.output_var, "AllSubtitles.txt")
        try:
            _ensure_dir(output_path)
        except Exception as e:
            self.status_var.set(f"⚠ 无法创建输出目录: {e}")
            return

        self.status_var.set("正在提取...")
        self._btn.config(state="disabled")

        def _work():
            try:
                text = extract_all_subtitles(srt_path)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.status_var.set(f"✓ 完成: {os.path.basename(output_path)}")
                self.master.after(0, lambda: (self._text.delete("1.0", tk.END),
                                              self._text.insert("1.0", text)))
                self.set_done()
            except Exception as e:
                self.status_var.set(f"失败: {e}")
                self.set_error(f"提取全部字幕失败: {e}")
            finally:
                self.master.after(0, lambda: self._btn.config(state="normal"))

        self.set_busy()
        threading.Thread(target=_work, daemon=True).start()

    def _copy(self):
        content = self._text.get("1.0", tk.END).strip()
        if not content:
            self.status_var.set("没有可拷贝的内容")
            return
        self.master.clipboard_clear()
        self.master.clipboard_append(content)
        self.master.update()
        self.status_var.set("内容已拷贝到剪贴板 ✓")


class SrtGenerateSegmentsApp(ToolBase):
    """Tab 2：生成分段描述 — 独立窗口版。"""

    _DEFAULT_PROMPT = """\
# 生成时间戳分段

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

请根据以上字幕内容生成YouTube分段描述，格式为每行一个分段，格式为：时:分:秒 标题"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("生成分段描述")
        master.geometry("750x450")

        self.srt_var = tk.StringVar()
        self.output_var = tk.StringVar(value="subs.txt")
        self.status_var = tk.StringVar()

        if initial_file:
            self.srt_var.set(initial_file)
            self.output_var.set(os.path.join(os.path.dirname(initial_file), "subs.txt"))

        self._build_ui()

    def _build_ui(self):
        f = self.master
        tk.Label(f, text="AI 档位:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Label(f, text="高档 (Premium) — 最强模型", fg="#228B22",
                 font=("Arial", 9)).grid(row=0, column=1, sticky="w")
        tk.Button(f, text="AI Router 管理",
                  command=lambda: _open_router_manager_for(self.master)).grid(row=0, column=2, padx=10)

        tk.Label(f, text="SRT字幕文件:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        tk.Entry(f, textvariable=self.srt_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_srt).grid(row=1, column=2, padx=10)

        tk.Label(f, text="Prompt提示语:").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        self._prompt = tk.Text(f, height=8, width=50, wrap=tk.WORD)
        self._prompt.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0, 10))
        self._prompt.insert(tk.END, self._DEFAULT_PROMPT)

        tk.Label(f, text="输出文件:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        tk.Entry(f, textvariable=self.output_var, width=50).grid(row=3, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_output).grid(row=3, column=2, padx=10)

        self._btn = tk.Button(f, text="生成分段描述", command=self._run, width=20)
        self._btn.grid(row=4, column=1, pady=25)

        tk.Label(f, textvariable=self.status_var, fg="blue").grid(
            row=5, column=0, columnspan=3, pady=10)

    def _select_srt(self):
        path = filedialog.askopenfilename(title="选择SRT文件", filetypes=[("SRT files", "*.srt")])
        if path:
            self.srt_var.set(path)
            self.output_var.set(os.path.join(os.path.dirname(path), "subs.txt"))

    def _select_output(self):
        path = filedialog.asksaveasfilename(title="选择输出文件", defaultextension=".txt",
                                            filetypes=[("Text files", "*.txt")])
        if path:
            self.output_var.set(path)

    def _run(self):
        srt_path = self.srt_var.get()
        prompt = self._prompt.get("1.0", tk.END).strip()
        if not srt_path or not os.path.exists(srt_path):
            self.status_var.set("⚠ 请选择有效的SRT文件")
            return
        if not prompt:
            self.status_var.set("⚠ 请输入Prompt提示语")
            return
        output_path = _resolve_output(srt_path, self.output_var, "subs.txt")
        try:
            _ensure_dir(output_path)
        except Exception as e:
            self.status_var.set(f"⚠ 无法创建输出目录: {e}")
            return

        self.status_var.set("正在生成分段描述...")
        self._btn.config(state="disabled")

        def _work():
            try:
                result = srt_ops.generate_youtube_segments(srt_path, prompt=prompt)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(result)
                self.status_var.set("生成完成")
                logger.info(f"分段描述已生成 → {os.path.basename(output_path)}")
                self.set_done()
            except Exception as e:
                self.set_error(f"生成分段描述失败: {e}")
                self.status_var.set("生成失败")
            finally:
                self.master.after(0, lambda: self._btn.config(state="normal"))

        self.set_busy()
        threading.Thread(target=_work, daemon=True).start()


class SrtExtractParagraphsApp(ToolBase):
    """Tab 3：提取段落内容 — 独立窗口版。"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("提取段落内容")
        master.geometry("750x300")

        self.srt_var = tk.StringVar()
        self.segments_var = tk.StringVar()
        self.output_var = tk.StringVar(value="subs-segment.txt")
        self.status_var = tk.StringVar()

        if initial_file:
            self.srt_var.set(initial_file)
            self.output_var.set(os.path.join(os.path.dirname(initial_file), "subs-segment.txt"))

        self._build_ui()

    def _build_ui(self):
        f = self.master
        tk.Label(f, text="SRT字幕文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Entry(f, textvariable=self.srt_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_srt).grid(row=0, column=2, padx=10)

        tk.Label(f, text="时间戳分割文件:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        tk.Entry(f, textvariable=self.segments_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_segments).grid(row=1, column=2, padx=10)

        tk.Label(f, text="输出文件:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        tk.Entry(f, textvariable=self.output_var, width=50).grid(row=2, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_output).grid(row=2, column=2, padx=10)

        self._btn = tk.Button(f, text="提取段落内容", command=self._run, width=20)
        self._btn.grid(row=3, column=1, pady=25)

        tk.Label(f, textvariable=self.status_var, fg="blue").grid(
            row=4, column=0, columnspan=3, pady=10)

    def _select_srt(self):
        path = filedialog.askopenfilename(title="选择SRT文件", filetypes=[("SRT files", "*.srt")])
        if path:
            self.srt_var.set(path)
            self.output_var.set(os.path.join(os.path.dirname(path), "subs-segment.txt"))

    def _select_segments(self):
        path = filedialog.askopenfilename(title="选择时间戳分割文件",
                                          filetypes=[("Text files", "*.txt")])
        if path:
            self.segments_var.set(path)

    def _select_output(self):
        path = filedialog.asksaveasfilename(title="选择输出文件", defaultextension=".txt",
                                            filetypes=[("Text files", "*.txt")])
        if path:
            self.output_var.set(path)

    def _run(self):
        srt_path = self.srt_var.get()
        segments_path = self.segments_var.get()
        if not srt_path or not os.path.exists(srt_path):
            self.status_var.set("⚠ 请选择有效的SRT文件")
            return
        if not segments_path or not os.path.exists(segments_path):
            self.status_var.set("⚠ 请选择有效的时间戳分割文件")
            return
        output_path = _resolve_output(srt_path, self.output_var, "subs-segment.txt")
        try:
            _ensure_dir(output_path)
        except Exception as e:
            self.status_var.set(f"⚠ 无法创建输出目录: {e}")
            return

        self.status_var.set("正在提取段落内容...")
        self._btn.config(state="disabled")

        def _work():
            try:
                result = srt_ops.extract_paragraphs_from_segments(srt_path, segments_path)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(result)
                self.status_var.set("提取完成")
                logger.info(f"段落内容已提取 → {os.path.basename(output_path)}")
                self.set_done()
            except Exception as e:
                self.set_error(f"提取段落失败: {e}")
                self.status_var.set("提取失败")
            finally:
                self.master.after(0, lambda: self._btn.config(state="normal"))

        self.set_busy()
        threading.Thread(target=_work, daemon=True).start()


class SrtRefineSegmentsApp(ToolBase):
    """Tab 4：精炼分段 — 独立窗口版。"""

    _DEFAULT_PROMPT = """\
## 精炼全部分段

【
请一次性对全部分段内容进行总结提炼，每个段落提炼后不超过128个字。
对于问答段落，保留精炼后的问题和回答，保持问答说话人的视角，不要改为第三方转述。
输出格式为：
时间戳 标题
精炼内容

分段之间空一行，不要添加解释。
】

以下是全部分段内容：
{all_segments_content}
"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("精炼分段")
        master.geometry("750x430")

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar(value="subs-segment-refined.txt")
        self.status_var = tk.StringVar()

        if initial_file:
            self.input_var.set(initial_file)
            self.output_var.set(
                os.path.join(os.path.dirname(initial_file), "subs-segment-refined.txt"))

        self._build_ui()

    def _build_ui(self):
        f = self.master
        tk.Label(f, text="段落内容文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Entry(f, textvariable=self.input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_input).grid(row=0, column=2, padx=10)

        tk.Label(f, text="AI 档位:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        tk.Label(f, text="高档 (Premium) — 最强模型", fg="#228B22",
                 font=("Arial", 9)).grid(row=1, column=1, sticky="w")
        tk.Button(f, text="AI Router 管理",
                  command=lambda: _open_router_manager_for(self.master)).grid(row=1, column=2, padx=10)

        tk.Label(f, text="Prompt提示语:").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        self._prompt = tk.Text(f, height=8, width=50, wrap=tk.WORD)
        self._prompt.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0, 10))
        self._prompt.insert(tk.END, self._DEFAULT_PROMPT)

        tk.Label(f, text="输出文件:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        tk.Entry(f, textvariable=self.output_var, width=50).grid(row=3, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_output).grid(row=3, column=2, padx=10)

        self._btn = tk.Button(f, text="精炼分段描述", command=self._run, width=20)
        self._btn.grid(row=4, column=1, pady=25)

        tk.Label(f, textvariable=self.status_var, fg="blue").grid(
            row=5, column=0, columnspan=3, pady=10)

    def _select_input(self):
        path = filedialog.askopenfilename(title="选择段落内容文件",
                                          filetypes=[("Text files", "*.txt")])
        if path:
            self.input_var.set(path)
            self.output_var.set(
                os.path.join(os.path.dirname(path), "subs-segment-refined.txt"))

    def _select_output(self):
        path = filedialog.asksaveasfilename(title="选择输出文件", defaultextension=".txt",
                                            filetypes=[("Text files", "*.txt")])
        if path:
            self.output_var.set(path)

    def _run(self):
        input_path = self.input_var.get()
        prompt = self._prompt.get("1.0", tk.END).strip()
        if not input_path or not os.path.exists(input_path):
            self.status_var.set("⚠ 请选择有效的段落内容文件")
            return
        if not prompt:
            self.status_var.set("⚠ 请输入Prompt提示语")
            return
        output_path = _resolve_output(input_path, self.output_var, "subs-segment-refined.txt")
        try:
            _ensure_dir(output_path)
        except Exception as e:
            self.status_var.set(f"⚠ 无法创建输出目录: {e}")
            return

        self.status_var.set("正在精炼分段描述...")
        self._btn.config(state="disabled")

        def _work():
            try:
                result = srt_ops.refine_segment_descriptions(input_path, prompt)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(result)
                self.status_var.set("精炼完成")
                logger.info(f"精炼分段内容已保存 → {os.path.basename(output_path)}")
                self.set_done()
            except Exception as e:
                self.set_error(f"精炼分段失败: {e}")
                self.status_var.set("精炼失败")
            finally:
                self.master.after(0, lambda: self._btn.config(state="normal"))

        self.set_busy()
        threading.Thread(target=_work, daemon=True).start()


class SrtGenerateTitlesApp(ToolBase):
    """Tab 5：生成标题 — 独立窗口版。"""

    _DEFAULT_PROMPT = """\
## 生成标题

【
给这个视频起个合适的名字，新闻性十足、概括核心焦点，稍微长些没关系

】"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("生成标题")
        master.geometry("750x380")

        self.subs_var = tk.StringVar()
        self.output_var = tk.StringVar(value="titles.txt")
        self.status_var = tk.StringVar()

        if initial_file:
            self.subs_var.set(initial_file)
            self.output_var.set(os.path.join(os.path.dirname(initial_file), "titles.txt"))

        self._build_ui()

    def _build_ui(self):
        f = self.master
        tk.Label(f, text="Subs文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Entry(f, textvariable=self.subs_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_subs).grid(row=0, column=2, padx=10)

        tk.Label(f, text="AI 档位:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        tk.Label(f, text="高档 (Premium) — 最强模型", fg="#228B22",
                 font=("Arial", 9)).grid(row=1, column=1, sticky="w")
        tk.Button(f, text="AI Router 管理",
                  command=lambda: _open_router_manager_for(self.master)).grid(row=1, column=2, padx=10)

        tk.Label(f, text="Prompt提示语:").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        self._prompt = tk.Text(f, height=6, width=50, wrap=tk.WORD)
        self._prompt.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0, 10))
        self._prompt.insert(tk.END, self._DEFAULT_PROMPT)

        tk.Label(f, text="输出文件:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        tk.Entry(f, textvariable=self.output_var, width=50).grid(row=3, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_output).grid(row=3, column=2, padx=10)

        self._btn = tk.Button(f, text="生成标题", command=self._run, width=20)
        self._btn.grid(row=4, column=1, pady=25)

        tk.Label(f, textvariable=self.status_var, fg="blue").grid(
            row=5, column=0, columnspan=3, pady=10)

    def _select_subs(self):
        path = filedialog.askopenfilename(title="选择Subs文件",
                                          filetypes=[("Text files", "*.txt")])
        if path:
            self.subs_var.set(path)
            self.output_var.set(os.path.join(os.path.dirname(path), "titles.txt"))

    def _select_output(self):
        path = filedialog.asksaveasfilename(title="选择输出文件", defaultextension=".txt",
                                            filetypes=[("Text files", "*.txt")])
        if path:
            self.output_var.set(path)

    def _run(self):
        subs_path = self.subs_var.get()
        prompt = self._prompt.get("1.0", tk.END).strip()
        if not subs_path or not os.path.exists(subs_path):
            self.status_var.set("⚠ 请选择有效的Subs文件")
            return
        if not prompt:
            self.status_var.set("⚠ 请输入Prompt提示语")
            return
        output_path = _resolve_output(subs_path, self.output_var, "titles.txt")
        try:
            _ensure_dir(output_path)
        except Exception as e:
            self.status_var.set(f"⚠ 无法创建输出目录: {e}")
            return

        self.status_var.set("正在生成标题...")
        self._btn.config(state="disabled")

        def _work():
            try:
                result = srt_ops.generate_video_titles(subs_path, prompt)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(result)
                self.status_var.set("生成完成")
                logger.info(f"视频标题已生成 → {os.path.basename(output_path)}")
                self.set_done()
            except Exception as e:
                self.set_error(f"生成标题失败: {e}")
                self.status_var.set("生成失败")
            finally:
                self.master.after(0, lambda: self._btn.config(state="normal"))

        self.set_busy()
        threading.Thread(target=_work, daemon=True).start()


# ===================== GUI 主界面 =====================
class YouTubeSegmentsApp(ToolBase):
    def __init__(self, master):
        self.master = master
        master.title("YouTube工具箱")
        master.geometry("750x450")
        master.resizable(False, False)

        # 创建标签页
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # 字幕提取标签页（使用频度最高，放在第一位）
        self.create_subtitles_tab()

        # 分段生成标签页
        self.create_segments_tab()

        # 段落提取标签页
        self.create_paragraphs_tab()

        # 分段精炼标签页
        self.create_refine_tab()

        # 标题生成标签页
        self.create_titles_tab()

    def create_segments_tab(self):
        """创建分段生成标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="生成分段描述")

        # AI 档位信息
        tk.Label(tab, text="AI 档位:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Label(tab, text="高档 (Premium) — 最强模型", fg="#228B22", font=("Arial", 9)).grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="AI Router 管理", command=self._open_router_manager).grid(row=0, column=2, padx=10)

        # SRT文件选择
        tk.Label(tab, text="SRT字幕文件:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.srt_path_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.srt_path_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_srt).grid(row=1, column=2, padx=10)

        # Prompt编辑
        tk.Label(tab, text="Prompt提示语:").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        self.segments_prompt_text = tk.Text(tab, height=8, width=50, wrap=tk.WORD)
        self.segments_prompt_text.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0,10))
        # 设置默认prompt
        default_segments_prompt = """# 生成时间戳分段

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

请根据以上字幕内容生成YouTube分段描述，格式为每行一个分段，格式为：时:分:秒 标题"""
        self.segments_prompt_text.insert(tk.END, default_segments_prompt)

        # 输出文件选择
        tk.Label(tab, text="输出文件:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        self.output_path_var = tk.StringVar(value="subs.txt")
        tk.Entry(tab, textvariable=self.output_path_var, width=50).grid(row=3, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_output).grid(row=3, column=2, padx=10)

        # 生成按钮
        self.generate_btn = tk.Button(tab, text="生成分段描述", command=self.generate_segments, width=20)
        self.generate_btn.grid(row=4, column=1, pady=25)

        # 进度/提示
        self.status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.status_var, fg="blue").grid(row=5, column=0, columnspan=3, pady=10)

    def create_paragraphs_tab(self):
        """创建段落提取标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="提取段落内容")

        # SRT文件选择
        tk.Label(tab, text="SRT字幕文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.paragraphs_srt_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.paragraphs_srt_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_paragraphs_srt).grid(row=0, column=2, padx=10)

        # 时间戳分割文件选择
        tk.Label(tab, text="时间戳分割文件:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.segments_file_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.segments_file_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_segments_file).grid(row=1, column=2, padx=10)

        # 输出文件选择
        tk.Label(tab, text="输出文件:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.paragraphs_output_var = tk.StringVar(value="subs-segment.txt")
        tk.Entry(tab, textvariable=self.paragraphs_output_var, width=50).grid(row=2, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_paragraphs_output).grid(row=2, column=2, padx=10)

        # 提取按钮
        self.extract_btn = tk.Button(tab, text="提取段落内容", command=self.extract_paragraphs, width=20)
        self.extract_btn.grid(row=3, column=1, pady=25)

        # 进度/提示
        self.paragraphs_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.paragraphs_status_var, fg="blue").grid(row=4, column=0, columnspan=3, pady=10)

    def create_titles_tab(self):
        """创建标题生成标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="生成标题")

        # Subs文件选择
        tk.Label(tab, text="Subs文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.titles_subs_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.titles_subs_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_titles_subs).grid(row=0, column=2, padx=10)

        # AI 档位信息
        tk.Label(tab, text="AI 档位:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        tk.Label(tab, text="高档 (Premium) — 最强模型", fg="#228B22", font=("Arial", 9)).grid(row=1, column=1, sticky="w")
        tk.Button(tab, text="AI Router 管理", command=self._open_router_manager).grid(row=1, column=2, padx=10)

        # Prompt编辑
        tk.Label(tab, text="Prompt提示语:").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        self.prompt_text = tk.Text(tab, height=6, width=50, wrap=tk.WORD)
        self.prompt_text.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0,10))
        # 设置默认prompt
        default_prompt = """## 生成标题

【
给这个视频起个合适的名字，新闻性十足、概括核心焦点，稍微长些没关系

】"""
        self.prompt_text.insert(tk.END, default_prompt)

        # 输出文件选择
        tk.Label(tab, text="输出文件:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        self.titles_output_var = tk.StringVar(value="titles.txt")
        tk.Entry(tab, textvariable=self.titles_output_var, width=50).grid(row=3, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_titles_output).grid(row=3, column=2, padx=10)

        # 生成按钮
        self.titles_btn = tk.Button(tab, text="生成标题", command=self.generate_titles, width=20)
        self.titles_btn.grid(row=4, column=1, pady=25)

        # 进度/提示
        self.titles_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.titles_status_var, fg="blue").grid(row=5, column=0, columnspan=3, pady=10)

    def create_refine_tab(self):
        """创建分段精炼标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="精炼分段")

        # Input paragraph file picker (expects output from Tab 3)
        tk.Label(tab, text="段落内容文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.refine_input_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.refine_input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_refine_input).grid(row=0, column=2, padx=10)

        # AI 档位信息
        tk.Label(tab, text="AI 档位:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        tk.Label(tab, text="高档 (Premium) — 最强模型", fg="#228B22", font=("Arial", 9)).grid(row=1, column=1, sticky="w")
        tk.Button(tab, text="AI Router 管理", command=self._open_router_manager).grid(row=1, column=2, padx=10)

        # Prompt编辑
        tk.Label(tab, text="Prompt提示语:").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        self.refine_prompt_text = tk.Text(tab, height=8, width=50, wrap=tk.WORD)
        self.refine_prompt_text.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0,10))

        default_refine_prompt = """## 精炼全部分段

【
请一次性对全部分段内容进行总结提炼，每个段落提炼后不超过128个字。
对于问答段落，保留精炼后的问题和回答，保持问答说话人的视角，不要改为第三方转述。
输出格式为：
时间戳 标题
精炼内容

分段之间空一行，不要添加解释。
】

以下是全部分段内容：
{all_segments_content}
"""
        self.refine_prompt_text.insert(tk.END, default_refine_prompt)

        # Output file picker
        tk.Label(tab, text="输出文件:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        self.refine_output_var = tk.StringVar(value="subs-segment-refined.txt")
        tk.Entry(tab, textvariable=self.refine_output_var, width=50).grid(row=3, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_refine_output).grid(row=3, column=2, padx=10)

        # Run refinement
        self.refine_btn = tk.Button(tab, text="精炼分段描述", command=self.refine_segments, width=20)
        self.refine_btn.grid(row=4, column=1, pady=25)

        # 进度/提示
        self.refine_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.refine_status_var, fg="blue").grid(row=5, column=0, columnspan=3, pady=10)

    def create_subtitles_tab(self):
        """创建字幕提取标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="提取字幕文字")

        # 创建左右分栏框架
        left_frame = tk.Frame(tab)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=10, pady=10)

        right_frame = tk.Frame(tab)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(0, 10), pady=10)

        # 左侧控制区域
        # SRT文件选择
        tk.Label(left_frame, text="SRT字幕文件:").grid(row=0, column=0, padx=5, pady=10, sticky="e")
        self.subtitles_srt_var = tk.StringVar()
        tk.Entry(left_frame, textvariable=self.subtitles_srt_var, width=40).grid(row=0, column=1, sticky="w")
        tk.Button(left_frame, text="浏览", command=self.select_subtitles_srt).grid(row=0, column=2, padx=10)

        # 输出文件选择
        tk.Label(left_frame, text="输出文件:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.subtitles_output_var = tk.StringVar(value="AllSubtitles.txt")
        tk.Entry(left_frame, textvariable=self.subtitles_output_var, width=40).grid(row=1, column=1, sticky="w")
        tk.Button(left_frame, text="浏览", command=self.select_subtitles_output).grid(row=1, column=2, padx=10)

        # 提取按钮
        self.subtitles_btn = tk.Button(left_frame, text="提取字幕文字", command=self.extract_subtitles, width=20)
        self.subtitles_btn.grid(row=2, column=1, pady=25)

        # 进度/提示
        self.subtitles_status_var = tk.StringVar()
        tk.Label(left_frame, textvariable=self.subtitles_status_var, fg="blue").grid(row=3, column=0, columnspan=3, pady=10)

        # 右侧显示区域
        # 标题和拷贝按钮框架
        header_frame = tk.Frame(right_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(header_frame, text="提取的字幕内容:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Button(header_frame, text="拷贝内容", command=self.copy_subtitles, width=12).pack(side=tk.RIGHT, padx=5)
        
        # 创建带滚动条的文本框
        text_frame = tk.Frame(right_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # 垂直滚动条
        scrollbar_y = tk.Scrollbar(text_frame)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 水平滚动条
        scrollbar_x = tk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 文本框
        self.subtitles_text_display = tk.Text(text_frame, wrap=tk.WORD, 
                                              yscrollcommand=scrollbar_y.set,
                                              xscrollcommand=scrollbar_x.set,
                                              font=("Consolas", 10))
        self.subtitles_text_display.pack(fill=tk.BOTH, expand=True)
        
        # 配置滚动条
        scrollbar_y.config(command=self.subtitles_text_display.yview)
        scrollbar_x.config(command=self.subtitles_text_display.xview)

    def _open_router_manager(self):
        """打开 AI Router 管理界面。"""
        from router_manager import open_router_manager
        open_router_manager(self.master)

    def select_srt(self):
        path = filedialog.askopenfilename(title="选择SRT文件", filetypes=[("SRT files", "*.srt")])
        if path:
            self.srt_path_var.set(path)
            # 自动设置默认输出文件名
            dir_path = os.path.dirname(path)
            default_output = os.path.join(dir_path, "subs.txt")
            self.output_path_var.set(default_output)

    def select_output(self):
        path = filedialog.asksaveasfilename(title="选择输出文件", defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if path:
            self.output_path_var.set(path)

    def generate_segments(self):
        srt_path = self.srt_path_var.get()
        output_path = self.output_path_var.get()
        prompt = self.segments_prompt_text.get("1.0", tk.END).strip()
        
        if not srt_path or not os.path.exists(srt_path):
            self.status_var.set("⚠ 请选择有效的SRT文件")
            return

        if not output_path:
            self.status_var.set("⚠ 请选择输出文件路径")
            return

        if not prompt:
            self.status_var.set("⚠ 请输入Prompt提示语")
            return

        # 如果输出路径不是绝对路径，设置为与SRT文件同目录
        if not os.path.isabs(output_path):
            srt_dir = os.path.dirname(srt_path)
            output_path = os.path.join(srt_dir, output_path)
            self.output_path_var.set(output_path)

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                self.status_var.set(f"⚠ 无法创建输出目录: {e}")
                return

        self.status_var.set("正在生成分段描述...")
        self.generate_btn.config(state="disabled")
        self.master.update()

        # 在后台线程中运行生成任务
        def run_generation():
            try:
                segments = generate_youtube_segments(srt_path, prompt=prompt)

                # 保存到用户指定的文件
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(segments)

                # 验证文件是否成功创建
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.status_var.set("生成完成")
                    logger.info(f"分段描述已生成 → {os.path.basename(output_path)}")
                    self.set_done()
                else:
                    raise Exception("文件创建失败或文件为空")

            except Exception as e:
                self.set_error(f"生成分段描述失败: {e}")
                self.status_var.set("生成失败")
            finally:
                self.master.after(0, lambda: self.generate_btn.config(state="normal"))

        self.set_busy()
        threading.Thread(target=run_generation, daemon=True).start()

    def select_paragraphs_srt(self):
        path = filedialog.askopenfilename(title="选择SRT文件", filetypes=[("SRT files", "*.srt")])
        if path:
            self.paragraphs_srt_var.set(path)
            # 自动设置默认输出文件名
            dir_path = os.path.dirname(path)
            default_output = os.path.join(dir_path, "subs-segment.txt")
            self.paragraphs_output_var.set(default_output)

    def select_segments_file(self):
        path = filedialog.askopenfilename(title="选择时间戳分割文件", filetypes=[("Text files", "*.txt")])
        if path:
            self.segments_file_var.set(path)

    def select_paragraphs_output(self):
        path = filedialog.asksaveasfilename(title="选择输出文件", defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if path:
            self.paragraphs_output_var.set(path)

    def extract_paragraphs(self):
        srt_path = self.paragraphs_srt_var.get()
        segments_path = self.segments_file_var.get()
        output_path = self.paragraphs_output_var.get()

        if not srt_path or not os.path.exists(srt_path):
            self.paragraphs_status_var.set("⚠ 请选择有效的SRT文件")
            return

        if not segments_path or not os.path.exists(segments_path):
            self.paragraphs_status_var.set("⚠ 请选择有效的时间戳分割文件")
            return

        if not output_path:
            self.paragraphs_status_var.set("⚠ 请选择输出文件路径")
            return

        # 如果输出路径不是绝对路径，设置为与SRT文件同目录
        if not os.path.isabs(output_path):
            srt_dir = os.path.dirname(srt_path)
            output_path = os.path.join(srt_dir, output_path)
            self.paragraphs_output_var.set(output_path)

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                self.paragraphs_status_var.set(f"⚠ 无法创建输出目录: {e}")
                return

        self.paragraphs_status_var.set("正在提取段落内容...")
        self.extract_btn.config(state="disabled")
        self.master.update()

        # 在后台线程中运行提取任务
        def run_extraction():
            try:
                paragraphs = extract_paragraphs_from_segments(srt_path, segments_path)

                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(paragraphs)

                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.paragraphs_status_var.set("提取完成")
                    logger.info(f"段落内容已提取 → {os.path.basename(output_path)}")
                    self.set_done()
                else:
                    raise Exception("文件创建失败或文件为空")

            except Exception as e:
                self.set_error(f"提取段落失败: {e}")
                self.paragraphs_status_var.set("提取失败")
            finally:
                self.master.after(0, lambda: self.extract_btn.config(state="normal"))

        self.set_busy()
        threading.Thread(target=run_extraction, daemon=True).start()

    def select_titles_subs(self):
        path = filedialog.askopenfilename(title="选择Subs文件", filetypes=[("Text files", "*.txt")])
        if path:
            self.titles_subs_var.set(path)
            # 自动设置默认输出文件名
            dir_path = os.path.dirname(path)
            default_output = os.path.join(dir_path, "titles.txt")
            self.titles_output_var.set(default_output)

    def select_refine_input(self):
        path = filedialog.askopenfilename(title="选择段落内容文件", filetypes=[("Text files", "*.txt")])
        if path:
            self.refine_input_var.set(path)
            # 自动设置默认输出文件名
            dir_path = os.path.dirname(path)
            default_output = os.path.join(dir_path, "subs-segment-refined.txt")
            self.refine_output_var.set(default_output)

    def select_refine_output(self):
        path = filedialog.asksaveasfilename(title="选择输出文件", defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if path:
            self.refine_output_var.set(path)

    def refine_segments(self):
        input_path = self.refine_input_var.get()
        output_path = self.refine_output_var.get()
        prompt = self.refine_prompt_text.get("1.0", tk.END).strip()

        if not input_path or not os.path.exists(input_path):
            self.refine_status_var.set("⚠ 请选择有效的段落内容文件")
            return

        if not output_path:
            self.refine_status_var.set("⚠ 请选择输出文件路径")
            return

        if not prompt:
            self.refine_status_var.set("⚠ 请输入Prompt提示语")
            return

        # 如果输出路径不是绝对路径，设置为与输入文件同目录
        if not os.path.isabs(output_path):
            input_dir = os.path.dirname(input_path)
            output_path = os.path.join(input_dir, output_path)
            self.refine_output_var.set(output_path)

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                self.refine_status_var.set(f"⚠ 无法创建输出目录: {e}")
                return

        self.refine_status_var.set("正在精炼分段描述...")
        self.refine_btn.config(state="disabled")
        self.master.update()

        # Run in background thread to keep GUI responsive.
        def run_refinement():
            try:
                refined_text = refine_segment_descriptions(input_path, prompt)

                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(refined_text)

                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.refine_status_var.set("精炼完成")
                    logger.info(f"精炼分段内容已保存 → {os.path.basename(output_path)}")
                    self.set_done()
                else:
                    raise Exception("文件创建失败或文件为空")

            except Exception as e:
                self.set_error(f"精炼分段失败: {e}")
                self.refine_status_var.set("精炼失败")
            finally:
                self.master.after(0, lambda: self.refine_btn.config(state="normal"))

        self.set_busy()
        threading.Thread(target=run_refinement, daemon=True).start()

    def select_titles_output(self):
        path = filedialog.asksaveasfilename(title="选择输出文件", defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if path:
            self.titles_output_var.set(path)

    def generate_titles(self):
        subs_path = self.titles_subs_var.get()
        output_path = self.titles_output_var.get()
        prompt = self.prompt_text.get("1.0", tk.END).strip()

        if not subs_path or not os.path.exists(subs_path):
            self.titles_status_var.set("⚠ 请选择有效的Subs文件")
            return

        if not output_path:
            self.titles_status_var.set("⚠ 请选择输出文件路径")
            return

        if not prompt:
            self.titles_status_var.set("⚠ 请输入Prompt提示语")
            return

        # 如果输出路径不是绝对路径，设置为与Subs文件同目录
        if not os.path.isabs(output_path):
            subs_dir = os.path.dirname(subs_path)
            output_path = os.path.join(subs_dir, output_path)
            self.titles_output_var.set(output_path)

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                self.titles_status_var.set(f"⚠ 无法创建输出目录: {e}")
                return

        self.titles_status_var.set("正在生成标题...")
        self.titles_btn.config(state="disabled")
        self.master.update()

        # 在后台线程中运行生成任务
        def run_title_generation():
            try:
                titles = generate_video_titles(subs_path, prompt)

                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(titles)

                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.titles_status_var.set("生成完成")
                    logger.info(f"视频标题已生成 → {os.path.basename(output_path)}")
                    self.set_done()
                else:
                    raise Exception("文件创建失败或文件为空")

            except Exception as e:
                self.set_error(f"生成标题失败: {e}")
                self.titles_status_var.set("生成失败")
            finally:
                self.master.after(0, lambda: self.titles_btn.config(state="normal"))

        self.set_busy()
        threading.Thread(target=run_title_generation, daemon=True).start()

    def select_subtitles_srt(self):
        path = filedialog.askopenfilename(title="选择SRT文件", filetypes=[("SRT files", "*.srt")])
        if path:
            self.subtitles_srt_var.set(path)
            # 自动设置默认输出文件名
            dir_path = os.path.dirname(path)
            default_output = os.path.join(dir_path, "AllSubtitles.txt")
            self.subtitles_output_var.set(default_output)

    def select_subtitles_output(self):
        path = filedialog.asksaveasfilename(title="选择输出文件", defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if path:
            self.subtitles_output_var.set(path)

    def extract_subtitles(self):
        srt_path = self.subtitles_srt_var.get()
        output_path = self.subtitles_output_var.get()

        if not srt_path or not os.path.exists(srt_path):
            self.subtitles_status_var.set("⚠ 请选择有效的SRT文件")
            return

        if not output_path:
            self.subtitles_status_var.set("⚠ 请选择输出文件路径")
            return

        # 如果输出路径不是绝对路径，设置为与SRT文件同目录
        if not os.path.isabs(output_path):
            srt_dir = os.path.dirname(srt_path)
            output_path = os.path.join(srt_dir, output_path)
            self.subtitles_output_var.set(output_path)

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                self.subtitles_status_var.set(f"⚠ 无法创建输出目录: {e}")
                return

        self.subtitles_status_var.set("正在提取字幕文字...")
        self.subtitles_btn.config(state="disabled")
        self.master.update()

        # 在后台线程中运行提取任务
        def run_subtitle_extraction():
            try:
                subtitles_text = extract_all_subtitles(srt_path)

                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(subtitles_text)

                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    output_filename = os.path.basename(output_path)
                    self.subtitles_status_var.set(f"✓ 提取完成，已保存到: {output_filename}")
                    self.master.after(0, self.display_subtitles_content, subtitles_text)
                    self.set_done()
                else:
                    raise Exception("文件创建失败或文件为空")

            except Exception as e:
                self.subtitles_status_var.set(f"提取失败: {e}")
                self.set_error(f"提取全部字幕失败: {e}")
            finally:
                self.master.after(0, lambda: self.subtitles_btn.config(state="normal"))

        self.set_busy()
        threading.Thread(target=run_subtitle_extraction, daemon=True).start()

    def display_subtitles_content(self, content):
        """在右侧文本框中显示字幕内容"""
        self.subtitles_text_display.delete("1.0", tk.END)
        self.subtitles_text_display.insert("1.0", content)

    def copy_subtitles(self):
        """将字幕内容拷贝到剪贴板"""
        try:
            content = self.subtitles_text_display.get("1.0", tk.END).strip()
            if not content:
                self.subtitles_status_var.set("没有可拷贝的内容")
                return
            
            # 清空剪贴板并设置新内容
            self.master.clipboard_clear()
            self.master.clipboard_append(content)
            self.master.update()  # 确保剪贴板更新
            
            self.subtitles_status_var.set("内容已拷贝到剪贴板 ✓")
        except Exception as e:
            self.subtitles_status_var.set(f"拷贝失败: {e}")

def main():
    # 启动GUI界面
    root = tk.Tk()
    app = YouTubeSegmentsApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
