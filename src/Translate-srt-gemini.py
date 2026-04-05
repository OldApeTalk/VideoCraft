import tkinter as tk
from tkinter import filedialog, ttk
import os
import srt
from hub_logger import logger
import re
import time
import asyncio
import threading
import google.generativeai as genai
from ai_router import router, TIER_PREMIUM, TIER_STANDARD, TIER_ECONOMY

# 尝试导入pydub，如果不可用则设置为None
# 注意：当前Live API实现仍使用文本翻译，pydub仅为未来音频处理功能预留
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    AudioSegment = None
    PYDUB_AVAILABLE = False

# 支持的语言列表 (语言代码 -> (英文名, 中文名))
# 与 Speech2Text-lemonfoxAPI-Online.py 中的 language_dict 保持一致
# UN官方语言优先：ar, zh, en, fr, ru, es
# 其他按英文名字母顺序
SUPPORTED_LANGUAGES = {
    'auto': ('Auto Detect', '自动检测'),
    'ar': ('Arabic', '阿拉伯语'),
    'zh': ('Chinese', '中文'),
    'en': ('English', '英语'),
    'fr': ('French', '法语'),
    'ru': ('Russian', '俄语'),
    'es': ('Spanish', '西班牙语'),
    'af': ('Afrikaans', '南非荷兰语'),
    'am': ('Amharic', '阿姆哈拉语'),
    'as': ('Assamese', '阿萨姆语'),
    'az': ('Azerbaijani', '阿塞拜疆语'),
    'ba': ('Bashkir', '巴什基尔语'),
    'be': ('Belarusian', '白俄罗斯语'),
    'bg': ('Bulgarian', '保加利亚语'),
    'bn': ('Bengali', '孟加拉语'),
    'bo': ('Tibetan', '藏语'),
    'br': ('Breton', '布列塔尼语'),
    'bs': ('Bosnian', '波斯尼亚语'),
    'ca': ('Catalan', '加泰罗尼亚语'),
    'cs': ('Czech', '捷克语'),
    'cy': ('Welsh', '威尔士语'),
    'da': ('Danish', '丹麦语'),
    'de': ('German', '德语'),
    'el': ('Greek', '希腊语'),
    'et': ('Estonian', '爱沙尼亚语'),
    'eu': ('Basque', '巴斯克语'),
    'fa': ('Persian', '波斯语'),
    'fi': ('Finnish', '芬兰语'),
    'fo': ('Faroese', '法罗语'),
    'gl': ('Galician', '加利西亚语'),
    'gu': ('Gujarati', '古吉拉特语'),
    'ha': ('Hausa', '豪萨语'),
    'haw': ('Hawaiian', '夏威夷语'),
    'he': ('Hebrew', '希伯来语'),
    'hi': ('Hindi', '印地语'),
    'hr': ('Croatian', '克罗地亚语'),
    'ht': ('Haitian Creole', '海地克里奥尔语'),
    'hu': ('Hungarian', '匈牙利语'),
    'hy': ('Armenian', '亚美尼亚语'),
    'id': ('Indonesian', '印度尼西亚语'),
    'is': ('Icelandic', '冰岛语'),
    'it': ('Italian', '意大利语'),
    'ja': ('Japanese', '日语'),
    'jw': ('Javanese', '爪哇语'),
    'ka': ('Georgian', '格鲁吉亚语'),
    'kk': ('Kazakh', '哈萨克语'),
    'km': ('Khmer', '高棉语'),
    'kn': ('Kannada', '卡纳达语'),
    'ko': ('Korean', '韩语'),
    'la': ('Latin', '拉丁语'),
    'lb': ('Luxembourgish', '卢森堡语'),
    'ln': ('Lingala', '林加拉语'),
    'lo': ('Lao', '老挝语'),
    'lt': ('Lithuanian', '立陶宛语'),
    'lv': ('Latvian', '拉脱维亚语'),
    'mg': ('Malagasy', '马达加斯加语'),
    'mi': ('Maori', '毛利语'),
    'mk': ('Macedonian', '马其顿语'),
    'ml': ('Malayalam', '马拉雅拉姆语'),
    'mn': ('Mongolian', '蒙古语'),
    'mr': ('Marathi', '马拉地语'),
    'ms': ('Malay', '马来语'),
    'mt': ('Maltese', '马耳他语'),
    'my': ('Myanmar', '缅甸语'),
    'ne': ('Nepali', '尼泊尔语'),
    'nl': ('Dutch', '荷兰语'),
    'nn': ('Norwegian Nynorsk', '新挪威语'),
    'no': ('Norwegian', '挪威语'),
    'oc': ('Occitan', '奥克语'),
    'pa': ('Punjabi', '旁遮普语'),
    'pl': ('Polish', '波兰语'),
    'ps': ('Pashto', '普什图语'),
    'pt': ('Portuguese', '葡萄牙语'),
    'ro': ('Romanian', '罗马尼亚语'),
    'sa': ('Sanskrit', '梵语'),
    'sd': ('Sindhi', '信德语'),
    'si': ('Sinhala', '僧伽罗语'),
    'sk': ('Slovak', '斯洛伐克语'),
    'sl': ('Slovenian', '斯洛文尼亚语'),
    'sn': ('Shona', '绍纳语'),
    'so': ('Somali', '索马里语'),
    'sq': ('Albanian', '阿尔巴尼亚语'),
    'sr': ('Serbian', '塞尔维亚语'),
    'su': ('Sundanese', '巽他语'),
    'sv': ('Swedish', '瑞典语'),
    'sw': ('Swahili', '斯瓦希里语'),
    'ta': ('Tamil', '泰米尔语'),
    'te': ('Telugu', '泰卢固语'),
    'tg': ('Tajik', '塔吉克语'),
    'th': ('Thai', '泰语'),
    'tk': ('Turkmen', '土库曼语'),
    'tl': ('Tagalog', '他加禄语'),
    'tr': ('Turkish', '土耳其语'),
    'tt': ('Tatar', '鞑靼语'),
    'uk': ('Ukrainian', '乌克兰语'),
    'ur': ('Urdu', '乌尔都语'),
    'uz': ('Uzbek', '乌兹别克语'),
    'vi': ('Vietnamese', '越南语'),
    'yi': ('Yiddish', '意第绪语'),
    'yo': ('Yoruba', '约鲁巴语'),
    'yue': ('Cantonese', '粤语'),
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

# 生成双语选项列表（与 Speech2Text-lemonfoxAPI-Online.py 保持一致）
language_options = ["Auto Detect (自动检测，用于混合或未知语言)"]
un_languages = ["ar", "zh", "en", "fr", "ru", "es"]
other_languages = sorted([code for code in SUPPORTED_LANGUAGES if code not in un_languages and code != 'auto'])

for code in un_languages + other_languages:
    eng, chn = SUPPORTED_LANGUAGES[code]
    language_options.append(f"{eng} ({chn})")

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
    def __init__(self, master, initial_file: str = None):
        self.master = master
        master.title("SRT 字幕批量翻译")
        master.geometry("700x430")
        master.resizable(False, False)

        # ── Row 0: AI 档位选择 + Router 管理 ──────────────────────────────────
        tk.Label(master, text="AI 档位:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.tier_var = tk.StringVar(value=TIER_STANDARD)
        tier_frame = tk.Frame(master)
        tier_frame.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(tier_frame, text="高档 (最强)", variable=self.tier_var,
                        value=TIER_PREMIUM).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(tier_frame, text="中档 (推荐)", variable=self.tier_var,
                        value=TIER_STANDARD).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(tier_frame, text="低档 (经济)", variable=self.tier_var,
                        value=TIER_ECONOMY).pack(side=tk.LEFT)
        tk.Button(master, text="Router 管理", command=self.open_router_manager
                  ).grid(row=0, column=2, padx=10)

        # ── Row 1: 源语言 ──────────────────────────────────────────────────────
        tk.Label(master, text="源语言 (Source):").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.source_lang_var = tk.StringVar(value="English (英语)")
        self.source_combo = ttk.Combobox(master, textvariable=self.source_lang_var,
                                         values=language_options, state="readonly", width=30)
        self.source_combo.grid(row=1, column=1, columnspan=2, sticky="w", padx=(0, 10))

        # ── Row 2: 目标语言 ────────────────────────────────────────────────────
        tk.Label(master, text="目标语言 (Target):").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.target_lang_var = tk.StringVar(value="Chinese (中文)")
        self.target_combo = ttk.Combobox(master, textvariable=self.target_lang_var,
                                         values=language_options, state="readonly", width=30)
        self.target_combo.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0, 10))

        # ── Row 3: 批次大小 ────────────────────────────────────────────────────
        tk.Label(master, text="每批次字幕条数:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        self.batch_size_var = tk.StringVar(value="100")
        batch_size_frame = tk.Frame(master)
        batch_size_frame.grid(row=3, column=1, columnspan=2, sticky="w", padx=(0, 10))
        ttk.Radiobutton(batch_size_frame, text="30",  variable=self.batch_size_var, value="30" ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(batch_size_frame, text="50",  variable=self.batch_size_var, value="50" ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(batch_size_frame, text="100", variable=self.batch_size_var, value="100").pack(side=tk.LEFT, padx=5)
        tk.Label(batch_size_frame, text="(批次越大越快，但可能影响准确性)",
                 font=("Arial", 8), fg="gray").pack(side=tk.LEFT, padx=5)

        # ── Row 4: SRT 文件 ────────────────────────────────────────────────────
        tk.Label(master, text="原始SRT文件:").grid(row=4, column=0, padx=10, pady=10, sticky="e")
        self.srt_path_var = tk.StringVar()
        tk.Entry(master, textvariable=self.srt_path_var, width=50).grid(row=4, column=1, sticky="w")
        tk.Button(master, text="浏览", command=self.select_srt).grid(row=4, column=2, padx=10)

        # ── Row 5: Prompt 编辑 ─────────────────────────────────────────────────
        tk.Label(master, text="Prompt提示语:").grid(row=5, column=0, padx=10, pady=5, sticky="ne")
        self.translate_prompt_text = tk.Text(master, height=10, width=50, wrap=tk.WORD)
        self.translate_prompt_text.grid(row=5, column=1, columnspan=2, sticky="w", padx=(0, 10))
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

        # ── Row 6: 翻译按钮 ────────────────────────────────────────────────────
        self.trans_btn = tk.Button(master, text="开始翻译", command=self.translate_srt, width=20)
        self.trans_btn.grid(row=6, column=1, pady=20)

        # ── Row 7: 状态栏 ──────────────────────────────────────────────────────
        self.status_var = tk.StringVar()
        tk.Label(master, textvariable=self.status_var, fg="blue").grid(
            row=7, column=0, columnspan=3, pady=5)

        if initial_file:
            self.srt_path_var.set(initial_file)

    def open_router_manager(self):
        from router_manager import open_router_manager
        open_router_manager(self.master)

    def get_lang_code(self, lang_str):
        """从语言选择字符串中提取语言代码（与 Speech2Text 保持一致）"""
        # 处理 Auto Detect
        if lang_str.startswith("Auto Detect"):
            return 'auto'
        
        # 从双语字符串提取英文名并转为小写，然后查找对应代码
        eng_name = lang_str.split(" (")[0]
        
        # 在 SUPPORTED_LANGUAGES 中查找匹配的语言代码
        for code, (english, chinese) in SUPPORTED_LANGUAGES.items():
            if english == eng_name:
                return code
        
        return 'en'  # 默认返回英语

    def select_srt(self):
        path = filedialog.askopenfilename(title="选择SRT文件", filetypes=[("SRT files", "*.srt")])
        if path:
            self.srt_path_var.set(path)

    def translate_with_standard_api(self, custom_prompt=None):
        srt_path = self.srt_path_var.get()
        source_lang = self.get_lang_code(self.source_lang_var.get())
        target_lang = self.get_lang_code(self.target_lang_var.get())
        
        if not srt_path or not os.path.exists(srt_path):
            self.status_var.set("⚠ 请选择有效的SRT文件")
            return

        if source_lang == target_lang:
            self.status_var.set("⚠ 源语言和目标语言不能相同")
            return
            
        self.status_var.set("正在读取字幕...")
        self.master.update()
        
        # 读取SRT
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                subs = list(srt.parse(f))
        except Exception as e:
            logger.error(f"解析SRT文件失败: {e}")
            self.status_var.set(f"⚠ 解析SRT失败: {e}")
            return
            
        # Gemini翻译逻辑：分批发送，请求间隔6秒
        try:
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

                translated_batch = router.complete(prompt, tier=self.tier_var.get())

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

                # API调用间隔，避免速率限制（付费版：0.5秒 ≈ 120 RPM）
                if batch_idx < len(batches) - 1:
                    print("  ⏳ 等待0.5秒...")
                    import time
                    time.sleep(0.5)

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
            logger.error(f"翻译失败: {e}")
            self.status_var.set(f"✗ 翻译失败: {e}")
            return
        
        # 输出
        target_lang_name = SUPPORTED_LANGUAGES[target_lang][0]  # 获取目标语言的英文名
        output_dir = os.path.dirname(srt_path)  # 获取原文件的目录
        output_file = os.path.join(output_dir, f"{target_lang_name}.srt")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(srt.compose(subs))
            self.status_var.set(f"翻译完成，已保存: {output_file}")
            logger.info(f"翻译完成 → {os.path.basename(output_file)}")
        except Exception as e:
            logger.error(f"保存翻译结果失败: {e}")
            self.status_var.set(f"✗ 保存失败: {e}")

    def translate_srt(self):
        custom_prompt = self.translate_prompt_text.get("1.0", tk.END).strip()
        if not custom_prompt:
            self.status_var.set("⚠ 请输入Prompt提示语")
            return
        # 使用标准 API 进行翻译
        self.translate_with_standard_api(custom_prompt)

# 启动主界面
if __name__ == "__main__":
    root = tk.Tk()
    app = TranslateApp(root)
    root.mainloop()