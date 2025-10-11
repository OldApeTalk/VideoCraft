"""
VideoCraft - 视频制作工具集
VideoCraft - Video Production Toolkit

这是一个统一的视频制作工具入口，通过按钮调用各个功能模块，实现视频下载、字幕生成、翻译、切割和烧录等功能。
This is a unified video production toolkit entry point that calls various functional modules via buttons to achieve video downloading, subtitle generation, translation, splitting, and burning.

功能模块 / Functional Modules:
1. 下载 / Download: yt-dlp-with simuheader ipv4.py - 使用 yt-dlp 下载 YouTube 视频，支持多种格式和音频提取。
   Download: yt-dlp-with simuheader ipv4.py - Download YouTube videos using yt-dlp, supporting multiple formats and audio extraction.

2. 语音转 SRT 字幕文件 / Speech to SRT Subtitle File: Speech2Text-lemonfoxAPI-Online.py - 使用 LemonFox API 将音频/视频转换为 SRT 字幕文件，支持多种语言。
   Speech to SRT Subtitle File: Speech2Text-lemonfoxAPI-Online.py - Convert audio/video to SRT subtitle files using LemonFox API, supporting multiple languages.

3. SRT 字幕文件翻译 / Translate SRT Subtitle File: Translate-srt.py - 使用 DeepL 或 Azure 翻译 SRT 字幕文件为中文。
   Translate SRT Subtitle File: Translate-srt.py - Translate SRT subtitle files to Chinese using DeepL or Azure.

4. SRT 文件适配屏幕的自动化切割 / Automatic Splitting of SRT Files for Screen Adaptation: SplitSubtitles.py - 自动拆分 SRT 字幕文件，使每行适应屏幕显示，支持中英文优化。
   Automatic Splitting of SRT Files for Screen Adaptation: SplitSubtitles.py - Automatically split SRT subtitle files to fit screen display, with Chinese and English optimization.

5. 将字幕烧录到视频 / Burn Subtitles into Video: AddSubTitleToMovieWithFFMpeg.py - 使用 FFmpeg 将中英双语字幕硬烧录到视频文件中。
   Burn Subtitles into Video: AddSubTitleToMovieWithFFMpeg.py - Use FFmpeg to hard-burn bilingual subtitles into video files.

设计理念 / Design Philosophy:
- 模块化设计，降低耦合度 / Modular design to reduce coupling
- 每个功能独立运行，通过统一入口调用 / Each function runs independently, called through a unified entry point
- 支持中英双语界面 / Support for Chinese and English interfaces
- 基于 Python 和相关库实现 / Implemented with Python and related libraries

作者 / Author: [Your Name]
版本 / Version: 1.0
更新日期 / Update Date: 2025-10-11
"""

import tkinter as tk
from tkinter import messagebox
import subprocess
import sys
import os

class VideoCraftApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VideoCraft - 视频制作工具集")
        self.root.geometry("600x400")

        # 标题
        title_label = tk.Label(root, text="VideoCraft\n视频制作工具集", font=("Arial", 16, "bold"))
        title_label.pack(pady=20)

        # 功能按钮
        functions = [
            ("下载 / Download", "yt-dlp-with simuheader ipv4.py"),
            ("语音转 SRT / Speech to SRT", "Speech2Text-lemonfoxAPI-Online.py"),
            ("翻译 SRT / Translate SRT", "Translate-srt.py"),
            ("切割 SRT / Split SRT", "SplitSubtitles.py"),
            ("烧录字幕 / Burn Subtitles", "AddSubTitleToMovieWithFFMpeg.py")
        ]

        for func_name, script_name in functions:
            btn = tk.Button(root, text=func_name, command=lambda s=script_name: self.run_script(s), width=30, height=2)
            btn.pack(pady=5)

        # 退出按钮
        exit_btn = tk.Button(root, text="退出 / Exit", command=root.quit, width=20)
        exit_btn.pack(pady=20)

    def run_script(self, script_name):
        try:
            # 获取当前脚本所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(current_dir, script_name)
            
            # 检查脚本是否存在
            if not os.path.exists(script_path):
                messagebox.showerror("错误 / Error", f"脚本文件不存在: {script_path}\nScript file not found: {script_path}")
                return

            # 运行脚本
            subprocess.Popen([sys.executable, script_path])
        except Exception as e:
            messagebox.showerror("错误 / Error", f"运行失败: {str(e)}\nFailed to run: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoCraftApp(root)
    root.mainloop()
