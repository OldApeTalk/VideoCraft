import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import srt
import re
import time
import asyncio
import threading
import google.generativeai as genai

# 尝试导入pydub，如果不可用则设置为None
# 注意：当前Live API实现仍使用文本翻译，pydub仅为未来音频处理功能预留
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    AudioSegment = None
    PYDUB_AVAILABLE = False

# 支持的语言列表 (语言代码 -> (英文名, 中文名))
SUPPORTED_LANGUAGES = {
    'auto': ('Auto Detect', '自动检测'),
    'en': ('English', '英语'),
    'zh': ('Chinese', '中文'),
    'ja': ('Japanese', '日语'),
    'ko': ('Korean', '韩语'),
    'de': ('German', '德语'),
    'fr': ('French', '法语'),
    'es': ('Spanish', '西班牙语'),
    'pt': ('Portuguese', '葡萄牙语'),
    'it': ('Italian', '意大利语'),
    'ru': ('Russian', '俄语'),
    'ar': ('Arabic', '阿拉伯语'),
    'hi': ('Hindi', '印地语'),
    'th': ('Thai', '泰语'),
    'vi': ('Vietnamese', '越南语'),
    'nl': ('Dutch', '荷兰语'),
    'pl': ('Polish', '波兰语'),
    'tr': ('Turkish', '土耳其语'),
    'sv': ('Swedish', '瑞典语'),
    'da': ('Danish', '丹麦语'),
    'no': ('Norwegian', '挪威语'),
    'fi': ('Finnish', '芬兰语'),
    'cs': ('Czech', '捷克语'),
    'hu': ('Hungarian', '匈牙利语'),
    'ro': ('Romanian', '罗马尼亚语'),
    'bg': ('Bulgarian', '保加利亚语'),
    'hr': ('Croatian', '克罗地亚语'),
    'sk': ('Slovak', '斯洛伐克语'),
    'sl': ('Slovenian', '斯洛文尼亚语'),
    'et': ('Estonian', '爱沙尼亚语'),
    'lv': ('Latvian', '拉脱维亚语'),
    'lt': ('Lithuanian', '立陶宛语'),
    'mt': ('Maltese', '马耳他语'),
    'ga': ('Irish', '爱尔兰语'),
    'is': ('Icelandic', '冰岛语'),
    'mk': ('Macedonian', '马其顿语'),
    'sq': ('Albanian', '阿尔巴尼亚语'),
    'bs': ('Bosnian', '波斯尼亚语'),
    'sr': ('Serbian', '塞尔维亚语'),
    'me': ('Montenegrin', '黑山语'),
    'uk': ('Ukrainian', '乌克兰语'),
    'be': ('Belarusian', '白俄罗斯语'),
    'ka': ('Georgian', '格鲁吉亚语'),
    'hy': ('Armenian', '亚美尼亚语'),
    'az': ('Azerbaijani', '阿塞拜疆语'),
    'kk': ('Kazakh', '哈萨克语'),
    'uz': ('Uzbek', '乌兹别克语'),
    'tk': ('Turkmen', '土库曼语'),
    'ky': ('Kyrgyz', '吉尔吉斯语'),
    'tg': ('Tajik', '塔吉克语'),
    'mn': ('Mongolian', '蒙古语'),
    'bn': ('Bengali', '孟加拉语'),
    'pa': ('Punjabi', '旁遮普语'),
    'gu': ('Gujarati', '古吉拉特语'),
    'or': ('Oriya', '奥里亚语'),
    'te': ('Telugu', '泰卢固语'),
    'kn': ('Kannada', '卡纳达语'),
    'ml': ('Malayalam', '马拉雅拉姆语'),
    'si': ('Sinhala', '僧伽罗语'),
    'ne': ('Nepali', '尼泊尔语'),
    'mr': ('Marathi', '马拉地语'),
    'as': ('Assamese', '阿萨姆语'),
    'bh': ('Bihari', '比哈里语'),
    'sa': ('Sanskrit', '梵语'),
    'sd': ('Sindhi', '信德语'),
    'ur': ('Urdu', '乌尔都语'),
    'fa': ('Persian', '波斯语'),
    'he': ('Hebrew', '希伯来语'),
    'yi': ('Yiddish', '意第绪语'),
    'am': ('Amharic', '阿姆哈拉语'),
    'ti': ('Tigrinya', '提格里尼亚语'),
    'om': ('Oromo', '奥罗莫语'),
    'so': ('Somali', '索马里语'),
    'sw': ('Swahili', '斯瓦希里语'),
    'rw': ('Kinyarwanda', '卢旺达语'),
    'rn': ('Kirundi', '基隆迪语'),
    'mg': ('Malagasy', '马达加斯加语'),
    'xh': ('Xhosa', '科萨语'),
    'zu': ('Zulu', '祖鲁语'),
    'st': ('Sesotho', '塞索托语'),
    'tn': ('Tswana', '茨瓦纳语'),
    'af': ('Afrikaans', '南非荷兰语'),
    'ha': ('Hausa', '豪萨语'),
    'yo': ('Yoruba', '约鲁巴语'),
    'ig': ('Igbo', '伊博语'),
    'id': ('Indonesian', '印度尼西亚语'),
    'ms': ('Malay', '马来语'),
    'tl': ('Filipino', '菲律宾语'),
    'jv': ('Javanese', '爪哇语'),
    'su': ('Sundanese', '巽他语'),
    'ceb': ('Cebuano', '宿务语'),
    'ilo': ('Iloko', '伊洛卡诺语'),
    'bi': ('Bislama', '比斯拉马语'),
    'to': ('Tonga', '汤加语'),
    'sm': ('Samoan', '萨摩亚语'),
    'haw': ('Hawaiian', '夏威夷语'),
    'fj': ('Fijian', '斐济语'),
    'mh': ('Marshallese', '马绍尔语'),
    'ty': ('Tahitian', '塔希提语'),
    'el': ('Greek', '希腊语'),
    'la': ('Latin', '拉丁语'),
    'cy': ('Welsh', '威尔士语'),
    'eu': ('Basque', '巴斯克语'),
    'ca': ('Catalan', '加泰罗尼亚语'),
    'gl': ('Galician', '加利西亚语'),
    'eo': ('Esperanto', '世界语'),
    'my': ('Burmese', '缅甸语'),
    'km': ('Khmer', '高棉语'),
    'lo': ('Lao', '老挝语'),
    'bo': ('Tibetan', '藏语'),
    'dz': ('Dzongkha', '宗喀语'),
    'si': ('Sinhala', '僧伽罗语'),
    'pi': ('Pali', '巴利语'),
}

# 生成语言选项列表
language_options = []
for code, (eng, chn) in SUPPORTED_LANGUAGES.items():
    language_options.append(f"{eng} ({chn}) - {code.upper()}")

def split_audio_by_size(audio_path, max_size_kb=100):
    """按文件大小分割音频，确保每段不超过max_size_kb KB"""
    if not PYDUB_AVAILABLE:
        raise ImportError("pydub不可用，无法进行音频分割。请安装pydub: pip install pydub")
    
    audio = AudioSegment.from_file(audio_path)
    max_size_bytes = max_size_kb * 1024
    
    # 估算每秒音频大小（粗略）
    sample_rate = audio.frame_rate
    channels = audio.channels
    bytes_per_second = sample_rate * channels * 2  # 16-bit
    
    # 计算段长（秒）
    segment_length_sec = max_size_bytes / bytes_per_second
    segment_length_ms = int(segment_length_sec * 1000)
    
    # 确保不小于1秒
    segment_length_ms = max(segment_length_ms, 1000)
    
    segments = []
    duration_ms = len(audio)
    
    for i in range(0, duration_ms, segment_length_ms):
        start_time = i
        end_time = min(i + segment_length_ms, duration_ms)
        
        # 提取段
        segment = audio[start_time:end_time]
        
        # 检查实际大小，如果仍超过限制，进一步分割
        temp_path = f"temp_segment_{i//segment_length_ms}.wav"
        segment.export(temp_path, format="wav")
        
        actual_size = os.path.getsize(temp_path)
        if actual_size > max_size_bytes:
            # 如果仍大，进一步分割成更小段
            sub_segments = split_audio_by_size(temp_path, max_size_kb // 2)
            segments.extend(sub_segments)
            os.remove(temp_path)
        else:
            segments.append({
                'path': temp_path,
                'start_ms': start_time,
                'end_ms': end_time,
                'size_kb': actual_size / 1024
            })
    
    return segments

# ===================== GUI 主界面 =====================
class TranslateApp:
    def __init__(self, master):
        self.master = master
        master.title("SRT字幕批量翻译工具（Gemini）")
        master.geometry("700x460")
        master.resizable(False, False)

        # 获取可用模型列表
        self.available_models = self.get_available_models()

        # Gemini API Key 配置
        tk.Label(master, text="Gemini API Key:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.api_key_var = tk.StringVar()
        tk.Entry(master, textvariable=self.api_key_var, width=50, show='*').grid(row=0, column=1, sticky="w")
        tk.Button(master, text="管理Key", command=self.configure_gemini_key).grid(row=0, column=2, padx=10)

        # 模型选择
        tk.Label(master, text="选择模型:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.model_var = tk.StringVar(value="gemini-2.5-flash" if "gemini-2.5-flash" in self.available_models else (self.available_models[0] if self.available_models else "gemini-2.5-flash"))
        self.model_combo = ttk.Combobox(master, textvariable=self.model_var, values=self.available_models, state="readonly", width=25)
        self.model_combo.grid(row=1, column=1, sticky="w", padx=(0,10))

        # 模型说明
        tk.Label(master, text="选择适合的模型进行翻译", fg="blue", font=("Arial", 8)).grid(row=1, column=2, sticky="w")

        # 源语言选择
        tk.Label(master, text="源语言 (Source):").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.source_lang_var = tk.StringVar(value="English (英语) - EN")
        self.source_combo = ttk.Combobox(master, textvariable=self.source_lang_var, values=language_options, state="readonly", width=30)
        self.source_combo.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0,10))

        # 目标语言选择
        tk.Label(master, text="目标语言 (Target):").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        self.target_lang_var = tk.StringVar(value="Chinese (中文) - ZH")
        self.target_combo = ttk.Combobox(master, textvariable=self.target_lang_var, values=language_options, state="readonly", width=30)
        self.target_combo.grid(row=3, column=1, columnspan=2, sticky="w", padx=(0,10))

        # 批次大小选择
        tk.Label(master, text="每批次字幕条数:").grid(row=4, column=0, padx=10, pady=5, sticky="e")
        self.batch_size_var = tk.StringVar(value="50")
        batch_size_frame = tk.Frame(master)
        batch_size_frame.grid(row=4, column=1, columnspan=2, sticky="w", padx=(0,10))
        ttk.Radiobutton(batch_size_frame, text="30", variable=self.batch_size_var, value="30").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(batch_size_frame, text="50", variable=self.batch_size_var, value="50").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(batch_size_frame, text="100", variable=self.batch_size_var, value="100").pack(side=tk.LEFT, padx=5)
        tk.Label(batch_size_frame, text="(批次越大速度越快，但可能影响准确性)", font=("Arial", 8), fg="gray").pack(side=tk.LEFT, padx=5)

        # SRT文件选择
        tk.Label(master, text="原始SRT文件:").grid(row=5, column=0, padx=10, pady=10, sticky="e")
        self.srt_path_var = tk.StringVar()
        tk.Entry(master, textvariable=self.srt_path_var, width=50).grid(row=5, column=1, sticky="w")
        tk.Button(master, text="浏览", command=self.select_srt).grid(row=5, column=2, padx=10)

        # Prompt编辑
        tk.Label(master, text="Prompt提示语:").grid(row=6, column=0, padx=10, pady=5, sticky="ne")
        self.translate_prompt_text = tk.Text(master, height=10, width=50, wrap=tk.WORD)
        self.translate_prompt_text.grid(row=6, column=1, columnspan=2, sticky="w", padx=(0,10))
        # 设置默认prompt
        default_translate_prompt = """You are a professional SRT subtitle translator. Your task is to translate the following SRT subtitles from {source_lang_name} to {target_lang_name}.

The subtitles are provided in a special numbered format with 【number】 markers (【1】subtitle, 【2】subtitle, etc.). You must return the translated subtitles in the EXACT SAME special numbered format.

CRITICAL REQUIREMENTS:
1. Translate EACH AND EVERY subtitle individually and separately
2. Return the EXACT SAME NUMBER of subtitles as input ({{batch_size}} subtitles)
3. Maintain the special numbered format: "【1】translated text", "【2】translated text", etc.
4. DO NOT split any single subtitle into multiple subtitles
5. DO NOT merge multiple subtitles into one subtitle
6. DO NOT change the numbering or add/remove any subtitles
7. DO NOT remove the 【】markers - they are essential for identification
8. Preserve the original line breaks and formatting within each subtitle
9. Output ONLY the numbered subtitles with 【】markers, no explanations, comments, or additional text
10. Do NOT add quotation marks around translated text unless they are part of the original meaning
11. Ensure translation quality and natural language

Input subtitles ({{batch_size}} subtitles):
{{numbered_input}}

Return the translated subtitles in the same special 【number】 format with {{batch_size}} subtitles:"""
        self.translate_prompt_text.insert(tk.END, default_translate_prompt)

        # 翻译按钮
        self.trans_btn = tk.Button(master, text="开始翻译", command=self.translate_srt, width=20)
        self.trans_btn.grid(row=7, column=1, pady=25)

        # 进度/提示
        self.status_var = tk.StringVar()
        tk.Label(master, textvariable=self.status_var, fg="blue").grid(row=8, column=0, columnspan=3, pady=10)

    def get_available_models(self):
        """获取可用的 Gemini 模型列表，仅显示 2.5 版本"""
        default_models = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        gemini_key_path = os.path.join(os.path.dirname(script_dir), 'keys', 'Gemini.key')
        if os.path.exists(gemini_key_path):
            try:
                with open(gemini_key_path, 'r') as f:
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

    def get_lang_code(self, lang_str):
        """从语言选择字符串中提取语言代码"""
        if " - " in lang_str:
            code = lang_str.split(" - ")[-1].lower()
            if code in SUPPORTED_LANGUAGES:
                return code
        return 'en'  # 默认返回英语

    def configure_gemini_key(self):
        win = tk.Toplevel(self.master)
        win.title("Gemini API Key 配置")
        tk.Label(win, text="Gemini API Key:").pack(pady=10)
        entry = tk.Entry(win, width=50)
        entry.pack(pady=5)
        # 预填已有key（使用绝对路径）
        script_dir = os.path.dirname(os.path.abspath(__file__))
        gemini_key_path = os.path.join(os.path.dirname(script_dir), 'keys', 'Gemini.key')
        if os.path.exists(gemini_key_path):
            with open(gemini_key_path, 'r') as f:
                entry.insert(0, f.read().strip())
        def save():
            key = entry.get().strip()
            if key:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                gemini_key_path = os.path.join(os.path.dirname(script_dir), 'keys', 'Gemini.key')
                # 确保keys文件夹存在
                os.makedirs(os.path.dirname(gemini_key_path), exist_ok=True)
                with open(gemini_key_path, 'w') as f:
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

    def translate_with_standard_api(self, custom_prompt=None):
        srt_path = self.srt_path_var.get()
        source_lang = self.get_lang_code(self.source_lang_var.get())
        target_lang = self.get_lang_code(self.target_lang_var.get())
        
        if not srt_path or not os.path.exists(srt_path):
            messagebox.showerror("错误", "请选择有效的SRT文件")
            return
        
        if source_lang == target_lang:
            messagebox.showerror("错误", "源语言和目标语言不能相同")
            return
            
        self.status_var.set("正在读取字幕...")
        self.master.update()
        
        # 读取SRT
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                subs = list(srt.parse(f))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse SRT file: {e}")
            return
            
        # Gemini翻译逻辑：分批发送，每批最多2000字符，请求间隔6秒
        script_dir = os.path.dirname(os.path.abspath(__file__))
        gemini_key_path = os.path.join(os.path.dirname(script_dir), 'keys', 'Gemini.key')
        if not os.path.exists(gemini_key_path):
            messagebox.showerror("错误", "请先配置Gemini Key")
            return
            
        try:
            with open(gemini_key_path, 'r') as f:
                api_key = f.read().strip()
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(self.model_var.get())
            
            # Gemini翻译逻辑
            source_lang_name = SUPPORTED_LANGUAGES.get(source_lang, ('Unknown', '未知'))[0]
            target_lang_name = SUPPORTED_LANGUAGES.get(target_lang, ('Unknown', '未知'))[0]

            # 直接处理每个字幕，不进行合并
            print(f"📋 准备翻译 {len(subs)} 条字幕")

            # 准备所有字幕文本 - 使用醒目的编号格式确保API不会合并字幕
            subtitle_contents = []
            for i, sub in enumerate(subs):
                # 使用醒目的【编号】格式，确保每条字幕都被单独处理
                subtitle_contents.append(f"【{i+1}】{sub.content}")

            # 分批处理，每批最多包含一定数量的字幕（而不是字符数）
            max_subs_per_batch = int(self.batch_size_var.get())  # 从 GUI 获取批次大小
            batches = []

            for i in range(0, len(subtitle_contents), max_subs_per_batch):
                batch_contents = subtitle_contents[i:i + max_subs_per_batch]
                batches.append({
                    'start_idx': i,
                    'contents': batch_contents
                })

            print(f"📦 分成 {len(batches)} 个批次进行翻译")

            # 翻译每批
            translated_subs = {}
            total_processed = 0

            for batch_idx, batch in enumerate(batches):
                self.status_var.set(f"正在翻译 ({source_lang.upper()} -> {target_lang.upper()}) - 批次 {batch_idx+1}/{len(batches)}")
                self.master.update()

                batch_start_idx = batch['start_idx']
                batch_contents = batch['contents']
                batch_size = len(batch_contents)

                # 创建编号文本输入
                numbered_input = '\n\n'.join(batch_contents)

                # 使用自定义prompt，替换占位符
                prompt = custom_prompt.replace("{source_lang_name}", source_lang_name)
                prompt = prompt.replace("{target_lang_name}", target_lang_name)
                prompt = prompt.replace("{batch_size}", str(batch_size))
                prompt = prompt.replace("{numbered_input}", numbered_input)

                response = model.generate_content(prompt)
                translated_batch = response.text.strip()

                # 处理可能的markdown代码块格式
                if translated_batch.startswith('```'):
                    # 移除开头的```json或```
                    lines = translated_batch.split('\n')
                    # 找到第一个非空行且不是代码块标记的行
                    start_idx = 0
                    for i, line in enumerate(lines):
                        line = line.strip()
                        if line and not line.startswith('```'):
                            start_idx = i
                            break

                    # 移除结尾的```
                    end_idx = len(lines)
                    for i in range(len(lines) - 1, -1, -1):
                        line = lines[i].strip()
                        if line and not line.startswith('```'):
                            end_idx = i + 1
                            break

                    translated_batch = '\n'.join(lines[start_idx:end_idx]).strip()

                # 调试：保存原始响应用于诊断（仅在出错时保存，正常翻译不保存）
                # 如果需要调试，取消下面的注释
                # debug_file = f"debug_response_batch_{batch_idx+1}.txt"
                # try:
                #     with open(debug_file, 'w', encoding='utf-8') as f:
                #         f.write(f"=== 批次 {batch_idx+1} 原始响应 ===\n")
                #         f.write(translated_batch)
                #         f.write(f"\n\n=== 批次 {batch_idx+1} 输入编号文本 ===\n")
                #         f.write(numbered_input)
                #     print(f"  💾 调试信息已保存到: {debug_file}")
                # except:
                #     pass  # 调试文件保存失败不影响主流程

                # 解析编号响应
                try:
                    # 按行分割并解析编号格式
                    lines = translated_batch.split('\n')
                    parsed_subs = {}

                    current_num = None
                    current_content = []

                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue

                        # 检查是否是编号行 (如 "【1】", "【2】", etc.)
                        import re
                        match = re.match(r'^【(\d+)】\s*(.*)$', line)
                        if match:
                            # 保存之前的字幕（如果有）
                            if current_num is not None and current_content:
                                parsed_subs[current_num] = '\n'.join(current_content).strip()

                            # 开始新的字幕
                            current_num = int(match.group(1)) - 1  # 转换为0-based索引
                            current_content = [match.group(2)]
                        elif current_num is not None:
                            # 继续当前字幕的内容
                            current_content.append(line)

                    # 保存最后一个字幕
                    if current_num is not None and current_content:
                        parsed_subs[current_num] = '\n'.join(current_content).strip()

                    # 验证数量
                    if len(parsed_subs) != batch_size:
                        print(f"  ⚠️  批次 {batch_idx+1} 字幕数量不匹配: 期望 {batch_size}, 实际 {len(parsed_subs)}")
                        actual_size = min(batch_size, len(parsed_subs))
                    else:
                        actual_size = batch_size
                        print(f"  ✅ 批次 {batch_idx+1} 编号解析成功: {actual_size} 条字幕")

                    # 存储翻译结果
                    for i in range(actual_size):
                        global_idx = batch_start_idx + i
                        if global_idx in parsed_subs:  # 修复：使用全局索引而不是批次内索引
                            translated_content = parsed_subs[global_idx]

                            # 清理可能的多余引号（如果API添加了引号包围）
                            if isinstance(translated_content, str):
                                # 清理首尾引号 - 更激进的清理
                                original_content = translated_content
                                while (len(translated_content) > 1 and
                                       translated_content.startswith('"') and
                                       translated_content.endswith('"')):
                                    # 检查清理后是否仍然有效
                                    cleaned = translated_content[1:-1]  # 移除最外层引号
                                    # 如果清理后内容仍然合理，则接受清理
                                    if cleaned.strip():
                                        translated_content = cleaned
                                    else:
                                        break

                                # 如果内容被清理了，记录一下
                                if translated_content != original_content:
                                    print(f"  🧹 清理字幕 {global_idx} 的多余引号")
                                    print(f"     原文: '{original_content}'")
                                    print(f"     清理后: '{translated_content}'")

                            translated_subs[global_idx] = translated_content

                    print(f"  📍 批次 {batch_idx+1} 处理完成 (全局索引 {batch_start_idx}-{batch_start_idx+actual_size-1})")

                except Exception as e:
                    print(f"  ❌ 批次 {batch_idx+1} 编号解析失败: {e}")
                    print(f"  📄 原始响应: {translated_batch[:200]}...")

                    # 后备解析：尝试按行分割（不推荐，但作为最后手段）
                    lines = translated_batch.split('\n')
                    valid_lines = [line.strip() for line in lines if line.strip() and not line.startswith('```')]

                    if len(valid_lines) >= batch_size:
                        print(f"  🔄 使用后备解析方法...")
                        for i in range(batch_size):
                            global_idx = batch_start_idx + i
                            if i < len(valid_lines):
                                translated_subs[global_idx] = valid_lines[i]
                        print(f"  ✅ 后备解析完成: {batch_size} 条字幕")
                    else:
                        print(f"  ❌ 后备解析也失败: 只有 {len(valid_lines)} 行可用文本")

                # 更新已处理的字幕数量
                total_processed += batch_size

                # API调用间隔，避免速率限制
                if batch_idx < len(batches) - 1:
                    print("  ⏳ 等待6秒...")
                    import time
                    time.sleep(6)

            # 直接应用翻译结果 - 未翻译的字幕保持原文
            untranslated_count = 0
            for i, sub in enumerate(subs):
                if i in translated_subs:
                    sub.content = translated_subs[i]
                else:
                    # 保持原文
                    untranslated_count += 1
                    print(f"字幕 {i+1} 未翻译，保持原文: '{sub.content[:50]}...'")

            if untranslated_count > 0:
                print(f"共 {untranslated_count} 条字幕未翻译，保持原文")
            else:
                print(f"成功: 所有 {len(subs)} 条字幕都已翻译")
            
        except Exception as e:
            messagebox.showerror("Gemini错误", f"翻译失败: {e}")
            return
        
        # 输出
        target_lang_name = SUPPORTED_LANGUAGES[target_lang][0]  # 获取目标语言的英文名
        output_dir = os.path.dirname(srt_path)  # 获取原文件的目录
        output_file = os.path.join(output_dir, f"{target_lang_name}.srt")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(srt.compose(subs))
            self.status_var.set(f"翻译完成，已保存: {output_file}")
            messagebox.showinfo("Success", f"Translated SRT saved to: {output_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save output: {e}")
            self.status_var.set("")

    def translate_srt(self):
        custom_prompt = self.translate_prompt_text.get("1.0", tk.END).strip()
        if not custom_prompt:
            messagebox.showerror("错误", "请输入Prompt提示语")
            return
        # 使用标准 API 进行翻译
        self.translate_with_standard_api(custom_prompt)

# 启动主界面
if __name__ == "__main__":
    root = tk.Tk()
    app = TranslateApp(root)
    root.mainloop()