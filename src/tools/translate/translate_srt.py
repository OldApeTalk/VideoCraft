from tools.base import ToolBase
import tkinter as tk
from tkinter import filedialog, ttk
import os
import sys
import srt
from hub_logger import logger
_SRC = os.path.dirname(os.path.abspath(__file__))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
from core.subtitle_ops import read_srt
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

# JSON Schema used by router.complete_json() for batch translation.
# Models are constrained to return {"translations": [{"index": int, "text": str}, ...]}
# where index matches the 【N】 marker in the prompt input (1-based).
_TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "text":  {"type": "string"},
                },
                "required": ["index", "text"],
            },
        },
    },
    "required": ["translations"],
}

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
class TranslateApp(ToolBase):
    def __init__(self, master, initial_file: str = None):
        from i18n import tr

        self.master = master
        master.title(tr("tool.translate.title"))
        master.geometry("700x430")
        master.resizable(False, False)

        # ── Row 0: AI 档位选择 + Router 管理 ──────────────────────────────────
        tk.Label(master, text=tr("tool.translate.tier")).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.tier_var = tk.StringVar(value=TIER_STANDARD)
        tier_frame = tk.Frame(master)
        tier_frame.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(tier_frame, text="高档 (最强)", variable=self.tier_var,
                        value=TIER_PREMIUM).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(tier_frame, text="中档 (推荐)", variable=self.tier_var,
                        value=TIER_STANDARD).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(tier_frame, text="低档 (经济)", variable=self.tier_var,
                        value=TIER_ECONOMY).pack(side=tk.LEFT)
        tk.Button(master, text=tr("tool.translate.router_manager"), command=self.open_router_manager
                  ).grid(row=0, column=2, padx=10)

        # ── Row 1: 源语言 ──────────────────────────────────────────────────────
        tk.Label(master, text=tr("tool.translate.source_lang")).grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.source_lang_var = tk.StringVar(value="English (英语)")
        self.source_combo = ttk.Combobox(master, textvariable=self.source_lang_var,
                                         values=language_options, state="readonly", width=30)
        self.source_combo.grid(row=1, column=1, columnspan=2, sticky="w", padx=(0, 10))

        # ── Row 2: 目标语言 ────────────────────────────────────────────────────
        tk.Label(master, text=tr("tool.translate.target_lang")).grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.target_lang_var = tk.StringVar(value="Chinese (中文)")
        self.target_combo = ttk.Combobox(master, textvariable=self.target_lang_var,
                                         values=language_options, state="readonly", width=30)
        self.target_combo.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0, 10))

        # ── Row 3: 批次大小 ────────────────────────────────────────────────────
        tk.Label(master, text=tr("tool.translate.batch_size")).grid(row=3, column=0, padx=10, pady=5, sticky="e")
        self.batch_size_var = tk.StringVar(value="100")
        batch_size_frame = tk.Frame(master)
        batch_size_frame.grid(row=3, column=1, columnspan=2, sticky="w", padx=(0, 10))
        ttk.Radiobutton(batch_size_frame, text="30",  variable=self.batch_size_var, value="30" ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(batch_size_frame, text="50",  variable=self.batch_size_var, value="50" ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(batch_size_frame, text="100", variable=self.batch_size_var, value="100").pack(side=tk.LEFT, padx=5)
        tk.Label(batch_size_frame, text="(批次越大越快，但可能影响准确性)",
                 font=("Arial", 8), fg="gray").pack(side=tk.LEFT, padx=5)

        # ── Row 4: SRT 文件 ────────────────────────────────────────────────────
        tk.Label(master, text=tr("tool.translate.source_label")).grid(row=4, column=0, padx=10, pady=10, sticky="e")
        self.srt_path_var = tk.StringVar()
        tk.Entry(master, textvariable=self.srt_path_var, width=50).grid(row=4, column=1, sticky="w")
        tk.Button(master, text=tr("tool.translate.browse"), command=self.select_srt).grid(row=4, column=2, padx=10)

        # ── Row 5: Prompt 编辑 ─────────────────────────────────────────────────
        tk.Label(master, text=tr("tool.translate.prompt_label")).grid(row=5, column=0, padx=10, pady=5, sticky="ne")
        self.translate_prompt_text = tk.Text(master, height=10, width=50, wrap=tk.WORD)
        self.translate_prompt_text.grid(row=5, column=1, columnspan=2, sticky="w", padx=(0, 10))
        default_translate_prompt = """You are a professional SRT subtitle translator. Translate the following subtitles from {source_lang_name} to {target_lang_name}.

The input is a batch of {batch_size} subtitles, each prefixed with a 【number】 marker to identify its position. Use the marker's number as the `index` in your response.

Rules:
1. Translate each subtitle independently. Do NOT merge, split, add, or remove subtitles — return exactly {batch_size} items.
2. Preserve line breaks and punctuation within each subtitle.
3. Do not wrap translations in quotation marks unless quotes are part of the original meaning.
4. Ensure natural, fluent {target_lang_name}.

Input subtitles (batch size = {batch_size}):
{numbered_input}
"""
        self.translate_prompt_text.insert(tk.END, default_translate_prompt)

        # ── Row 6: 翻译按钮 ────────────────────────────────────────────────────
        self.trans_btn = tk.Button(master, text=tr("tool.translate.btn_start"),
                                   command=self.translate_srt, width=20)
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

    def _set_status(self, msg: str):
        """Thread-safe status bar update; safe to call from any thread."""
        self.master.after(0, self.status_var.set, msg)

    def translate_with_standard_api(self, srt_path, source_lang, target_lang,
                                     custom_prompt, batch_size, tier):
        """Run the full translation pipeline in a background thread.
        All UI updates are posted back to the main thread via after(0, ...)."""
        def set_status(msg):
            self.master.after(0, self.status_var.set, msg)

        def finish():
            # Always re-enable the button, even on failure
            from i18n import tr as _tr
            self.master.after(0, lambda: self.trans_btn.config(state="normal", text=_tr("tool.translate.btn_start")))

        try:
            # Parse SRT on the worker thread (file I/O, no UI involved)
            try:
                subs = list(srt.parse(read_srt(srt_path)))
            except Exception as e:
                self.set_error(f"解析SRT文件失败: {e}")
                set_status(f"⚠ 解析SRT失败: {e}")
                return

            source_lang_name = SUPPORTED_LANGUAGES.get(source_lang, ('Unknown', '未知'))[0]
            target_lang_name = SUPPORTED_LANGUAGES.get(target_lang, ('Unknown', '未知'))[0]

            print(f"📋 准备翻译 {len(subs)} 条字幕")

            subtitle_contents = [f"【{i+1}】{sub.content}" for i, sub in enumerate(subs)]

            batches = []
            for i in range(0, len(subtitle_contents), batch_size):
                batches.append({'start_idx': i, 'contents': subtitle_contents[i:i + batch_size]})

            print(f"📦 分成 {len(batches)} 个批次进行翻译")

            translated_subs = {}

            for batch_idx, batch in enumerate(batches):
                set_status(f"正在翻译 ({source_lang.upper()} -> {target_lang.upper()}) - 批次 {batch_idx+1}/{len(batches)}")

                batch_start_idx = batch['start_idx']
                batch_contents  = batch['contents']
                cur_batch_size  = len(batch_contents)
                numbered_input  = '\n\n'.join(batch_contents)

                prompt = custom_prompt.replace("{source_lang_name}", source_lang_name)
                prompt = prompt.replace("{target_lang_name}", target_lang_name)
                prompt = prompt.replace("{batch_size}", str(cur_batch_size))
                prompt = prompt.replace("{numbered_input}", numbered_input)

                try:
                    parsed = router.complete_json(prompt, schema=_TRANSLATE_SCHEMA, tier=tier)
                except Exception as e:
                    print(f"  ❌ 批次 {batch_idx+1} JSON 调用失败: {e}")
                    # Fall back to original text so the overall translation task keeps going.
                    for i, original_line in enumerate(batch_contents):
                        # Strip the 【N】 marker from the original to leave plain text.
                        text_only = re.sub(r'^【\d+】\s*', '', original_line)
                        translated_subs[batch_start_idx + i] = text_only
                    if batch_idx < len(batches) - 1:
                        time.sleep(0.5)
                    continue

                items = parsed.get("translations", []) if isinstance(parsed, dict) else []
                if len(items) != cur_batch_size:
                    print(f"  ⚠️  批次 {batch_idx+1} 字幕数量不匹配: 期望 {cur_batch_size}, 实际 {len(items)}")
                else:
                    print(f"  ✅ 批次 {batch_idx+1} JSON 解析成功: {cur_batch_size} 条字幕")

                matched = 0
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    try:
                        local_idx = int(item.get("index", 0)) - 1
                    except (TypeError, ValueError):
                        continue
                    text = item.get("text", "")
                    if not isinstance(text, str):
                        continue
                    if 0 <= local_idx < cur_batch_size:
                        translated_subs[batch_start_idx + local_idx] = text
                        matched += 1

                # Fill any holes with the original line so output stays dense.
                for i in range(cur_batch_size):
                    global_idx = batch_start_idx + i
                    if global_idx not in translated_subs:
                        text_only = re.sub(r'^【\d+】\s*', '', batch_contents[i])
                        translated_subs[global_idx] = text_only

                print(f"  📍 批次 {batch_idx+1} 处理完成 (匹配 {matched}/{cur_batch_size})")

                if batch_idx < len(batches) - 1:
                    print("  ⏳ 等待0.5秒...")
                    time.sleep(0.5)

            # Apply translated content; keep originals for any subtitle that failed translation
            untranslated_count = 0
            for i, sub in enumerate(subs):
                if i in translated_subs:
                    sub.content = translated_subs[i]
                else:
                    untranslated_count += 1
                    print(f"字幕 {i+1} 未翻译，保持原文: '{sub.content[:50]}...'")

            if untranslated_count > 0:
                print(f"共 {untranslated_count} 条字幕未翻译，保持原文")
            else:
                print(f"成功: 所有 {len(subs)} 条字幕都已翻译")

            # Write output SRT named after the target language
            output_dir  = os.path.dirname(srt_path)
            output_file = os.path.join(output_dir, f"{target_lang_name}.srt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(srt.compose(subs))
            set_status(f"翻译完成，已保存: {output_file}")
            logger.info(f"翻译完成 → {os.path.basename(output_file)}")
            self.set_done()

        except Exception as e:
            self.set_error(f"翻译失败: {e}")
            set_status(f"✗ 翻译失败: {e}")
        finally:
            finish()

    def translate_srt(self):
        custom_prompt = self.translate_prompt_text.get("1.0", tk.END).strip()
        if not custom_prompt:
            self.status_var.set("⚠ 请输入Prompt提示语")
            return

        srt_path    = self.srt_path_var.get()
        source_lang = self.get_lang_code(self.source_lang_var.get())
        target_lang = self.get_lang_code(self.target_lang_var.get())
        batch_size  = int(self.batch_size_var.get())
        tier        = self.tier_var.get()

        if not srt_path or not os.path.exists(srt_path):
            self.status_var.set("⚠ 请选择有效的SRT文件")
            return
        if source_lang == target_lang:
            self.status_var.set("⚠ 源语言和目标语言不能相同")
            return

        from i18n import tr as _tr
        self.trans_btn.config(state="disabled", text=_tr("tool.translate.btn_running"))
        self.status_var.set(_tr("tool.translate.status_reading"))
        self.set_busy()

        threading.Thread(
            target=self.translate_with_standard_api,
            args=(srt_path, source_lang, target_lang, custom_prompt, batch_size, tier),
            daemon=True
        ).start()

# 启动主界面
if __name__ == "__main__":
    root = tk.Tk()
    app = TranslateApp(root)
    root.mainloop()