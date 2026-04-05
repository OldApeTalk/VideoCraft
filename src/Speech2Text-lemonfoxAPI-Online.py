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
        master.geometry("600x550")
        self._build_ui()
        if initial_file and os.path.exists(initial_file):
            self.entry_mp3_path.delete(0, tk.END)
            self.entry_mp3_path.insert(0, initial_file)

    def _build_ui(self):
        f = self.master

        tk.Label(f, text="MP3 文件:").pack(pady=5)
        self.entry_mp3_path = tk.Entry(f, width=60)
        self.entry_mp3_path.pack()
        tk.Button(f, text="浏览", command=self._select_mp3_file).pack(pady=5)

        tk.Label(f, text="选择语言:").pack(pady=5)
        self.combo_language = tk.StringVar(value=language_options[0])
        combo_menu = ttk.Combobox(f, textvariable=self.combo_language,
                                  values=language_options, state="readonly", width=40)
        combo_menu.pack(fill=tk.X, padx=10)

        self.translate_var = tk.BooleanVar()
        tk.Checkbutton(f, text="自动将识别的字幕转换为英语",
                       variable=self.translate_var).pack(pady=5)

        tk.Button(f, text="转录为原始SRT", command=self._transcribe_audio,
                  width=20).pack(pady=10)

        tk.Label(f, text="日志:").pack(pady=5)
        self.log_text = tk.Text(f, height=8, width=70)
        self.log_text.pack(pady=5, padx=10)

    def _select_mp3_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Audio/Video File",
            filetypes=[("Audio/Video Files", "*.mp3;*.mp4"),
                       ("MP3 Files", "*.mp3"), ("MP4 Files", "*.mp4")]
        )
        if file_path:
            self.entry_mp3_path.delete(0, tk.END)
            self.entry_mp3_path.insert(0, file_path)

    def _log(self, msg: str):
        """向内部日志文本框写一行。"""
        self.log_text.insert(tk.END, msg)
        self.log_text.see(tk.END)
        self.master.update_idletasks()

    def _transcribe_audio(self):
        """执行转录并生成原始SRT（不拆分）"""
        mp3_path = self.entry_mp3_path.get()
        selected_language = self.combo_language.get()
        api_key = router.get_asr_key("lemonfox")

        if not mp3_path or not os.path.exists(mp3_path):
            self._log("⚠ 请选择有效的MP3文件。\n")
            return

        if not api_key:
            self._log("⚠ LemonFox API Key 未配置，请在 AI Router 管理界面中设置。\n")
            logger.warning("LemonFox API Key 未配置")
            return

        # 解析语言
        if selected_language.startswith("Auto Detect"):
            api_lang = None
        else:
            eng_name = selected_language.split(" (")[0].lower()
            api_lang = eng_name

        # 生成默认文件名
        if selected_language.startswith("Auto Detect"):
            default_filename = "Auto_Detect.srt"
        else:
            eng_name = selected_language.split(" (")[0]
            default_filename = f"{eng_name}.srt"

        # 选择SRT保存路径
        srt_path = filedialog.asksaveasfilename(
            title="Save SRT File",
            defaultextension=".srt",
            initialfile=default_filename,
            initialdir=os.path.dirname(mp3_path)
        )
        if not srt_path:
            return  # 用户取消

        try:
            self._log("开始调用API进行转录...\n")

            url = "https://api.lemonfox.ai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {api_key}"}
            file_ext = os.path.splitext(mp3_path)[1].lower()
            mime_type = "video/mp4" if file_ext == ".mp4" else "audio/mpeg"
            files = {"file": (os.path.basename(mp3_path), open(mp3_path, "rb"), mime_type)}
            data = {"response_format": "srt"}
            if api_lang:
                data["language"] = api_lang
            if self.translate_var.get():
                data["translate_to_english"] = True

            response = requests.post(url, headers=headers, data=data, files=files)

            if not response.ok:
                raise Exception(f"API错误：{response.status_code} - {response.text}")

            raw_srt_content = response.text
            self._log(f"Raw SRT content from API (first 200 chars): {raw_srt_content[:200]}\n")

            srt_content = clean_srt_content(raw_srt_content)
            self._log(f"Cleaned SRT content (first 200 chars): {srt_content[:200]}\n")
            self._log("转录完成。生成SRT文件...\n")

            with open(srt_path, "w", encoding="utf-8", newline='') as f:
                f.write(srt_content)

            self._log(f"原始SRT文件已生成：{srt_path}\n")
            logger.info(f"语音转字幕完成 → {os.path.basename(srt_path)}")

        except Exception as e:
            self._log(f"错误：{str(e)}\n")
            logger.error(f"语音转字幕失败: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    initial = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None
    app = Speech2TextApp(root, initial_file=initial)
    root.mainloop()
