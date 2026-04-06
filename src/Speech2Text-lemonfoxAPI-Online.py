import os
import sys
import tkinter as tk
from tkinter import filedialog, ttk
import requests
import textwrap  # 用于辅助文本处理
from hub_logger import logger

# Whisper支持的语言字典：ISO代码 -> (英文名, 中文名)
# UN官方语言优先：ar, zh, en, fr, ru, es
# 其他按英文名字母顺序
language_dict = {
    "ar": ("Arabic", "阿拉伯语"),
    "zh": ("Chinese", "中文"),
    "en": ("English", "英语"),
    "fr": ("French", "法语"),
    "ru": ("Russian", "俄语"),
    "es": ("Spanish", "西班牙语"),
    "af": ("Afrikaans", "南非荷兰语"),
    "am": ("Amharic", "阿姆哈拉语"),
    "as": ("Assamese", "阿萨姆语"),
    "az": ("Azerbaijani", "阿塞拜疆语"),
    "ba": ("Bashkir", "巴什基尔语"),
    "be": ("Belarusian", "白俄罗斯语"),
    "bg": ("Bulgarian", "保加利亚语"),
    "bn": ("Bengali", "孟加拉语"),
    "bo": ("Tibetan", "藏语"),
    "br": ("Breton", "布列塔尼语"),
    "bs": ("Bosnian", "波斯尼亚语"),
    "ca": ("Catalan", "加泰罗尼亚语"),
    "cs": ("Czech", "捷克语"),
    "cy": ("Welsh", "威尔士语"),
    "da": ("Danish", "丹麦语"),
    "de": ("German", "德语"),
    "el": ("Greek", "希腊语"),
    "et": ("Estonian", "爱沙尼亚语"),
    "eu": ("Basque", "巴斯克语"),
    "fa": ("Persian", "波斯语"),
    "fi": ("Finnish", "芬兰语"),
    "fo": ("Faroese", "法罗语"),
    "gl": ("Galician", "加利西亚语"),
    "gu": ("Gujarati", "古吉拉特语"),
    "ha": ("Hausa", "豪萨语"),
    "haw": ("Hawaiian", "夏威夷语"),
    "he": ("Hebrew", "希伯来语"),
    "hi": ("Hindi", "印地语"),
    "hr": ("Croatian", "克罗地亚语"),
    "ht": ("Haitian Creole", "海地克里奥尔语"),
    "hu": ("Hungarian", "匈牙利语"),
    "hy": ("Armenian", "亚美尼亚语"),
    "id": ("Indonesian", "印度尼西亚语"),
    "is": ("Icelandic", "冰岛语"),
    "it": ("Italian", "意大利语"),
    "ja": ("Japanese", "日语"),
    "jw": ("Javanese", "爪哇语"),
    "ka": ("Georgian", "格鲁吉亚语"),
    "kk": ("Kazakh", "哈萨克语"),
    "km": ("Khmer", "高棉语"),
    "kn": ("Kannada", "卡纳达语"),
    "ko": ("Korean", "韩语"),
    "la": ("Latin", "拉丁语"),
    "lb": ("Luxembourgish", "卢森堡语"),
    "lo": ("Lao", "老挝语"),
    "lt": ("Lithuanian", "立陶宛语"),
    "lv": ("Latvian", "拉脱维亚语"),
    "mg": ("Malagasy", "马达加斯加语"),
    "mi": ("Maori", "毛利语"),
    "mk": ("Macedonian", "马其顿语"),
    "ml": ("Malayalam", "马拉雅拉姆语"),
    "mn": ("Mongolian", "蒙古语"),
    "mr": ("Marathi", "马拉地语"),
    "ms": ("Malay", "马来语"),
    "mt": ("Maltese", "马耳他语"),
    "my": ("Myanmar", "缅甸语"),
    "ne": ("Nepali", "尼泊尔语"),
    "nl": ("Dutch", "荷兰语"),
    "nn": ("Nynorsk", "挪威尼诺斯克语"),
    "no": ("Norwegian", "挪威语"),
    "oc": ("Occitan", "奥克语"),
    "pa": ("Punjabi", "旁遮普语"),
    "pl": ("Polish", "波兰语"),
    "ps": ("Pashto", "普什图语"),
    "pt": ("Portuguese", "葡萄牙语"),
    "ro": ("Romanian", "罗马尼亚语"),
    "sa": ("Sanskrit", "梵语"),
    "sd": ("Sindhi", "信德语"),
    "si": ("Sinhala", "僧伽罗语"),
    "sk": ("Slovak", "斯洛伐克语"),
    "sl": ("Slovenian", "斯洛文尼亚语"),
    "sn": ("Shona", "绍纳语"),
    "so": ("Somali", "索马里语"),
    "sq": ("Albanian", "阿尔巴尼亚语"),
    "sr": ("Serbian", "塞尔维亚语"),
    "su": ("Sundanese", "巽他语"),
    "sv": ("Swedish", "瑞典语"),
    "sw": ("Swahili", "斯瓦希里语"),
    "ta": ("Tamil", "泰米尔语"),
    "te": ("Telugu", "泰卢固语"),
    "tg": ("Tajik", "塔吉克语"),
    "th": ("Thai", "泰语"),
    "tk": ("Turkmen", "土库曼语"),
    "tl": ("Filipino", "菲律宾语"),
    "tr": ("Turkish", "土耳其语"),
    "tt": ("Tatar", "鞑靼语"),
    "uk": ("Ukrainian", "乌克兰语"),
    "ur": ("Urdu", "乌尔都语"),
    "uz": ("Uzbek", "乌兹别克语"),
    "vi": ("Vietnamese", "越南语"),
    "yi": ("Yiddish", "意第绪语"),
    "yo": ("Yoruba", "约鲁巴语"),
    "yue": ("Cantonese", "粤语")
}

# 生成双语选项列表
language_options = ["Auto Detect (自动检测，用于混合或未知语言)"]
un_languages = ["ar", "zh", "en", "fr", "ru", "es"]
other_languages = sorted([code for code in language_dict if code not in un_languages])

for code in un_languages + other_languages:
    eng, chn = language_dict[code]
    language_options.append(f"{eng} ({chn})")

from ai_router import router


def clean_srt_content(srt_content):
    """清理API返回的SRT内容"""
    if srt_content:
        srt_content_cleaned = srt_content.strip('"')
        srt_content_unescaped = srt_content_cleaned.replace('\\n', '\n')
        srt_content_fixed = srt_content_unescaped.replace('\r\n', '\n').replace('\n', '\r\n')
        return srt_content_fixed
    return ""


def parse_timestamp(ts_str):
    """解析SRT时间戳为秒，支持 ',' 或 '.' 作为小数分隔符"""
    if '.' in ts_str.rsplit(':', 1)[-1]:
        decimal = '.'
    elif ',' in ts_str.rsplit(':', 1)[-1]:
        decimal = ','
    else:
        raise ValueError(f"No decimal separator in {ts_str}")
    h, m, s_ms = ts_str.split(':')
    s, ms = s_ms.split(decimal)
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def format_timestamp(t, always_include_hours=True, decimal_marker=','):
    """格式化秒为SRT时间戳"""
    hours = int(t // 3600)
    mins = int((t % 3600) // 60)
    secs = int(t % 60)
    msecs = int(round((t - int(t)) * 1000))
    if always_include_hours or hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}{decimal_marker}{msecs:03d}"
    else:
        return f"{mins:02d}:{secs:02d}{decimal_marker}{msecs:03d}"


def parse_srt(srt_content, log_callback=None):
    """解析SRT内容为段落列表"""
    srt_content = srt_content.replace('\r', '')
    segments = []
    blocks = srt_content.strip().split('\n\n')
    for block in blocks:
        if not block:
            continue
        lines = block.split('\n')
        if len(lines) < 3:
            continue
        try:
            index = int(lines[0])
            time_line = lines[1].strip()
            start_str, end_str = [s.strip() for s in time_line.split('-->')]
            start = parse_timestamp(start_str)
            end = parse_timestamp(end_str)
            text = '\n'.join(lines[2:]).strip()
            segments.append((index, start, end, text))
        except Exception as e:
            if log_callback:
                log_callback(f"解析块错误：{str(e)} - 块内容：{block[:100]}\n")
    return segments


def split_long_segment(start, end, text, max_chars=60):
    """使用线性插值将长段落分割成短字幕块（无词级时间戳）"""
    text = text.strip()
    words = text.split()
    if not words:
        return [(start, end, "")]
    total_word_chars = sum(len(w) + 1 for w in words) - 1
    if total_word_chars == 0:
        return [(start, end, "")]
    duration = end - start
    sub_segments = []
    current_words = []
    cum_word_chars = 0
    for word in words:
        test_words = current_words + [word]
        test_text = ' '.join(test_words)
        if len(test_text) > max_chars and current_words:
            sub_text = ' '.join(current_words)
            sub_word_chars = len(sub_text)
            sub_start = start + (cum_word_chars / total_word_chars) * duration
            sub_end = start + ((cum_word_chars + sub_word_chars) / total_word_chars) * duration
            sub_segments.append((sub_start, sub_end, sub_text))
            cum_word_chars += sub_word_chars
            current_words = [word]
        else:
            current_words = test_words
    if current_words:
        sub_text = ' '.join(current_words)
        sub_word_chars = len(sub_text)
        sub_start = start + (cum_word_chars / total_word_chars) * duration
        sub_end = start + ((cum_word_chars + sub_word_chars) / total_word_chars) * duration
        sub_segments.append((sub_start, sub_end, sub_text))
    return sub_segments


class Speech2TextApp:
    """语音转字幕工具（LemonFox API）— Toplevel 内嵌版。"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("MP3 to SRT Converter using LemonFox API")
        master.geometry("600x580")
        self._build_ui()
        if initial_file and os.path.exists(initial_file):
            self.entry_mp3_path.delete(0, tk.END)
            self.entry_mp3_path.insert(0, initial_file)
            self._auto_fill_output()

    def _build_ui(self):
        f = self.master

        # 源文件
        tk.Label(f, text="音视频文件:").pack(pady=(10, 2))
        row1 = tk.Frame(f)
        row1.pack(fill=tk.X, padx=10)
        self.entry_mp3_path = tk.Entry(row1, width=52)
        self.entry_mp3_path.pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(row1, text="浏览", width=6,
                  command=self._select_mp3_file).pack(side=tk.LEFT, padx=(4, 0))

        # 输出 SRT
        tk.Label(f, text="输出 SRT 文件:").pack(pady=(8, 2))
        row2 = tk.Frame(f)
        row2.pack(fill=tk.X, padx=10)
        self.entry_srt_path = tk.Entry(row2, width=52)
        self.entry_srt_path.pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(row2, text="浏览", width=6,
                  command=self._select_srt_path).pack(side=tk.LEFT, padx=(4, 0))

        # 语言
        tk.Label(f, text="识别语言:").pack(pady=(8, 2))
        self.combo_language = tk.StringVar(value="English (英语)")
        self.combo_language.trace_add("write", lambda *_: self._auto_fill_output())
        combo_menu = ttk.Combobox(f, textvariable=self.combo_language,
                                  values=language_options, state="readonly", width=50)
        combo_menu.pack(fill=tk.X, padx=10)

        self.translate_var = tk.BooleanVar()
        tk.Checkbutton(f, text="自动将识别的字幕转换为英语",
                       variable=self.translate_var).pack(pady=5)

        tk.Button(f, text="转录为 SRT", command=self._transcribe_audio,
                  width=20, bg="#0078d4", fg="white").pack(pady=10)

        tk.Label(f, text="日志:").pack(pady=(0, 2))
        self.log_text = tk.Text(f, height=8, width=70)
        self.log_text.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)

    def _auto_fill_output(self):
        """根据源文件路径和语言自动生成输出 SRT 路径（语言用 ISO 码）。"""
        src = self.entry_mp3_path.get().strip()
        if not src:
            return
        base = os.path.splitext(src)[0]
        lang = self.combo_language.get()
        if lang.startswith("Auto Detect"):
            suffix = "auto"
        else:
            eng_name = lang.split(" (")[0]
            suffix = next(
                (code for code, (e, _) in language_dict.items() if e == eng_name),
                eng_name.lower()[:2]
            )
        out = f"{base}_{suffix}.srt"
        self.entry_srt_path.delete(0, tk.END)
        self.entry_srt_path.insert(0, out)

    def _select_mp3_file(self):
        file_path = filedialog.askopenfilename(
            title="选择音视频文件",
            filetypes=[("Audio/Video Files", "*.mp3;*.mp4;*.wav;*.m4a;*.mkv"),
                       ("All Files", "*.*")]
        )
        if file_path:
            self.entry_mp3_path.delete(0, tk.END)
            self.entry_mp3_path.insert(0, file_path)
            self._auto_fill_output()

    def _select_srt_path(self):
        src = self.entry_mp3_path.get().strip()
        init_dir = os.path.dirname(src) if src else ""
        file_path = filedialog.asksaveasfilename(
            title="保存 SRT 文件",
            defaultextension=".srt",
            filetypes=[("SRT Files", "*.srt")],
            initialdir=init_dir,
        )
        if file_path:
            self.entry_srt_path.delete(0, tk.END)
            self.entry_srt_path.insert(0, file_path)

    def _log(self, msg: str):
        """向内部日志文本框写一行。"""
        self.log_text.insert(tk.END, msg)
        self.log_text.see(tk.END)
        self.master.update_idletasks()

    def _verbose_json_to_srt(self, data: dict) -> str:
        """将 verbose_json 响应的 segments 转换为 SRT 格式字符串。"""
        lines = []
        for i, seg in enumerate(data.get("segments", []), 1):
            start = format_timestamp(seg["start"])
            end   = format_timestamp(seg["end"])
            text  = seg["text"].strip()
            lines.append(f"{i}\n{start} --> {end}\n{text}\n")
        return "\n".join(lines)

    def _transcribe_audio(self):
        """调用 verbose_json，同时保存 .json 和 .srt 两个文件。"""
        import json as _json
        mp3_path = self.entry_mp3_path.get()
        selected_language = self.combo_language.get()
        api_key = router.get_asr_key("lemonfox")

        if not mp3_path or not os.path.exists(mp3_path):
            self._log("⚠ 请选择有效的音视频文件。\n")
            return
        if not api_key:
            self._log("⚠ LemonFox API Key 未配置，请在 AI Router 管理界面中设置。\n")
            logger.warning("LemonFox API Key 未配置")
            return

        srt_path = self.entry_srt_path.get().strip()
        if not srt_path:
            self._log("⚠ 请指定输出 SRT 文件路径。\n")
            return

        # 解析语言参数
        if selected_language.startswith("Auto Detect"):
            api_lang = None
        else:
            eng_name = selected_language.split(" (")[0].lower()
            api_lang = eng_name

        try:
            self._log("开始调用 API（verbose_json 模式）...\n")

            url     = "https://api.lemonfox.ai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {api_key}"}
            file_ext = os.path.splitext(mp3_path)[1].lower()
            mime_type = "video/mp4" if file_ext == ".mp4" else "audio/mpeg"
            files = {"file": (os.path.basename(mp3_path), open(mp3_path, "rb"), mime_type)}
            data  = {"response_format": "verbose_json"}
            if api_lang:
                data["language"] = api_lang
            if self.translate_var.get():
                data["translate_to_english"] = True

            response = requests.post(url, headers=headers, data=data, files=files)
            if not response.ok:
                raise Exception(f"API错误：{response.status_code} - {response.text}")

            result = response.json()

            # 拿到实际识别语言
            detected_lang = result.get("language", "")  # Whisper 返回英文名，如 "english"
            if detected_lang:
                iso_detected = next(
                    (code for code, (e, _) in language_dict.items()
                     if e.lower() == detected_lang.lower()),
                    detected_lang[:2].lower()
                )
                self._log(f"检测到语言：{detected_lang} → ISO: {iso_detected}\n")

                # 判断是否需要重命名：
                # 1. Auto Detect 模式（srt_path 含 _auto）
                # 2. 指定了语言，但实际检测结果与选择不一致
                is_auto = selected_language.startswith("Auto Detect")
                iso_selected = api_lang[:2] if api_lang else None  # 已是小写英文名前两字母，粗略比较
                # 更精确：从 language_dict 反查选择语言的 ISO 码
                if not is_auto and api_lang:
                    iso_selected = next(
                        (code for code, (e, _) in language_dict.items()
                         if e.lower() == api_lang.lower()),
                        api_lang[:2].lower()
                    )
                mismatch = (not is_auto) and iso_selected and (iso_selected != iso_detected)

                if is_auto or mismatch:
                    if mismatch:
                        self._log(f"⚠ 选择语言({iso_selected}) 与检测结果({iso_detected})不符，按实际语言命名。\n")
                        logger.warning(f"语言不一致：选择 {iso_selected}，实际检测为 {iso_detected}，文件已按实际语言命名")
                    base_no_lang = srt_path
                    # 去掉原有语言后缀（_auto 或 _xx）
                    import re as _re
                    base_no_lang = _re.sub(r'_[a-z]{2,5}(\.srt)$', r'\1', srt_path)
                    new_srt = base_no_lang[:-4] + f"_{iso_detected}.srt"
                    self.entry_srt_path.delete(0, tk.END)
                    self.entry_srt_path.insert(0, new_srt)
                    srt_path = new_srt

            # 保存 verbose_json 原始文件
            json_path = os.path.splitext(srt_path)[0] + ".json"
            with open(json_path, "w", encoding="utf-8") as jf:
                _json.dump(result, jf, ensure_ascii=False, indent=2)
            self._log(f"verbose_json 已保存：{json_path}\n")

            # 从 segments 组装 SRT
            srt_content = self._verbose_json_to_srt(result)
            srt_content = clean_srt_content(srt_content)
            with open(srt_path, "w", encoding="utf-8", newline='') as sf:
                sf.write(srt_content)

            self._log(f"SRT 已生成：{srt_path}\n")
            self._log(f"音频时长：{result.get('duration', '?')} 秒\n")
            self._log(f"段落数：{len(result.get('segments', []))}\n")
            logger.info(f"语音转字幕完成 → {os.path.basename(srt_path)}")

        except Exception as e:
            self._log(f"错误：{str(e)}\n")
            logger.error(f"语音转字幕失败: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    initial = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None
    app = Speech2TextApp(root, initial_file=initial)
    root.mainloop()
