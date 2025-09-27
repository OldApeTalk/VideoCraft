import tkinter as tk
from tkinter import filedialog, messagebox
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.tools.subtitles import SubtitlesClip
import os
import re  # 用于解析 SRT

# 自定义函数：用 UTF-8 读取并解析 SRT 文件成列表
def parse_srt(filename):
    subtitles = []
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        blocks = re.split(r'\n\s*\n', content)  # 分割每个字幕块
        for block in blocks:
            lines = block.splitlines()
            if len(lines) >= 3:
                # 跳过序号行
                times = lines[1].split(' --> ')
                start = time_to_seconds(times[0])
                end = time_to_seconds(times[1])
                text = ' '.join(lines[2:])  # 合并多行文本
                subtitles.append(((start, end), text))
    return subtitles

# 辅助函数：将 SRT 时间格式转为秒
def time_to_seconds(time_str):
    h, m, s_ms = time_str.split(':')
    s, ms = s_ms.split(',')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

def select_video():
    video_path = filedialog.askopenfilename(title="Select Video File", filetypes=[("Video Files", "*.mp4 *.avi *.mov")])
    if video_path:
        video_entry.delete(0, tk.END)
        video_entry.insert(0, video_path)

def select_subtitle1():
    sub1_path = filedialog.askopenfilename(title="Select Subtitle 1 (SRT)", filetypes=[("SRT Files", "*.srt")])
    if sub1_path:
        sub1_entry.delete(0, tk.END)
        sub1_entry.insert(0, sub1_path)

def select_subtitle2():
    sub2_path = filedialog.askopenfilename(title="Select Subtitle 2 (SRT)", filetypes=[("SRT Files", "*.srt")])
    if sub2_path:
        sub2_entry.delete(0, tk.END)
        sub2_entry.insert(0, sub2_path)

def merge_videos():
    video_path = video_entry.get()
    sub1_path = sub1_entry.get()
    sub2_path = sub2_entry.get()
    
    if not video_path or not sub1_path or not sub2_path:
        messagebox.showerror("Error", "Please select all files: video, subtitle 1, and subtitle 2.")
        return
    
    try:
        # Load the video
        video = VideoFileClip(video_path)
        
        # Function to generate text clips for subtitles (使用命名参数避免冲突)
        def generator1(txt):
            clip = TextClip(
                text=txt,  # text 作为命名参数
                font='C:/Windows/Fonts/msyh.ttc',  # Windows 中文字体，支持中文
                font_size=24,  # 如果报 unexpected 'font_size'，改成 fontsize=24 (旧版 MoviePy)
                color='white',
                bg_color='black',
                text_align='center',  # 如果报 unexpected 'text_align'，改成 align='center' (旧版)
                method='caption',
                size=(video.w, None)
            )
            return clip.with_position(('center', 50)).with_opacity(0.7)  # 使用 50 像素顶部边距
        
        def generator2(txt):
            clip = TextClip(
                text=txt,  # text 作为命名参数
                font='C:/Windows/Fonts/msyh.ttc',  # Windows 中文字体，支持中文
                font_size=24,  # 如果报 unexpected 'font_size'，改成 fontsize=24 (旧版 MoviePy)
                color='yellow',
                bg_color='black',
                text_align='center',  # 如果报 unexpected 'text_align'，改成 align='center' (旧版)
                method='caption',
                size=(video.w, None)
            )
            return clip.with_position(('center', video.h - 50 - clip.h)).with_opacity(0.7)  # 动态计算底部位置
        
        # Parse subtitles manually with UTF-8
        subs1 = parse_srt(sub1_path)
        subs2 = parse_srt(sub2_path)
        
        # Create subtitles clips with parsed lists
        subtitles1 = SubtitlesClip(subs1, make_textclip=generator1)
        subtitles2 = SubtitlesClip(subs2, make_textclip=generator2)
        
        # Composite the video with both subtitles
        final_video = CompositeVideoClip([video, subtitles1.with_duration(video.duration), subtitles2.with_duration(video.duration)])
        
        # Output file path
        output_path = os.path.splitext(video_path)[0] + "_merged.mp4"
        final_video.write_videofile(output_path, codec='libx264', audio_codec='aac')
        
        messagebox.showinfo("Success", f"Video merged successfully! Saved as: {output_path}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {str(e)}")

# Create GUI window
root = tk.Tk()
root.title("Video Subtitle Merger")
root.geometry("500x250")

# Video selection
tk.Label(root, text="Video File:").grid(row=0, column=0, padx=10, pady=10)
video_entry = tk.Entry(root, width=40)
video_entry.grid(row=0, column=1, padx=10)
tk.Button(root, text="Browse", command=select_video).grid(row=0, column=2, padx=10)

# Subtitle 1 selection
tk.Label(root, text="Subtitle 1 (Top):").grid(row=1, column=0, padx=10, pady=10)
sub1_entry = tk.Entry(root, width=40)
sub1_entry.grid(row=1, column=1, padx=10)
tk.Button(root, text="Browse", command=select_subtitle1).grid(row=1, column=2, padx=10)

# Subtitle 2 selection
tk.Label(root, text="Subtitle 2 (Bottom):").grid(row=2, column=0, padx=10, pady=10)
sub2_entry = tk.Entry(root, width=40)
sub2_entry.grid(row=2, column=1, padx=10)
tk.Button(root, text="Browse", command=select_subtitle2).grid(row=2, column=2, padx=10)

# Merge button
tk.Button(root, text="Merge Video with Subtitles", command=merge_videos).grid(row=3, column=1, pady=20)

root.mainloop()