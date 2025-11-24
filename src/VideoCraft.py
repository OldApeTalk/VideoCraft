"""
VideoCraft - 视频制作工具集
VideoCraft - Video Production Toolkit

这是一个统一的视频制作工具入口，通过按钮调用各个功能模块，实现视频下载、字幕生成、翻译、切割和烧录等功能。
This is a unified video production toolkit entry point that calls various functional modules via buttons to achieve video downloading, subtitle generation, translation, splitting, and burning.

界面布局 / Interface Layout:
- 左边核心工作流 / Left Core Workflow: 视频制作的主要流程（下载→语音转字幕→翻译→烧录）
- 右边辅助工具 / Right Auxiliary Tools: 视频音频处理和视频切割工具

功能模块 / Functional Modules:
核心工作流 / Core Workflow:
1. 下载 / Download: yt-dlp-with simuheader ipv4.py - 使用 yt-dlp 下载 YouTube 视频，支持多种格式和音频提取。
   Download: yt-dlp-with simuheader ipv4.py - Download YouTube videos using yt-dlp, supporting multiple formats and audio extraction.

2. 语音转 SRT 字幕文件 / Speech to SRT Subtitle File: Speech2Text-lemonfoxAPI-Online.py - 使用 LemonFox API 将音频/视频转换为 SRT 字幕文件，支持多种语言。
   Speech to SRT Subtitle File: Speech2Text-lemonfoxAPI-Online.py - Convert audio/video to SRT subtitle files using LemonFox API, supporting multiple languages.

3. SRT 字幕文件翻译 / Translate SRT Subtitle File: Translate-srt.py - 使用 DeepL 或 Azure 翻译 SRT 字幕文件为中文。
   Translate SRT Subtitle File: Translate-srt.py - Translate SRT subtitle files to Chinese using DeepL or Azure.

4. 将字幕烧录到视频 / Burn Subtitles into Video: SubtitleTool.py - 统一的字幕处理工具，支持字幕分割和双语字幕烧录。
   Burn Subtitles into Video: SubtitleTool.py - Unified subtitle processing tool supporting subtitle splitting and bilingual subtitle burning.

辅助工具 / Auxiliary Tools:
6. VideoTools / VideoTools: VideoTools.py - 视频音频处理工具，包括音频提取、码率转换、音量调整。
   VideoTools: VideoTools.py - Video and audio processing tools, including audio extraction, bitrate conversion, and volume adjustment.

7. SplitVideo / SplitVideo: SplitVideo0.2.py - 视频分段切割工具，根据时间戳文件批量切割视频。
   SplitVideo: SplitVideo0.2.py - Video segment splitting tool that cuts videos in batches based on timestamp files.

设计理念 / Design Philosophy:
- 模块化设计，降低耦合度 / Modular design to reduce coupling
- 每个功能独立运行，通过统一入口调用 / Each function runs independently, called through a unified entry point
- 支持中英双语界面 / Support for Chinese and English interfaces
- 基于 Python 和相关库实现 / Implemented with Python and related libraries

作者 / Author: [Your Name]
版本 / Version: 2.0
更新日期 / Update Date: 2025-10-20
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
        self.root.geometry("1400x650")

        # 标题
        title_label = tk.Label(root, text="VideoCraft - 视频制作工具集", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=6, pady=20)

        # 核心工作流区域（左边）
        core_frame = tk.LabelFrame(root, text="核心工作流", padx=20, pady=10)
        core_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="n")

        tk.Label(core_frame, text="视频制作核心流程", font=("Arial", 12, "bold")).pack(pady=10)

        # 核心功能按钮
        core_functions = [
            ("下载视频 / Download", "yt-dlp-with simuheader ipv4.py"),
            ("语音转字幕 / Speech to SRT", "Speech2Text-lemonfoxAPI-Online.py"),
            ("翻译字幕 / Translate SRT", "Translate-srt-gemini.py"),
            ("烧录字幕 / Burn Subtitles", "SubtitleTool.py")
        ]

        for func_name, script_name in core_functions:
            btn = tk.Button(core_frame, text=func_name, command=lambda s=script_name: self.run_script(s), 
                           width=25, height=2, bg="#e8f5e8")
            btn.pack(pady=5)

        # 辅助工具区域（中间）
        tools_frame = tk.LabelFrame(root, text="辅助工具", padx=20, pady=10)
        tools_frame.grid(row=1, column=2, columnspan=2, padx=10, pady=10, sticky="n")

        tk.Label(tools_frame, text="视频处理辅助工具", font=("Arial", 12, "bold")).pack(pady=10)

        # VideoTools 按钮和描述
        video_tools_frame = tk.Frame(tools_frame)
        video_tools_frame.pack(pady=10)
        
        btn_video_tools = tk.Button(video_tools_frame, text="VideoTools\n视频音频工具", 
                                   command=lambda: self.run_script("VideoTools.py"), 
                                   width=20, height=3, bg="#e1f5fe", font=("Arial", 10))
        btn_video_tools.pack()
        
        tk.Label(video_tools_frame, text="• 音频提取为MP3\n• 转换MP3码率\n• 调整音量±20dB", 
                justify=tk.LEFT, font=("Arial", 9)).pack(pady=5)

        # SplitVideo 按钮和描述
        split_video_frame = tk.Frame(tools_frame)
        split_video_frame.pack(pady=10)
        
        btn_split_video = tk.Button(split_video_frame, text="SplitVideo\n视频分段切割", 
                                   command=lambda: self.run_script("SplitVideo0.2.py"), 
                                   width=20, height=3, bg="#f3e5f5", font=("Arial", 10))
        btn_split_video.pack()
        
        tk.Label(split_video_frame, text="• 根据时间戳切割视频\n• 支持关键帧对齐\n• 批量分段处理", 
                justify=tk.LEFT, font=("Arial", 9)).pack(pady=5)

        # SrtTools 按钮和描述
        srt_tools_frame = tk.Frame(tools_frame)
        srt_tools_frame.pack(pady=10)
        
        btn_srt_tools = tk.Button(srt_tools_frame, text="SrtTools\n字幕处理工具", 
                                   command=lambda: self.run_script("SrtTools.py"), 
                                   width=20, height=3, bg="#fff3e0", font=("Arial", 10))
        btn_srt_tools.pack()
        
        tk.Label(srt_tools_frame, text="• 生成YouTube片段\n• 提取段落内容\n• 生成视频标题\n• 提取字幕文本", 
                justify=tk.LEFT, font=("Arial", 9)).pack(pady=5)

        # 创作工具区域（右边）
        create_frame = tk.LabelFrame(root, text="创作工具", padx=20, pady=10)
        create_frame.grid(row=1, column=4, columnspan=2, padx=10, pady=10, sticky="n")

        tk.Label(create_frame, text="视频创作工具", font=("Arial", 12, "bold")).pack(pady=10)

        # Text2Video 按钮和描述
        text2video_frame = tk.Frame(create_frame)
        text2video_frame.pack(pady=10)
        
        btn_text2video = tk.Button(text2video_frame, text="Text2Video\n文本转视频", 
                                   command=lambda: self.run_script("text2Video.py"), 
                                   width=20, height=3, bg="#e8eaf6", font=("Arial", 10))
        btn_text2video.pack()
        
        tk.Label(text2video_frame, text="• 文本转语音(TTS)\n• 音频合成视频\n• 支持多种语音\n• Gemini TTS", 
                justify=tk.LEFT, font=("Arial", 9)).pack(pady=5)

        exit_btn = tk.Button(root, text="退出 / Exit", command=root.quit, width=20)
        exit_btn.grid(row=2, column=2, columnspan=2, pady=20)

    def run_script(self, script_name):
        try:
            # 获取当前脚本所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(current_dir, script_name)
            
            # 检查脚本是否存在
            if not os.path.exists(script_path):
                messagebox.showerror("错误 / Error", f"脚本文件不存在: {script_path}\nScript file not found: {script_path}")
                return

            # 使用虚拟环境的Python解释器
            venv_python = os.path.join(current_dir, "..", "myenv", "Scripts", "python.exe")
            if os.path.exists(venv_python):
                subprocess.Popen([venv_python, script_path])
            else:
                # 如果虚拟环境不存在，使用系统Python
                subprocess.Popen([sys.executable, script_path])
        except Exception as e:
            messagebox.showerror("错误 / Error", f"运行失败: {str(e)}\nFailed to run: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoCraftApp(root)
    root.mainloop()
