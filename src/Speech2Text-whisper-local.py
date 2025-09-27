import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import whisper
import textwrap  # 用于辅助文本处理，但现在主要用词分割

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

def select_file():
    """选择MP3文件"""
    file_path = filedialog.askopenfilename(title="Select MP3 File", filetypes=[("MP3 Files", "*.mp3")])
    if file_path:
        entry_file_path.delete(0, tk.END)
        entry_file_path.insert(0, file_path)

def split_long_segment(segment, max_chars=60):
    """使用词级时间戳将长段落分割成短字幕块"""
    if "words" not in segment or not segment["words"]:
        # 如果没有词时间戳，简单返回原段落（或可线性插值，但这里简化）
        return [(segment["start"], segment["end"], segment["text"].strip())]

    words = segment["words"]
    sub_segments = []
    current_text = ""
    current_start = segment["start"]
    current_words = []

    for word in words:
        word_text = word["word"].strip()
        if len(current_text) + len(word_text) + 1 > max_chars and current_words:
            # 达到最大长度，创建新块
            sub_segments.append((current_start, current_words[-1]["end"], current_text.strip()))
            current_text = ""
            current_start = word["start"]
            current_words = []
        
        current_text += word_text + " "
        current_words.append(word)

    # 添加最后一个子段落
    if current_words:
        sub_segments.append((current_start, current_words[-1]["end"], current_text.strip()))

    return sub_segments

def transcribe_audio():
    """执行转录并生成SRT"""
    mp3_path = entry_file_path.get()
    selected_language = combo_language.get()
    split_segments = var_split.get()  # 是否分割长段落

    if not mp3_path or not os.path.exists(mp3_path):
        messagebox.showerror("Error", "请选择有效的MP3文件。")
        return

    # 解析语言代码
    if selected_language.startswith("Auto Detect"):
        language_code = None
    else:
        # 从双语字符串提取ISO代码
        eng_name = selected_language.split(" (")[0]
        language_code = next((code for code, (eng, chn) in language_dict.items() if eng == eng_name), None)

    # 选择SRT保存路径
    default_srt = os.path.splitext(mp3_path)[0] + ".srt"
    srt_path = filedialog.asksaveasfilename(title="Save SRT File", defaultextension=".srt", initialfile=os.path.basename(default_srt), initialdir=os.path.dirname(mp3_path))
    if not srt_path:
        srt_path = default_srt

    try:
        log_text.insert(tk.END, "开始加载模型...\n")
        root.update()

        # 检查模型是否存在并提示下载
        model_name = "large-v3"
        model_path = os.path.expanduser(f"~/.cache/whisper/{model_name}.pt")
        if not os.path.exists(model_path):
            messagebox.showinfo("提示", "首次运行将下载模型（约3GB），请耐心等待。")
            log_text.insert(tk.END, "下载模型中...\n")
            root.update()

        # 加载模型
        model = whisper.load_model(model_name)

        log_text.insert(tk.END, "模型加载完成。开始转录（启用词级时间戳）...\n")
        root.update()

        # 转录音频，启用词级时间戳
        result = model.transcribe(
            mp3_path,
            language=language_code,
            fp16=True,  # GPU加速
            task="transcribe",
            verbose=True,
            word_timestamps=True  # 关键：启用词级时间戳
        )

        log_text.insert(tk.END, "转录完成。生成SRT文件...\n")
        root.update()

        # 写入SRT文件
        with open(srt_path, "w", encoding="utf-8") as f:
            subtitle_index = 1
            for segment in result["segments"]:
                if split_segments:
                    # 分割长段落
                    sub_segments = split_long_segment(segment)
                else:
                    # 不分割，使用原段落
                    sub_segments = [(segment["start"], segment["end"], segment["text"].strip())]

                for start, end, text in sub_segments:
                    # 格式化时间戳：逗号分隔，始终包括小时
                    start_ts = whisper.utils.format_timestamp(start, always_include_hours=True, decimal_marker=',')
                    end_ts = whisper.utils.format_timestamp(end, always_include_hours=True, decimal_marker=',')
                    # 可选：如果仍需内部分割长行
                    wrapped_text = "\n".join(textwrap.wrap(text, width=60))
                    f.write(f"{subtitle_index}\n{start_ts} --> {end_ts}\n{wrapped_text}\n\n")
                    subtitle_index += 1

        log_text.insert(tk.END, f"SRT文件已生成：{srt_path}（长段落已分割成短字幕）\n")
        messagebox.showinfo("成功", f"SRT文件已生成：{srt_path}")

    except Exception as e:
        log_text.insert(tk.END, f"错误：{str(e)}\n")
        messagebox.showerror("Error", f"发生错误：{str(e)}")

# 创建GUI窗口
root = tk.Tk()
root.title("MP3 to SRT Converter using Whisper")
root.geometry("600x400")  # 增大窗口

# MP3文件选择
label_file = tk.Label(root, text="MP3 文件:")
label_file.pack(pady=5)
entry_file_path = tk.Entry(root, width=60)
entry_file_path.pack()
button_select = tk.Button(root, text="浏览", command=select_file)
button_select.pack(pady=5)

# 语言选择
label_language = tk.Label(root, text="选择语言:")
label_language.pack(pady=5)
combo_language = tk.StringVar()
combo_menu = ttk.OptionMenu(root, combo_language, language_options[0], *language_options)  # 使用ttk以支持滚动
combo_menu.pack(fill=tk.X, padx=10)

# 分割选项（更新描述）
var_split = tk.BooleanVar(value=True)  # 默认启用
check_split = tk.Checkbutton(root, text="分割长段落成短字幕 (使用词级时间戳，每块最多60字符)", variable=var_split)
check_split.pack(pady=5)

# 运行按钮
button_run = tk.Button(root, text="转录为SRT", command=transcribe_audio)
button_run.pack(pady=10)

# 日志显示
label_log = tk.Label(root, text="日志:")
label_log.pack(pady=5)
log_text = tk.Text(root, height=8, width=70)
log_text.pack(pady=5, padx=10)

root.mainloop()