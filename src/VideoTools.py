# 这里汇集处理视频的工具，当然也包含音频的一些小功能
# 1、音频提取mp3，可以选择不同的码率
# 2、转换mp3的码率
# 3、调整音量，范围+-20dB，支持音频和视频文件
#
# This collection includes video processing tools, and of course includes some small audio functions
# 1. Audio extraction to MP3, can choose different bitrates
# 2. Convert MP3 bitrate
# 3. Adjust volume, range +-20dB, supports audio and video files

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import subprocess
import re

def extract_audio_to_mp3(input_file, output_mp3, bitrate, progress_callback):
    """
    从视频或音频文件中提取音频并转换为MP3
    """
    cmd = ['ffmpeg', '-i', input_file, '-b:a', bitrate, '-acodec', 'libmp3lame', output_mp3, '-y']
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='ignore')
    duration = None
    for line in process.stderr:
        if 'Duration:' in line:
            duration_match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', line)
            if duration_match:
                h, m, s = map(float, duration_match.groups())
                duration = h * 3600 + m * 60 + s
        if 'time=' in line and duration:
            time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
            if time_match:
                h, m, s = map(float, time_match.groups())
                current_time = h * 3600 + m * 60 + s
                progress = min((current_time / duration) * 100, 100)
                progress_callback(progress)
    process.wait()
    if process.returncode == 0:
        progress_callback(100)
        messagebox.showinfo("成功", "音频提取成功！")
    else:
        messagebox.showerror("错误", "提取失败")

def adjust_volume(input_file, output_file, db_change, progress_callback):
    """
    调整音频或视频文件的音量
    """
    import math
    volume_multiplier = 10 ** (db_change / 20.0)
    
    # 检查输入文件是否为视频文件
    video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv']
    is_video = any(input_file.lower().endswith(ext) for ext in video_extensions)
    
    if is_video:
        # 对于视频文件，复制视频流并调整音频流
        cmd = ['ffmpeg', '-i', input_file, '-af', f'volume={volume_multiplier}', '-c:v', 'copy', output_file, '-y']
    else:
        # 对于音频文件，直接调整音量
        cmd = ['ffmpeg', '-i', input_file, '-af', f'volume={volume_multiplier}', output_file, '-y']
    
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='ignore')
    duration = None
    for line in process.stderr:
        if 'Duration:' in line:
            duration_match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', line)
            if duration_match:
                h, m, s = map(float, duration_match.groups())
                duration = h * 3600 + m * 60 + s
        if 'time=' in line and duration:
            time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
            if time_match:
                h, m, s = map(float, time_match.groups())
                current_time = h * 3600 + m * 60 + s
                progress = min((current_time / duration) * 100, 100)
                progress_callback(progress)
    process.wait()
    if process.returncode == 0:
        progress_callback(100)
        messagebox.showinfo("成功", "音量调整成功！")
    else:
        messagebox.showerror("错误", "调整失败")

def convert_mp3_bitrate(input_mp3, output_mp3, bitrate, progress_callback):
    """
    转换MP3文件的码率
    """
    cmd = ['ffmpeg', '-i', input_mp3, '-b:a', bitrate, '-acodec', 'libmp3lame', output_mp3, '-y']
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='ignore')
    duration = None
    for line in process.stderr:
        if 'Duration:' in line:
            duration_match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', line)
            if duration_match:
                h, m, s = map(float, duration_match.groups())
                duration = h * 3600 + m * 60 + s
        if 'time=' in line and duration:
            time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
            if time_match:
                h, m, s = map(float, time_match.groups())
                current_time = h * 3600 + m * 60 + s
                progress = min((current_time / duration) * 100, 100)
                progress_callback(progress)
    process.wait()
    if process.returncode == 0:
        progress_callback(100)
        messagebox.showinfo("成功", "码率转换成功！")
    else:
        messagebox.showerror("错误", "转换失败")


class VideoToolsGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VideoTools - 视频音频工具")
        self.root.geometry("600x500")

        # 标签
        self.label = tk.Label(root, text="选择功能", font=("Arial", 16))
        self.label.pack(pady=10)

        # 功能选择
        self.function_var = tk.StringVar(value="extract")
        self.extract_radio = tk.Radiobutton(root, text="音频提取为MP3", variable=self.function_var, value="extract")
        self.extract_radio.pack()
        self.convert_radio = tk.Radiobutton(root, text="转换MP3码率", variable=self.function_var, value="convert")
        self.convert_radio.pack()
        self.adjust_radio = tk.Radiobutton(root, text="调整音量", variable=self.function_var, value="adjust")
        self.adjust_radio.pack()

        # 输入文件
        self.input_label = tk.Label(root, text="输入文件:")
        self.input_label.pack()
        self.input_entry = tk.Entry(root, width=50)
        self.input_entry.pack()
        self.input_button = tk.Button(root, text="浏览", command=self.select_input_file)
        self.input_button.pack()

        # 输出文件
        self.output_label = tk.Label(root, text="输出文件:")
        self.output_label.pack()
        self.output_entry = tk.Entry(root, width=50)
        self.output_entry.pack()
        self.output_button = tk.Button(root, text="浏览", command=self.select_output_file)
        self.output_button.pack()

        # 码率选择
        self.bitrate_label = tk.Label(root, text="选择码率:")
        self.bitrate_label.pack()
        self.bitrate_var = tk.StringVar(value="128k")
        self.bitrate_combo = ttk.Combobox(root, textvariable=self.bitrate_var, values=["64k", "128k", "192k", "256k", "320k"])
        self.bitrate_combo.pack()

        # 音量调整
        self.volume_label = tk.Label(root, text="音量调整 (dB):")
        self.volume_label.pack()
        self.volume_var = tk.DoubleVar(value=0.0)
        self.volume_scale = tk.Scale(root, from_=-20, to=20, orient=tk.HORIZONTAL, resolution=0.1, variable=self.volume_var)
        self.volume_scale.pack()

        # 执行按钮
        self.execute_button = tk.Button(root, text="执行", command=self.execute_function)
        self.execute_button.pack(pady=10)

        # 进度条
        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=10)

    def select_input_file(self):
        function = self.function_var.get()
        if function == "adjust":
            # 调整音量支持视频和音频文件
            filetypes = [("视频/音频文件", "*.mp4 *.avi *.mkv *.mp3 *.wav *.flac *.mov *.wmv")]
        else:
            # 其他功能主要处理音频
            filetypes = [("视频/音频文件", "*.mp4 *.avi *.mkv *.mp3 *.wav *.flac")]
        
        file_path = filedialog.askopenfilename(filetypes=filetypes)
        if file_path:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, file_path)

    def select_output_file(self):
        function = self.function_var.get()
        input_file = self.input_entry.get()
        
        if function == "adjust" and input_file:
            # 根据输入文件类型决定输出类型
            if input_file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv')):
                defaultextension = ".mp4"
                filetypes = [("视频文件", "*.mp4")]
            else:
                defaultextension = ".mp3"
                filetypes = [("音频文件", "*.mp3")]
        else:
            defaultextension = ".mp3"
            filetypes = [("MP3文件", "*.mp3")]
        
        file_path = filedialog.asksaveasfilename(defaultextension=defaultextension, filetypes=filetypes)
        if file_path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, file_path)

    def execute_function(self):
        input_file = self.input_entry.get()
        output_file = self.output_entry.get()
        bitrate = self.bitrate_var.get()
        db_change = self.volume_var.get()

        if not input_file or not output_file:
            messagebox.showerror("错误", "请选择输入和输出文件")
            return

        self.execute_button.config(state="disabled")
        self.progress["value"] = 0

        def update_progress(value):
            self.progress["value"] = value
            self.root.update_idletasks()

        thread = threading.Thread(target=self.run_operation, args=(update_progress, db_change))
        thread.start()

    def run_operation(self, progress_callback, db_change):
        input_file = self.input_entry.get()
        output_file = self.output_entry.get()
        bitrate = self.bitrate_var.get()

        if self.function_var.get() == "extract":
            extract_audio_to_mp3(input_file, output_file, bitrate, progress_callback)
        elif self.function_var.get() == "convert":
            convert_mp3_bitrate(input_file, output_file, bitrate, progress_callback)
        elif self.function_var.get() == "adjust":
            adjust_volume(input_file, output_file, db_change, progress_callback)

        self.execute_button.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoToolsGUI(root)
    root.mainloop()
