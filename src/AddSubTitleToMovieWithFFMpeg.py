import tkinter as tk
from tkinter import filedialog, messagebox
import os
import subprocess

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
        # 定义 VF 滤镜字符串：添加两个字幕，应用样式
        vf = (
            f"subtitles='{sub1_path}':force_style='Fontname=Microsoft YaHei,Fontsize=24,PrimaryColour=&H4DFFFFFF&,OutlineColour=&H4D000000&,BorderStyle=3,Alignment=10,MarginV=50,Outline=0,Shadow=0',"
            f"subtitles='{sub2_path}':force_style='Fontname=Microsoft YaHei,Fontsize=24,PrimaryColour=&H4D00FFFF&,OutlineColour=&H4D000000&,BorderStyle=3,Alignment=2,MarginV=50,Outline=0,Shadow=0'"
        )
        
        # 输出文件路径
        output_path = os.path.splitext(video_path)[0] + "_merged.mp4"
        
        # FFmpeg 命令
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vf', vf,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            output_path
        ]
        
        # 执行命令
        subprocess.run(cmd, check=True)
        
        messagebox.showinfo("Success", f"Video merged successfully! Saved as: {output_path}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {str(e)}\nEnsure FFmpeg is installed and in your PATH.")

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