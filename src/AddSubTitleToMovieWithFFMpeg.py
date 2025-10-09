"""
设计说明：
本程序用于将中英文两个 SRT 字幕文件以烧录（硬字幕）方式叠加到视频文件下方，中文字幕在英文字幕之上，适用于中英双语字幕排版需求。
主要功能与设计要点如下：

1. 支持选择视频文件（如 MP4、AVI、MOV）和两个 SRT 字幕文件（一般为中英文）。
2. 字幕排版：
   - 两个字幕都显示在画面底部，中文字幕（Subtitle 1）在英文字幕（Subtitle 2）之上。
   - 字幕样式可通过 FFmpeg 的 force_style 参数自定义，包括字体、字号、颜色、边框、阴影、对齐方式等。
3. 自动输出合成后的视频文件，文件名为“原视频名_merged.mp4”。
4. 具备一定的自提能力（如自动推断输出路径、自动检查 FFmpeg 是否可用）。
5. 使用 FFmpeg 命令行工具进行字幕烧录，确保兼容性和效率。
6. 提供简单易用的图形界面，便于用户操作。

注意事项：
- 需要本地已安装 FFmpeg，并确保其已加入系统 PATH。
- 字幕文件建议为 UTF-8 编码的标准 SRT 文件。
- 如需自定义字幕样式，可在代码中调整 force_style 参数。

"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import subprocess

# ========== UI界面部分 ==========

def select_video():
    file_path = filedialog.askopenfilename(
        title="选择视频文件",
        filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv"), ("所有文件", "*.*")]
    )
    if file_path:
        entry_video.delete(0, tk.END)
        entry_video.insert(0, file_path)

def select_subtitle1():
    file_path = filedialog.askopenfilename(
        title="选择中文字幕文件（底部，位于英文字幕之上）",
        filetypes=[("SRT 字幕文件", "*.srt"), ("所有文件", "*.*")]
    )
    if file_path:
        entry_sub1.delete(0, tk.END)
        entry_sub1.insert(0, file_path)

def select_subtitle2():
    file_path = filedialog.askopenfilename(
        title="选择英文字幕文件（底部，最下方）",
        filetypes=[("SRT 字幕文件", "*.srt"), ("所有文件", "*.*")]
    )
    if file_path:
        entry_sub2.delete(0, tk.END)
        entry_sub2.insert(0, file_path)

def escape_ffmpeg_path(path):
    # 转为绝对路径，反斜杠转正斜杠，冒号转义
    abs_path = os.path.abspath(path)
    abs_path = abs_path.replace("\\", "/")
    abs_path = abs_path.replace(":", "\\:")
    return abs_path

def merge_videos():
    video_path = entry_video.get()
    sub1_path = entry_sub1.get()
    sub2_path = entry_sub2.get()

    if not video_path or not sub1_path or not sub2_path:
        messagebox.showerror("错误", "请确保选择了所有文件：视频、中文字幕（底部，之上）和英文字幕（底部，最下方）。")
        return

    if not os.path.exists(video_path):
        messagebox.showerror("错误", f"视频文件不存在: {video_path}")
        return
    if not os.path.exists(sub1_path):
        messagebox.showerror("错误", f"中文字幕文件不存在: {sub1_path}")
        return
    if not os.path.exists(sub2_path):
        messagebox.showerror("错误", f"英文字幕文件不存在: {sub2_path}")
        return

    # 路径处理
    video_path_abs = os.path.abspath(video_path)
    sub1_path_ff = escape_ffmpeg_path(sub1_path)
    sub2_path_ff = escape_ffmpeg_path(sub2_path)
    output_path = os.path.splitext(video_path_abs)[0] + "_merged.mp4"

    # 字幕样式
    # 中文：黄色、加粗、描黑边
    font1 = "Microsoft YaHei"
    fontsize1 = 24
    marginv1 = 100
    style1 = (
        f"Fontname={font1},Fontsize={fontsize1},PrimaryColour=&H00FFFF00&,"
        f"OutlineColour=&H00000000&,BorderStyle=1,Outline=2,Shadow=0,"
        f"Bold=1,Alignment=2,MarginV={marginv1}"
    )
    # 英文：白色、描黑边
    font2 = "Microsoft YaHei"
    fontsize2 = 24
    marginv2 = 50
    style2 = (
        f"Fontname={font2},Fontsize={fontsize2},PrimaryColour=&H00FFFFFF&,"
        f"OutlineColour=&H00000000&,BorderStyle=1,Outline=2,Shadow=0,"
        f"Bold=0,Alignment=2,MarginV={marginv2}"
    )

    vf = (
        f"subtitles=filename='{sub2_path_ff}':force_style='{style2}',"
        f"subtitles=filename='{sub1_path_ff}':force_style='{style1}'"
    )

    cmd = [
        'ffmpeg',
        '-y',
        '-i', video_path_abs,
        '-vf', vf,
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-movflags', '+faststart',
        output_path
    ]

    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if completed.returncode == 0:
            messagebox.showinfo("成功", f"视频合成成功！已保存为: {output_path}")
        else:
            messagebox.showerror("FFmpeg错误", f"FFmpeg 执行失败：\n{completed.stderr}")
    except Exception as e:
        messagebox.showerror("错误", f"发生错误: {str(e)}\n请确保已安装 FFmpeg 并将其添加到系统 PATH 中。")

root = tk.Tk()
root.title("双语字幕烧录工具（FFmpeg）")
root.geometry("700x420")  # 调整窗口为更大尺寸，宽700高420

# 视频文件
tk.Label(root, text="视频文件:").grid(row=0, column=0, padx=10, pady=15, sticky="e")
entry_video = tk.Entry(root, width=55)
entry_video.grid(row=0, column=1, padx=5)
tk.Button(root, text="浏览", command=select_video).grid(row=0, column=2, padx=10)

# 字幕1（底部，中文，在英文字幕之上）
tk.Label(root, text="中文字幕（底部，之上）:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
entry_sub1 = tk.Entry(root, width=55)
entry_sub1.grid(row=1, column=1, padx=5)
tk.Button(root, text="浏览", command=select_subtitle1).grid(row=1, column=2, padx=10)

# 字幕2（底部，英文，最下方）
tk.Label(root, text="英文字幕（底部，最下方）:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
entry_sub2 = tk.Entry(root, width=55)
entry_sub2.grid(row=2, column=1, padx=5)
tk.Button(root, text="浏览", command=select_subtitle2).grid(row=2, column=2, padx=10)

# 合成按钮
btn_merge = tk.Button(root, text="开始烧录双语字幕", width=25, command=merge_videos)
btn_merge.grid(row=3, column=1, pady=25)

root.mainloop()