import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import requests
import textwrap  # 用于辅助文本处理

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
    "ln": ("Lingala", "林加拉语"),
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
    "nn": ("Norwegian Nynorsk", "新挪威语"),
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
    "tl": ("Tagalog", "他加禄语"),
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

KEY_FILE = "lemonfox.key"

def select_mp3_file():
    """选择音频/视频文件"""
    file_path = filedialog.askopenfilename(
        title="Select Audio/Video File",
        filetypes=[("Audio/Video Files", "*.mp3;*.mp4"), ("MP3 Files", "*.mp3"), ("MP4 Files", "*.mp4")]
    )
    if file_path:
        entry_mp3_path.delete(0, tk.END)
        entry_mp3_path.insert(0, file_path)

def load_key():
    """加载保存的API Key"""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r") as f:
            key = f.read().strip()
            entry_api_key.delete(0, tk.END)
            entry_api_key.insert(0, key)

def save_key():
    """保存API Key到文件"""
    api_key = entry_api_key.get().strip()
    if not api_key:
        messagebox.showerror("Error", "请输入有效的API Key。")
        return
    with open(KEY_FILE, "w") as f:
        f.write(api_key)
    messagebox.showinfo("成功", "API Key 已保存。")

def delete_key():
    """删除API Key文件"""
    if os.path.exists(KEY_FILE):
        os.remove(KEY_FILE)
        entry_api_key.delete(0, tk.END)
        messagebox.showinfo("成功", "API Key 文件已删除。")
    else:
        messagebox.showinfo("信息", "没有找到 API Key 文件。")

def clean_srt_content(srt_content):
    """清理API返回的SRT内容"""
    if srt_content:
        # 移除周围引号
        srt_content_cleaned = srt_content.strip('"')
        # 将转义的 \\n 转换为实际换行符 \n
        srt_content_unescaped = srt_content_cleaned.replace('\\n', '\n')
        # 将所有换行符标准化为 \r\n
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

def parse_srt(srt_content):
    """解析SRT内容为段落列表"""
    # 移除 \r 以处理 Windows 行结束符
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
            # 如果文本有多行，保留 \n
            text = '\n'.join(lines[2:]).strip()
            segments.append((index, start, end, text))
        except Exception as e:
            log_text.insert(tk.END, f"解析块错误：{str(e)} - 块内容：{block[:100]}\n")
            pass  # 跳过无效块
    return segments

def split_long_segment(start, end, text, max_chars=60):
    """使用线性插值将长段落分割成短字幕块（无词级时间戳）"""
    text = text.strip()
    words = text.split()
    if not words:
        return [(start, end, "")]
    
    total_word_chars = sum(len(w) + 1 for w in words) - 1  # 近似包括空格
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
            sub_word_chars = len(sub_text)  # 使用实际长度
            sub_start = start + (cum_word_chars / total_word_chars) * duration
            sub_end = start + ((cum_word_chars + sub_word_chars) / total_word_chars) * duration
            sub_segments.append((sub_start, sub_end, sub_text))
            cum_word_chars += sub_word_chars
            current_words = [word]
        else:
            current_words = test_words
    
    # 添加最后一个子段落
    if current_words:
        sub_text = ' '.join(current_words)
        sub_word_chars = len(sub_text)
        sub_start = start + (cum_word_chars / total_word_chars) * duration
        sub_end = start + ((cum_word_chars + sub_word_chars) / total_word_chars) * duration
        sub_segments.append((sub_start, sub_end, sub_text))
    
    return sub_segments

def transcribe_audio():
    """执行转录并生成原始SRT（不拆分）"""
    mp3_path = entry_mp3_path.get()
    selected_language = combo_language.get()
    api_key = entry_api_key.get().strip()

    if not mp3_path or not os.path.exists(mp3_path):
        messagebox.showerror("Error", "请选择有效的MP3文件。")
        return
    
    if not api_key:
        messagebox.showerror("Error", "请输入有效的API Key。")
        return

    # 解析语言
    if selected_language.startswith("Auto Detect"):
        api_lang = None
    else:
        # 从双语字符串提取英文名并小写
        eng_name = selected_language.split(" (")[0].lower()
        api_lang = eng_name

    # 选择SRT保存路径
    default_srt = os.path.splitext(mp3_path)[0] + ".srt"
    srt_path = filedialog.asksaveasfilename(title="Save SRT File", defaultextension=".srt", initialfile=os.path.basename(default_srt), initialdir=os.path.dirname(mp3_path))
    if not srt_path:
        return  # 用户取消了路径选择，不进行转录

    try:
        log_text.insert(tk.END, "开始调用API进行转录...\n")
        root.update()

        # 调用LemonFox API
        url = "https://api.lemonfox.ai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"}
        file_ext = os.path.splitext(mp3_path)[1].lower()
        if file_ext == ".mp4":
            mime_type = "video/mp4"
        else:
            mime_type = "audio/mpeg"
        files = {"file": (os.path.basename(mp3_path), open(mp3_path, "rb"), mime_type)}
        data = {"response_format": "srt"}
        if api_lang:
            data["language"] = api_lang
        if translate_var.get():
            data["translate_to_english"] = True

        response = requests.post(url, headers=headers, data=data, files=files)

        if not response.ok:
            raise Exception(f"API错误：{response.status_code} - {response.text}")

        raw_srt_content = response.text
        log_text.insert(tk.END, f"Raw SRT content from API (first 200 chars): {raw_srt_content[:200]}\n")
        root.update()

        srt_content = clean_srt_content(raw_srt_content)
        log_text.insert(tk.END, f"Cleaned SRT content (first 200 chars): {srt_content[:200]}\n")
        root.update()

        log_text.insert(tk.END, "转录完成。生成SRT文件...\n")
        root.update()

        # 保存清理后的原始SRT
        with open(srt_path, "w", encoding="utf-8", newline='') as f:
            f.write(srt_content)

        log_text.insert(tk.END, f"原始SRT文件已生成：{srt_path}\n")
        messagebox.showinfo("成功", f"原始SRT文件已生成：{srt_path}")

    except Exception as e:
        log_text.insert(tk.END, f"错误：{str(e)}\n")
        messagebox.showerror("Error", f"发生错误：{str(e)}")


# 创建GUI窗口
root = tk.Tk()
root.title("MP3 to SRT Converter using LemonFox API")
root.geometry("600x550")  # 增大窗口以容纳额外部分

# MP3文件选择
label_mp3 = tk.Label(root, text="MP3 文件:")
label_mp3.pack(pady=5)
entry_mp3_path = tk.Entry(root, width=60)
entry_mp3_path.pack()
button_select_mp3 = tk.Button(root, text="浏览", command=select_mp3_file)
button_select_mp3.pack(pady=5)

# API Key输入
label_api_key = tk.Label(root, text="LemonFox API Key:")
label_api_key.pack(pady=5)
api_key_var = tk.StringVar()
entry_api_key = tk.Entry(root, width=60, textvariable=api_key_var, show="*")
entry_api_key.pack(pady=5)

def toggle_key_visibility():
    if entry_api_key.cget('show') == '*':
        entry_api_key.config(show='')
        button_toggle_key.config(text="隐藏 Key")
    else:
        entry_api_key.config(show='*')
        button_toggle_key.config(text="显示 Key")

button_toggle_key = tk.Button(root, text="显示 Key", command=toggle_key_visibility)
button_toggle_key.pack(pady=2)

# Key管理按钮
frame_key_buttons = tk.Frame(root)
frame_key_buttons.pack(pady=5)
button_save_key = tk.Button(frame_key_buttons, text="保存 Key", command=save_key)
button_save_key.pack(side=tk.LEFT, padx=5)
button_delete_key = tk.Button(frame_key_buttons, text="删除 Key", command=delete_key)
button_delete_key.pack(side=tk.LEFT, padx=5)

# 语言选择
label_language = tk.Label(root, text="选择语言:")
label_language.pack(pady=5)
combo_language = tk.StringVar()
combo_menu = ttk.OptionMenu(root, combo_language, language_options[0], *language_options)  # 使用ttk以支持滚动
combo_menu.pack(fill=tk.X, padx=10)

# 自动转换为英语复选框
translate_var = tk.BooleanVar()
check_translate = tk.Checkbutton(root, text="自动将识别的字幕转换为英语", variable=translate_var)
check_translate.pack(pady=5)

# 转录按钮（仅生成原始SRT）
button_transcribe = tk.Button(root, text="转录为原始SRT", command=transcribe_audio)
button_transcribe.pack(pady=10)

# 日志显示
label_log = tk.Label(root, text="日志:")
label_log.pack(pady=5)
log_text = tk.Text(root, height=8, width=70)
log_text.pack(pady=5, padx=10)

# 加载保存的Key
load_key()

root.mainloop()