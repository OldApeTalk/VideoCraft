import os
import srt
import google.generativeai as genai
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from datetime import datetime

def generate_youtube_segments(srt_path, api_key_path=None, model_name='gemini-2.5-flash-lite', prompt=None):
    '''
    根据SRT字幕文件生成YouTube分段描述

    Args:
        srt_path (str): SRT文件路径
        api_key_path (str): Gemini API key文件路径
        model_name (str): 使用的Gemini模型名称
        prompt (str): 自定义提示语，如果为None则使用默认提示语

    Returns:
        str: 生成的YouTube分段描述
    '''
    # 设置默认API key路径
    if api_key_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        api_key_path = os.path.join(os.path.dirname(script_dir), 'keys', 'Gemini.key')
    
    # 检查API key文件
    if not os.path.exists(api_key_path):
        raise FileNotFoundError(f'Gemini API key文件 \'{api_key_path}\' 不存在，请先配置API key')

    # 读取API key
    with open(api_key_path, 'r', encoding='utf-8') as f:
        api_key = f.read().strip()

    if not api_key:
        raise ValueError('API key为空，请检查配置文件')

    # 配置Gemini
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

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

    # 调用Gemini API
    try:
        response = model.generate_content(prompt)
        segments = response.text.strip()
        return segments
    except Exception as e:
        raise RuntimeError(f'调用Gemini API失败: {e}')

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
                # 解析时间戳 (hh:mm:ss)
                h, m, s = map(int, time_str.split(':'))
                timestamp = h * 3600 + m * 60 + s
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

def generate_video_titles(subs_path, prompt, api_key_path=None, model_name='gemini-2.5-flash-lite'):
    """
    根据subs文件内容生成视频标题

    Args:
        subs_path (str): Subs文件路径
        prompt (str): 生成标题的prompt
        api_key_path (str): Gemini API key文件路径
        model_name (str): 使用的Gemini模型名称

    Returns:
        str: 生成的标题内容
    """
    # 设置默认API key路径
    if api_key_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        api_key_path = os.path.join(os.path.dirname(script_dir), 'keys', 'Gemini.key')
    
    # 检查API key文件
    if not os.path.exists(api_key_path):
        raise FileNotFoundError(f'Gemini API key文件 \'{api_key_path}\' 不存在，请先配置API key')

    # 读取API key
    with open(api_key_path, 'r', encoding='utf-8') as f:
        api_key = f.read().strip()

    if not api_key:
        raise ValueError('API key为空，请检查配置文件')

    # 配置Gemini
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    # 读取subs文件内容
    with open(subs_path, 'r', encoding='utf-8') as f:
        subs_content = f.read()

    # 构建完整的prompt
    full_prompt = f"{prompt}\n\n以下是视频的分段描述内容：\n\n{subs_content}\n\n请根据以上内容生成合适的视频标题。"

    # 调用Gemini API
    try:
        response = model.generate_content(full_prompt)
        titles = response.text.strip()
        return titles
    except Exception as e:
        raise RuntimeError(f'调用Gemini API失败: {e}')

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

# ===================== GUI 主界面 =====================
class YouTubeSegmentsApp:
    def __init__(self, master):
        self.master = master
        master.title("YouTube工具箱（Gemini）")
        master.geometry("750x450")
        master.resizable(False, False)

        # 创建标签页
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # 分段生成标签页
        self.create_segments_tab()

        # 段落提取标签页
        self.create_paragraphs_tab()

        # 标题生成标签页
        self.create_titles_tab()

        # 字幕提取标签页
        self.create_subtitles_tab()

    def create_segments_tab(self):
        """创建分段生成标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="生成分段描述")

        # 获取可用模型列表
        self.available_models = self.get_available_models()

        # Gemini API Key 配置
        tk.Label(tab, text="Gemini API Key:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.api_key_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.api_key_var, width=50, show='*').grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="管理Key", command=self.configure_gemini_key).grid(row=0, column=2, padx=10)

        # 模型选择
        tk.Label(tab, text="选择模型:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.model_var = tk.StringVar(value="gemini-2.5-flash-lite" if "gemini-2.5-flash-lite" in self.available_models else (self.available_models[0] if self.available_models else "gemini-2.5-flash-lite"))
        self.model_combo = ttk.Combobox(tab, textvariable=self.model_var, values=self.available_models, state="readonly", width=25)
        self.model_combo.grid(row=1, column=1, sticky="w", padx=(0,10))

        # 模型说明
        tk.Label(tab, text="选择适合的模型进行分段生成", fg="blue", font=("Arial", 8)).grid(row=1, column=2, sticky="w")

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

    def create_subtitles_tab(self):
        """创建字幕提取标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="提取字幕文字")

        # SRT文件选择
        tk.Label(tab, text="SRT字幕文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.subtitles_srt_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.subtitles_srt_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_subtitles_srt).grid(row=0, column=2, padx=10)

        # 输出文件选择
        tk.Label(tab, text="输出文件:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.subtitles_output_var = tk.StringVar(value="AllSubtitles.txt")
        tk.Entry(tab, textvariable=self.subtitles_output_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_subtitles_output).grid(row=1, column=2, padx=10)

        # 提取按钮
        self.subtitles_btn = tk.Button(tab, text="提取字幕文字", command=self.extract_subtitles, width=20)
        self.subtitles_btn.grid(row=2, column=1, pady=25)

        # 进度/提示
        self.subtitles_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.subtitles_status_var, fg="blue").grid(row=3, column=0, columnspan=3, pady=10)

    def get_available_models(self):
        """获取可用的 Gemini 模型列表，仅显示 2.5 版本"""
        default_models = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        api_key_path = os.path.join(os.path.dirname(script_dir), 'keys', 'Gemini.key')
        if os.path.exists(api_key_path):
            try:
                with open(api_key_path, 'r') as f:
                    api_key = f.read().strip()
                genai.configure(api_key=api_key)
                models = genai.list_models()
                # 只选择支持 generateContent 且为 2.5 版本的模型
                model_names = [m.name.split('/')[-1] for m in models if 'generateContent' in m.supported_generation_methods and '2.5' in m.name]
                if model_names:
                    sorted_models = sorted(model_names)
                    print("可用 2.5 版本模型列表:")
                    for model in sorted_models:
                        print(f"  - {model}")
                    print("注意: 模型价格信息请参考 Google Cloud 定价页面 (https://cloud.google.com/vertex-ai/pricing)")
                    return sorted_models
            except Exception as e:
                print(f"获取模型列表失败: {e}")
        
        print("使用默认 2.5 版本模型列表:")
        for model in default_models:
            print(f"  - {model}")
        return default_models

    def refresh_available_models(self):
        """刷新可用模型列表并更新 Combobox"""
        self.available_models = self.get_available_models()
        self.model_combo['values'] = self.available_models
        # 如果当前选择的模型不在新列表中，重置为第一个
        if self.model_var.get() not in self.available_models:
            self.model_var.set(self.available_models[0] if self.available_models else "gemini-2.5-flash")

    def configure_gemini_key(self):
        win = tk.Toplevel(self.master)
        win.title("Gemini API Key 配置")
        tk.Label(win, text="Gemini API Key:").pack(pady=10)
        entry = tk.Entry(win, width=50)
        entry.pack(pady=5)
        # 预填已有key
        script_dir = os.path.dirname(os.path.abspath(__file__))
        api_key_path = os.path.join(os.path.dirname(script_dir), 'keys', 'Gemini.key')
        if os.path.exists(api_key_path):
            with open(api_key_path, 'r') as f:
                entry.insert(0, f.read().strip())
        def save():
            key = entry.get().strip()
            if key:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                api_key_path = os.path.join(os.path.dirname(script_dir), 'keys', 'Gemini.key')
                os.makedirs(os.path.dirname(api_key_path), exist_ok=True)
                with open(api_key_path, 'w') as f:
                    f.write(key)
                self.api_key_var.set(key)  # 更新界面显示
                self.refresh_available_models()  # 刷新模型列表
                messagebox.showinfo("Success", "API key saved!")
                win.destroy()
            else:
                messagebox.showerror("Error", "请输入有效的API key")
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
                segments = generate_youtube_segments(srt_path, model_name=self.model_var.get(), prompt=prompt)
                
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
                titles = generate_video_titles(subs_path, prompt, model_name=self.model_var.get())

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
                    self.subtitles_status_var.set("提取完成")
                    messagebox.showinfo("Success", f"字幕文字已保存到: {output_path}")
                else:
                    raise Exception("文件创建失败或文件为空")

            except Exception as e:
                messagebox.showerror("错误", f"提取失败: {e}")
                self.subtitles_status_var.set("提取失败")
            finally:
                self.subtitles_btn.config(state="normal")

        threading.Thread(target=run_subtitle_extraction, daemon=True).start()

def main():
    # 启动GUI界面
    root = tk.Tk()
    app = YouTubeSegmentsApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
