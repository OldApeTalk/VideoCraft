from tools.base import ToolBase
from i18n import tr
import i18n
import os
import sys
import tkinter as tk
from tkinter import filedialog, ttk
import requests
import textwrap  # for text helper utilities
import time
import threading
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

def build_language_options() -> list:
    """Build the combobox option list based on current UI locale.
    In zh mode shows bilingual "English (英语)" form; in en mode shows
    plain English names so the list isn't cluttered with Chinese text."""
    un_languages = ["ar", "zh", "en", "fr", "ru", "es"]
    other_languages = sorted([code for code in language_dict if code not in un_languages])
    ordered = un_languages + other_languages

    auto = tr("tool.speech.auto_detect")
    if i18n.get_current_lang() == "zh":
        return [auto] + [
            f"{language_dict[code][0]} ({language_dict[code][1]})" for code in ordered
        ]
    return [auto] + [language_dict[code][0] for code in ordered]

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
                log_callback(f"Block parse error: {str(e)} - block: {block[:100]}\n")
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


class Speech2TextApp(ToolBase):
    """语音转字幕工具（LemonFox API）— Toplevel 内嵌版。"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title(tr("tool.speech.title"))
        master.geometry("600x580")
        self._build_ui()
        if initial_file and os.path.exists(initial_file):
            self.entry_mp3_path.delete(0, tk.END)
            self.entry_mp3_path.insert(0, initial_file)
            self._auto_fill_output()

    def _build_ui(self):
        f = self.master

        # Source file
        tk.Label(f, text=tr("tool.speech.source_label")).pack(pady=(10, 2))
        row1 = tk.Frame(f)
        row1.pack(fill=tk.X, padx=10)
        self.entry_mp3_path = tk.Entry(row1, width=52)
        self.entry_mp3_path.pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(row1, text=tr("tool.speech.browse"), width=6,
                  command=self._select_mp3_file).pack(side=tk.LEFT, padx=(4, 0))

        # Output SRT
        tk.Label(f, text=tr("tool.speech.output_label")).pack(pady=(8, 2))
        row2 = tk.Frame(f)
        row2.pack(fill=tk.X, padx=10)
        self.entry_srt_path = tk.Entry(row2, width=52)
        self.entry_srt_path.pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(row2, text=tr("tool.speech.browse"), width=6,
                  command=self._select_srt_path).pack(side=tk.LEFT, padx=(4, 0))

        # Recognition language
        tk.Label(f, text=tr("tool.speech.language_label")).pack(pady=(8, 2))
        options = build_language_options()
        # Default to English (first non-auto entry, which is "English" or "English (英语)").
        default_value = next((o for o in options if o.startswith("English")), options[0])
        self.combo_language = tk.StringVar(value=default_value)
        self.combo_language.trace_add("write", lambda *_: self._auto_fill_output())
        combo_menu = ttk.Combobox(f, textvariable=self.combo_language,
                                  values=options, state="readonly", width=50)
        combo_menu.pack(fill=tk.X, padx=10)

        self.translate_var = tk.BooleanVar()
        tk.Checkbutton(f, text=tr("tool.speech.translate_to_en"),
                       variable=self.translate_var).pack(pady=(5, 0))

        self.speaker_var = tk.BooleanVar()
        tk.Checkbutton(f, text=tr("tool.speech.speaker_labels"),
                       variable=self.speaker_var).pack(pady=(0, 5))

        self.btn_transcribe = tk.Button(f, text=tr("tool.speech.btn_transcribe"),
                                        command=self._transcribe_audio,
                                        width=20, bg="#0078d4", fg="white")
        self.btn_transcribe.pack(pady=10)

        tk.Label(f, text=tr("tool.speech.log_label")).pack(pady=(0, 2))
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
            title=tr("tool.speech.dialog.select_audio"),
            filetypes=[(tr("tool.speech.filter.audio_video"), "*.mp3;*.mp4;*.wav;*.m4a;*.mkv"),
                       (tr("tool.speech.filter.all_files"), "*.*")]
        )
        if file_path:
            self.entry_mp3_path.delete(0, tk.END)
            self.entry_mp3_path.insert(0, file_path)
            self._auto_fill_output()

    def _select_srt_path(self):
        src = self.entry_mp3_path.get().strip()
        init_dir = os.path.dirname(src) if src else ""
        file_path = filedialog.asksaveasfilename(
            title=tr("tool.speech.dialog.save_srt"),
            defaultextension=".srt",
            filetypes=[(tr("tool.speech.filter.srt"), "*.srt")],
            initialdir=init_dir,
        )
        if file_path:
            self.entry_srt_path.delete(0, tk.END)
            self.entry_srt_path.insert(0, file_path)

    def _log(self, msg: str):
        """Append a message to the log text widget. Must be called from the main thread."""
        self.log_text.insert(tk.END, msg)
        self.log_text.see(tk.END)

    @staticmethod
    def _resolve_upload_mime(file_path: str) -> tuple[str, bool]:
        """Infer upload MIME type from extension, with safe fallback."""
        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".mp4": "video/mp4",
            ".mkv": "video/x-matroska",
        }
        if ext in mime_map:
            return mime_map[ext], False
        return "application/octet-stream", True

    @staticmethod
    def _build_request_data(api_lang: str | None, translate: bool, speaker: bool) -> list[tuple[str, str]]:
        data = [
            ("response_format", "verbose_json"),
            ("timestamp_granularities[]", "segment"),
            ("timestamp_granularities[]", "word"),
        ]
        if api_lang:
            data.append(("language", api_lang))
        if translate:
            data.append(("translate_to_english", "true"))
        if speaker:
            data.append(("speaker_labels", "true"))
        return data

    @staticmethod
    def _safe_int(value, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except Exception:
            return default
        return min(max(parsed, minimum), maximum)

    def _verbose_json_to_srt(self, data: dict) -> str:
        """将 verbose_json 响应的 segments 转换为 SRT 格式字符串。
        若 segment 含 speaker 字段（说话人区分模式），文本前置 [SPEAKER_xx]。
        """
        lines = []
        for i, seg in enumerate(data.get("segments", []), 1):
            start   = format_timestamp(seg["start"])
            end     = format_timestamp(seg["end"])
            text    = seg["text"].strip()
            speaker = seg.get("speaker", "")
            if speaker:
                text = f"[{speaker}] {text}"
            lines.append(f"{i}\n{start} --> {end}\n{text}\n")
        return "\n".join(lines)

    def _transcribe_audio(self):
        """Validate inputs on the main thread, then launch a background thread for the API call
        so the UI stays responsive during the (potentially long) transcription request."""
        mp3_path = self.entry_mp3_path.get()
        selected_language = self.combo_language.get()
        api_key = router.get_asr_key("lemonfox")

        if not mp3_path or not os.path.exists(mp3_path):
            self._log(tr("tool.speech.warning.no_audio"))
            return
        if not api_key:
            self._log(tr("tool.speech.warning.no_apikey"))
            logger.warning(tr("tool.speech.warning.no_apikey_log"))
            return

        srt_path = self.entry_srt_path.get().strip()
        if not srt_path:
            self._log(tr("tool.speech.warning.no_output"))
            return

        # Read all UI state on the main thread before handing off to the worker
        if selected_language.startswith("Auto Detect"):
            api_lang = None
        else:
            eng_name = selected_language.split(" (")[0].lower()
            api_lang = eng_name

        translate = self.translate_var.get()
        speaker   = self.speaker_var.get()

        self.btn_transcribe.config(state="disabled", text=tr("tool.speech.btn_running"))
        self.set_busy()
        self._log(tr("tool.speech.log.starting"))

        def _do_transcribe():
            import json as _json
            import re as _re

            def log(msg):
                # Route all log writes back to the main thread via after()
                self.master.after(0, self._log, msg)

            def set_btn_text(text):
                self.master.after(0, lambda t=text: self.btn_transcribe.config(text=t))

            def finish():
                # Re-enable button on the main thread when done or on error
                self.master.after(0, lambda: self.btn_transcribe.config(
                    state="normal", text=tr("tool.speech.btn_transcribe")))

            try:
                asr_cfg = router.get_asr_config("lemonfox") or {}
                url = asr_cfg.get("base_url") or "https://api.lemonfox.ai/v1/audio/transcriptions"
                headers = {"Authorization": f"Bearer {api_key}"}
                mime_type, used_fallback_mime = self._resolve_upload_mime(mp3_path)
                data = self._build_request_data(api_lang, translate, speaker)

                connect_timeout = self._safe_int(asr_cfg.get("connect_timeout_sec"), 60, 5, 300)
                read_timeout = self._safe_int(asr_cfg.get("read_timeout_sec"), 120, 30, 600)
                max_retries = self._safe_int(asr_cfg.get("max_retries"), 1, 1, 10)
                timeout = (connect_timeout, read_timeout)
                max_attempts = max_retries + 1

                log(tr("tool.speech.log.request_summary",
                       url=url,
                       filename=os.path.basename(mp3_path),
                       mime=mime_type,
                       language=api_lang or "auto",
                       translate=str(translate).lower(),
                       speaker=str(speaker).lower(),
                       timeout=f"{connect_timeout}/{read_timeout}"))
                if used_fallback_mime:
                    log(tr("tool.speech.warning.mime_fallback", mime=mime_type))

                result = None
                for attempt in range(1, max_attempts + 1):
                    wait_started_at = None
                    wait_stop_event = threading.Event()
                    state_lock = threading.Lock()
                    upload_reported = -1
                    wait_log_second = -1
                    waiting_started = False

                    def start_waiting_status():
                        nonlocal wait_started_at, waiting_started
                        with state_lock:
                            if waiting_started:
                                return
                            waiting_started = True
                            wait_started_at = time.time()
                        log(tr("tool.speech.log.state_waiting_start",
                               attempt=attempt, max=max_attempts))

                    def report_upload(uploaded: int, total: int):
                        nonlocal upload_reported
                        if total <= 0:
                            return
                        percent = int(uploaded * 100 / total)
                        if percent > 100:
                            percent = 100
                        with state_lock:
                            should_log = (percent != upload_reported and (percent % 5 == 0 or percent == 100))
                            if should_log:
                                upload_reported = percent
                        if should_log:
                            set_btn_text(tr("tool.speech.btn_uploading", percent=percent))
                            log(tr("tool.speech.log.state_uploading",
                                   attempt=attempt, max=max_attempts, percent=percent))
                        if percent >= 100:
                            start_waiting_status()

                    def wait_status_loop():
                        nonlocal wait_log_second
                        while not wait_stop_event.wait(1):
                            with state_lock:
                                started = wait_started_at
                            if started is None:
                                continue
                            elapsed = int(time.time() - started)
                            set_btn_text(tr("tool.speech.btn_waiting", elapsed=elapsed, total=read_timeout))
                            if elapsed != wait_log_second and elapsed % 5 == 0:
                                wait_log_second = elapsed
                                log(tr("tool.speech.log.state_waiting_tick",
                                       attempt=attempt, max=max_attempts,
                                       elapsed=elapsed, total=read_timeout))

                    wait_thread = threading.Thread(target=wait_status_loop, daemon=True)
                    wait_thread.start()

                    class ProgressFile:
                        def __init__(self, path: str, callback):
                            self._fp = open(path, "rb")
                            self._total = os.path.getsize(path)
                            self._uploaded = 0
                            self._callback = callback

                        def read(self, size=-1):
                            chunk = self._fp.read(size)
                            if chunk:
                                self._uploaded += len(chunk)
                                self._callback(self._uploaded, self._total)
                            else:
                                self._callback(self._total, self._total)
                            return chunk

                        def close(self):
                            self._fp.close()

                        def __getattr__(self, item):
                            return getattr(self._fp, item)

                    try:
                        progress_fp = ProgressFile(mp3_path, report_upload)
                        try:
                            files = {"file": (os.path.basename(mp3_path), progress_fp, mime_type)}
                            response = requests.post(
                                url,
                                headers=headers,
                                data=data,
                                files=files,
                                timeout=timeout,
                            )
                        finally:
                            progress_fp.close()
                        status_code = response.status_code
                        if not response.ok:
                            body_preview = (response.text or "")[:500]
                            raise RuntimeError(tr("tool.speech.error.api_error",
                                                  code=status_code, text=body_preview))

                        try:
                            result = response.json()
                        except ValueError:
                            raise RuntimeError(tr("tool.speech.error.invalid_json"))
                        break

                    except requests.exceptions.ConnectTimeout as e:
                        if attempt < max_attempts:
                            wait_s = min(2 ** attempt, 30)
                            log(tr("tool.speech.log.retry_connect_timeout",
                                   attempt=attempt, max=max_attempts, wait=wait_s))
                            time.sleep(wait_s)
                            continue
                        raise RuntimeError(tr("tool.speech.error.connect_timeout")) from e
                    except requests.exceptions.ReadTimeout as e:
                        if attempt < max_attempts:
                            wait_s = min(2 ** attempt, 30)
                            log(tr("tool.speech.log.retry_read_timeout",
                                   attempt=attempt, max=max_attempts, wait=wait_s))
                            time.sleep(wait_s)
                            continue
                        raise RuntimeError(tr("tool.speech.error.read_timeout")) from e
                    except requests.exceptions.ConnectionError as e:
                        if attempt < max_attempts:
                            wait_s = min(2 ** attempt, 30)
                            log(tr("tool.speech.log.retry_connection_error",
                                   attempt=attempt, max=max_attempts, wait=wait_s))
                            time.sleep(wait_s)
                            continue
                        raise RuntimeError(tr("tool.speech.error.connection_error")) from e
                    except requests.exceptions.RequestException as e:
                        raise RuntimeError(tr("tool.speech.error.request_exception",
                                              e=str(e))) from e
                    finally:
                        wait_stop_event.set()
                        set_btn_text(tr("tool.speech.btn_running"))

                if result is None:
                    raise RuntimeError(tr("tool.speech.error.no_result"))
                current_srt_path = srt_path

                # Resolve the detected language ISO code reported by the Whisper model
                detected_lang = result.get("language", "")
                if detected_lang:
                    iso_detected = next(
                        (code for code, (e, _) in language_dict.items()
                         if e.lower() == detected_lang.lower()),
                        detected_lang[:2].lower()
                    )
                    log(tr("tool.speech.log.detected_lang", detected=detected_lang, iso=iso_detected))

                    is_auto = selected_language.startswith("Auto Detect")
                    iso_selected = None
                    if not is_auto and api_lang:
                        iso_selected = next(
                            (code for code, (e, _) in language_dict.items()
                             if e.lower() == api_lang.lower()),
                            api_lang[:2].lower()
                        )
                    mismatch = (not is_auto) and iso_selected and (iso_selected != iso_detected)

                    if is_auto or mismatch:
                        if mismatch:
                            log(tr("tool.speech.log.lang_mismatch", selected=iso_selected, detected=iso_detected))
                            self.set_warning(tr("tool.speech.warning.lang_mismatch",
                                                selected=iso_selected, detected=iso_detected))
                        base_no_lang = _re.sub(r'_[a-z]{2,5}(\.srt)$', r'\1', current_srt_path)
                        current_srt_path = base_no_lang[:-4] + f"_{iso_detected}.srt"
                        self.master.after(0, lambda p=current_srt_path: (
                            self.entry_srt_path.delete(0, tk.END),
                            self.entry_srt_path.insert(0, p)
                        ))

                # Save raw verbose_json alongside the SRT for word-level timestamp access
                json_path = os.path.splitext(current_srt_path)[0] + ".json"
                with open(json_path, "w", encoding="utf-8") as jf:
                    _json.dump(result, jf, ensure_ascii=False, indent=2)
                log(tr("tool.speech.log.json_saved", path=json_path))

                # Build SRT from the segments array in the verbose_json response
                srt_content = self._verbose_json_to_srt(result)
                srt_content = clean_srt_content(srt_content)
                with open(current_srt_path, "w", encoding="utf-8", newline='') as sf:
                    sf.write(srt_content)

                log(tr("tool.speech.log.srt_saved", path=current_srt_path))
                log(tr("tool.speech.log.duration", seconds=result.get('duration', '?')))
                log(tr("tool.speech.log.segments", count=len(result.get('segments', []))))
                word_count = len(result.get("words", []))
                if word_count:
                    log(tr("tool.speech.log.words", count=word_count))
                logger.info(tr("tool.speech.log.complete", filename=os.path.basename(current_srt_path)))
                self.set_done()

            except Exception as e:
                log(tr("tool.speech.error.generic", e=str(e)))
                self.set_error(tr("tool.speech.error.transcribe_failed", e=e))
            finally:
                finish()

        threading.Thread(target=_do_transcribe, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    initial = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None
    app = Speech2TextApp(root, initial_file=initial)
    root.mainloop()
