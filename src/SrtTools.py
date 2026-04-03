import os
import re
import srt
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from datetime import datetime

# ===================== Multi-AI Provider Configuration =====================

def _keys_dir():
    """Return the path to the keys/ directory next to src/."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'keys')

AI_PROVIDERS = {
    "Gemini": {
        "type": "gemini",
        "key_file": "Gemini.key",
        "models": [
            {"id": "gemini-2.5-pro",        "label": "Gemini 2.5 Pro (最强)"},
            {"id": "gemini-2.5-flash",      "label": "Gemini 2.5 Flash (快速)"},
            {"id": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite (经济)"},
        ],
        "default_model": "gemini-2.5-flash",
    },
    "Groq": {
        "type": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "key_file": "Groq.key",
        "models": [
            {"id": "openai/gpt-oss-120b",                       "label": "GPT-OSS 120B (最强,推荐)"},
            {"id": "llama-3.3-70b-versatile",                    "label": "Llama 3.3 70B (稳定)"},
            {"id": "openai/gpt-oss-20b",                         "label": "GPT-OSS 20B (极速)"},
            {"id": "qwen/qwen3-32b",                             "label": "Qwen3 32B (Preview)"},
            {"id": "meta-llama/llama-4-scout-17b-16e-instruct",  "label": "Llama 4 Scout 17B (Preview)"},
            {"id": "llama-3.1-8b-instant",                       "label": "Llama 3.1 8B (轻量)"},
        ],
        "default_model": "openai/gpt-oss-120b",
    },
    "DeepSeek": {
        "type": "openai_compatible",
        "base_url": "https://api.deepseek.com",
        "key_file": "DeepSeek.key",
        "models": [
            {"id": "deepseek-chat",     "label": "DeepSeek V3.2 (通用)"},
            {"id": "deepseek-reasoner", "label": "DeepSeek V3.2 推理 (Thinking)"},
        ],
        "default_model": "deepseek-chat",
    },
    "自定义(OpenAI兼容)": {
        "type": "openai_compatible",
        "base_url": "",
        "key_file": "Custom.key",
        "models": [],
        "default_model": "",
    },
}

def _read_api_key(provider_name):
    """Read API key from the provider's key file. Returns (key, error_msg)."""
    provider = AI_PROVIDERS[provider_name]
    key_path = os.path.join(_keys_dir(), provider["key_file"])
    if not os.path.exists(key_path):
        return None, f"API Key 文件不存在: {provider['key_file']}\n请先在「管理Key」中配置"
    with open(key_path, 'r', encoding='utf-8') as f:
        key = f.read().strip()
    if not key:
        return None, f"API Key 为空: {provider['key_file']}"
    return key, None

def ai_generate(provider_name, model_id, prompt):
    """
    Unified AI generation entry point — delegates to the central AI Router.
    Supports Gemini (native SDK) and OpenAI-compatible providers.
    Returns the generated text string.
    """
    from ai_router import router
    return router.complete(prompt, provider=provider_name, model=model_id)

# ===================== Business Logic Functions =====================

def generate_youtube_segments(srt_path, provider_name='Gemini', model_name='gemini-2.5-flash', prompt=None):
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

    with open(srt_path, 'r', encoding='utf-8') as f:
        subs = list(srt.parse(f))

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
    try:
        segments = ai_generate(provider_name, model_name, prompt)
        return segments
    except Exception as e:
        raise RuntimeError(f'调用AI生成失败 ({provider_name}/{model_name}): {e}')

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
    with open(srt_path, 'r', encoding='utf-8') as f:
        subs = list(srt.parse(f))

    # 读取时间戳分割文件
    with open(segments_path, 'r', encoding='utf-8') as f:
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

def generate_video_titles(subs_path, prompt, provider_name='Gemini', model_name='gemini-2.5-flash'):
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
    with open(subs_path, 'r', encoding='utf-8') as f:
        subs_content = f.read()

    # 构建完整的prompt
    full_prompt = f"{prompt}\n\n以下是视频的分段描述内容：\n\n{subs_content}\n\n请根据以上内容生成合适的视频标题。"

    # 调用AI生成
    try:
        titles = ai_generate(provider_name, model_name, full_prompt)
        return titles
    except Exception as e:
        raise RuntimeError(f'调用AI生成失败 ({provider_name}/{model_name}): {e}')

def extract_all_subtitles(srt_path):
    """
    从SRT文件中提取所有字幕文字，每条字幕一行

    Args:
        srt_path (str): SRT文件路径

    Returns:
        str: 提取的字幕文字，每行一条
    """
    # 读取并解析SRT文件
    with open(srt_path, 'r', encoding='utf-8') as f:
        subs = list(srt.parse(f))

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

def refine_segment_descriptions(paragraphs_path, prompt, provider_name='Gemini', model_name='gemini-2.5-flash'):
    """
    Refine all segments generated by Tab 3 in one AI request.

    Args:
        paragraphs_path (str): Input paragraph file path (output from Tab 3).
        prompt (str): Refinement prompt. Recommended placeholder: {all_segments_content}.
            Also supports {segments_content}. Legacy placeholders
            ({segment_time}/{segment_title}/{segment_content}) are auto-adapted.
        provider_name (str): AI provider name (key in AI_PROVIDERS).
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

    refined_text = ai_generate(provider_name, model_name, full_prompt)

    if not refined_text:
        raise RuntimeError('AI返回为空，未生成精炼结果')

    return refined_text
# ===================== GUI 主界面 =====================
class YouTubeSegmentsApp:
    def __init__(self, master):
        self.master = master
        master.title("YouTube工具箱（多AI提供商）")
        master.geometry("750x450")
        master.resizable(False, False)

        # Provider / model state
        self.provider_var = tk.StringVar(value=list(AI_PROVIDERS.keys())[0])
        self.model_var = tk.StringVar()
        self._sync_model_list()  # populate model list for initial provider

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

        # AI 提供商选择
        tk.Label(tab, text="AI 提供商:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.provider_combo = ttk.Combobox(tab, textvariable=self.provider_var,
                                           values=list(AI_PROVIDERS.keys()), state="readonly", width=20)
        self.provider_combo.grid(row=0, column=1, sticky="w")
        self.provider_combo.bind("<<ComboboxSelected>>", self._on_provider_changed)
        tk.Button(tab, text="管理Key", command=self.configure_api_key).grid(row=0, column=2, padx=10)

        # 模型选择
        tk.Label(tab, text="选择模型:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.model_combo = ttk.Combobox(tab, textvariable=self.model_var,
                                        values=self._get_model_ids(), state="readonly", width=35)
        self.model_combo.grid(row=1, column=1, sticky="w", padx=(0,10))
        tk.Label(tab, text="切换提供商自动刷新模型列表", fg="blue", font=("Arial", 8)).grid(row=1, column=2, sticky="w")

        # SRT文件选择
        tk.Label(tab, text="SRT字幕文件:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.srt_path_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.srt_path_var, width=50).grid(row=2, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_srt).grid(row=2, column=2, padx=10)

        # Prompt编辑
        tk.Label(tab, text="Prompt提示语:").grid(row=3, column=0, padx=10, pady=5, sticky="ne")
        self.segments_prompt_text = tk.Text(tab, height=8, width=50, wrap=tk.WORD)
        self.segments_prompt_text.grid(row=3, column=1, columnspan=2, sticky="w", padx=(0,10))
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
        tk.Label(tab, text="输出文件:").grid(row=4, column=0, padx=10, pady=5, sticky="e")
        self.output_path_var = tk.StringVar(value="subs.txt")
        tk.Entry(tab, textvariable=self.output_path_var, width=50).grid(row=4, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_output).grid(row=4, column=2, padx=10)

        # 生成按钮
        self.generate_btn = tk.Button(tab, text="生成分段描述", command=self.generate_segments, width=20)
        self.generate_btn.grid(row=5, column=1, pady=25)

        # 进度/提示
        self.status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.status_var, fg="blue").grid(row=6, column=0, columnspan=3, pady=10)

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

        # Prompt编辑
        tk.Label(tab, text="Prompt提示语:").grid(row=1, column=0, padx=10, pady=5, sticky="ne")
        self.prompt_text = tk.Text(tab, height=6, width=50, wrap=tk.WORD)
        self.prompt_text.grid(row=1, column=1, columnspan=2, sticky="w", padx=(0,10))
        # 设置默认prompt
        default_prompt = """## 生成标题

【
给这个视频起个合适的名字，新闻性十足、概括核心焦点，稍微长些没关系

】"""
        self.prompt_text.insert(tk.END, default_prompt)

        # 输出文件选择
        tk.Label(tab, text="输出文件:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.titles_output_var = tk.StringVar(value="titles.txt")
        tk.Entry(tab, textvariable=self.titles_output_var, width=50).grid(row=2, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_titles_output).grid(row=2, column=2, padx=10)

        # 生成按钮
        self.titles_btn = tk.Button(tab, text="生成标题", command=self.generate_titles, width=20)
        self.titles_btn.grid(row=3, column=1, pady=25)

        # 进度/提示
        self.titles_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.titles_status_var, fg="blue").grid(row=4, column=0, columnspan=3, pady=10)

    def create_refine_tab(self):
        """创建分段精炼标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="精炼分段")

        # Input paragraph file picker (expects output from Tab 3)
        tk.Label(tab, text="段落内容文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.refine_input_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.refine_input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_refine_input).grid(row=0, column=2, padx=10)

        # Model selector (shares the same provider/model with segment generation tab)
        tk.Label(tab, text="选择模型:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.refine_model_combo = ttk.Combobox(tab, textvariable=self.model_var,
                                               values=self._get_model_ids(), state="readonly", width=35)
        self.refine_model_combo.grid(row=1, column=1, sticky="w", padx=(0,10))
        tk.Label(tab, text="与“生成分段描述”共享提供商/模型", fg="blue", font=("Arial", 8)).grid(row=1, column=2, sticky="w")

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

    def _get_model_ids(self):
        """Return list of model IDs for the currently selected provider."""
        provider = AI_PROVIDERS.get(self.provider_var.get())
        if not provider:
            return []
        return [m["id"] for m in provider["models"]]

    def _sync_model_list(self, event=None):
        """Update model_var and all model comboboxes when provider changes."""
        provider = AI_PROVIDERS.get(self.provider_var.get())
        if not provider:
            return
        model_ids = [m["id"] for m in provider["models"]]
        default = provider.get("default_model", model_ids[0] if model_ids else "")
        self.model_var.set(default)
        # Update all model comboboxes if they exist
        for combo_attr in ("model_combo", "refine_model_combo"):
            combo = getattr(self, combo_attr, None)
            if combo:
                combo["values"] = model_ids

    def _on_provider_changed(self, event=None):
        """Handle provider combobox selection change."""
        self._sync_model_list()

    def configure_api_key(self):
        """Open a dialog to view/edit the API key for the current provider."""
        provider_name = self.provider_var.get()
        provider = AI_PROVIDERS[provider_name]
        key_path = os.path.join(_keys_dir(), provider["key_file"])

        win = tk.Toplevel(self.master)
        win.title(f"{provider_name} API Key 配置")
        tk.Label(win, text=f"{provider_name} API Key:").pack(pady=10)
        entry = tk.Entry(win, width=50)
        entry.pack(pady=5)
        # Pre-fill existing key
        if os.path.exists(key_path):
            with open(key_path, 'r', encoding='utf-8') as f:
                entry.insert(0, f.read().strip())

        # For custom provider, also allow editing base_url
        if provider_name == "自定义(OpenAI兼容)":
            tk.Label(win, text="Base URL:").pack(pady=(10, 0))
            url_entry = tk.Entry(win, width=50)
            url_entry.pack(pady=5)
            url_entry.insert(0, provider.get("base_url", ""))

            tk.Label(win, text="模型ID (逗号分隔):").pack(pady=(10, 0))
            models_entry = tk.Entry(win, width=50)
            models_entry.pack(pady=5)
            models_entry.insert(0, ",".join(m["id"] for m in provider["models"]))

        def save():
            key = entry.get().strip()
            if not key:
                messagebox.showerror("Error", "请输入有效的API key")
                return
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            with open(key_path, 'w', encoding='utf-8') as f:
                f.write(key)
            # Update custom provider config if applicable
            if provider_name == "自定义(OpenAI兼容)":
                provider["base_url"] = url_entry.get().strip()
                model_ids = [m.strip() for m in models_entry.get().split(",") if m.strip()]
                provider["models"] = [{"id": mid, "label": mid} for mid in model_ids]
                if model_ids:
                    provider["default_model"] = model_ids[0]
                self._sync_model_list()
            messagebox.showinfo("Success", f"{provider_name} API key 已保存!")
            win.destroy()

        tk.Button(win, text="保存", command=save).pack(pady=10)

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
            messagebox.showerror("错误", "请选择有效的SRT文件")
            return
        
        if not output_path:
            messagebox.showerror("错误", "请选择输出文件路径")
            return
        
        if not prompt:
            messagebox.showerror("错误", "请输入Prompt提示语")
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
                messagebox.showerror("错误", f"无法创建输出目录: {e}")
                return
        
        self.status_var.set("正在生成分段描述...")
        self.generate_btn.config(state="disabled")
        self.master.update()
        
        # 在后台线程中运行生成任务
        def run_generation():
            try:
                segments = generate_youtube_segments(srt_path, provider_name=self.provider_var.get(), model_name=self.model_var.get(), prompt=prompt)
                
                # 保存到用户指定的文件
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(segments)
                
                # 验证文件是否成功创建
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.status_var.set("生成完成")
                    messagebox.showinfo("Success", f"YouTube分段描述已保存到: {output_path}")
                else:
                    raise Exception("文件创建失败或文件为空")
                
            except Exception as e:
                messagebox.showerror("错误", f"生成失败: {e}")
                self.status_var.set("生成失败")
            finally:
                self.generate_btn.config(state="normal")
        
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
            messagebox.showerror("错误", "请选择有效的SRT文件")
            return

        if not segments_path or not os.path.exists(segments_path):
            messagebox.showerror("错误", "请选择有效的时间戳分割文件")
            return

        if not output_path:
            messagebox.showerror("错误", "请选择输出文件路径")
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
                messagebox.showerror("错误", f"无法创建输出目录: {e}")
                return

        self.paragraphs_status_var.set("正在提取段落内容...")
        self.extract_btn.config(state="disabled")
        self.master.update()

        # 在后台线程中运行提取任务
        def run_extraction():
            try:
                paragraphs = extract_paragraphs_from_segments(srt_path, segments_path)

                # 保存到用户指定的文件
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(paragraphs)

                # 验证文件是否成功创建
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.paragraphs_status_var.set("提取完成")
                    messagebox.showinfo("Success", f"段落内容已保存到: {output_path}")
                else:
                    raise Exception("文件创建失败或文件为空")

            except Exception as e:
                messagebox.showerror("错误", f"提取失败: {e}")
                self.paragraphs_status_var.set("提取失败")
            finally:
                self.extract_btn.config(state="normal")

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
            messagebox.showerror("错误", "请选择有效的段落内容文件")
            return

        if not output_path:
            messagebox.showerror("错误", "请选择输出文件路径")
            return

        if not prompt:
            messagebox.showerror("错误", "请输入Prompt提示语")
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
                messagebox.showerror("错误", f"无法创建输出目录: {e}")
                return

        self.refine_status_var.set("正在精炼分段描述...")
        self.refine_btn.config(state="disabled")
        self.master.update()

        # Run in background thread to keep GUI responsive.
        def run_refinement():
            try:
                refined_text = refine_segment_descriptions(input_path, prompt, provider_name=self.provider_var.get(), model_name=self.model_var.get())

                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(refined_text)

                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.refine_status_var.set("精炼完成")
                    messagebox.showinfo("Success", f"精炼分段内容已保存到: {output_path}")
                else:
                    raise Exception("文件创建失败或文件为空")

            except Exception as e:
                messagebox.showerror("错误", f"精炼失败: {e}")
                self.refine_status_var.set("精炼失败")
            finally:
                self.refine_btn.config(state="normal")

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
            messagebox.showerror("错误", "请选择有效的Subs文件")
            return

        if not output_path:
            messagebox.showerror("错误", "请选择输出文件路径")
            return

        if not prompt:
            messagebox.showerror("错误", "请输入Prompt提示语")
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
                messagebox.showerror("错误", f"无法创建输出目录: {e}")
                return

        self.titles_status_var.set("正在生成标题...")
        self.titles_btn.config(state="disabled")
        self.master.update()

        # 在后台线程中运行生成任务
        def run_title_generation():
            try:
                titles = generate_video_titles(subs_path, prompt, provider_name=self.provider_var.get(), model_name=self.model_var.get())

                # 保存到用户指定的文件
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(titles)

                # 验证文件是否成功创建
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.titles_status_var.set("生成完成")
                    messagebox.showinfo("Success", f"视频标题已保存到: {output_path}")
                else:
                    raise Exception("文件创建失败或文件为空")

            except Exception as e:
                messagebox.showerror("错误", f"生成失败: {e}")
                self.titles_status_var.set("生成失败")
            finally:
                self.titles_btn.config(state="normal")

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
            messagebox.showerror("错误", "请选择有效的SRT文件")
            return

        if not output_path:
            messagebox.showerror("错误", "请选择输出文件路径")
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
                messagebox.showerror("错误", f"无法创建输出目录: {e}")
                return

        self.subtitles_status_var.set("正在提取字幕文字...")
        self.subtitles_btn.config(state="disabled")
        self.master.update()

        # 在后台线程中运行提取任务
        def run_subtitle_extraction():
            try:
                subtitles_text = extract_all_subtitles(srt_path)

                # 保存到用户指定的文件
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(subtitles_text)

                # 验证文件是否成功创建
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    output_filename = os.path.basename(output_path)
                    self.subtitles_status_var.set(f"✓ 提取完成，已保存到: {output_filename}")
                    # 在右侧文本框中显示提取的内容
                    self.master.after(0, self.display_subtitles_content, subtitles_text)
                else:
                    raise Exception("文件创建失败或文件为空")

            except Exception as e:
                self.subtitles_status_var.set(f"提取失败: {e}")
            finally:
                self.subtitles_btn.config(state="normal")

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
