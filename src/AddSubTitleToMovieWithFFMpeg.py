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
from tkinter import colorchooser
from tkinter import ttk
import os
import subprocess
import threading
import time
import re
import json

# 全局变量
video_duration = 0.0  # 视频总时长（秒）
processing = False  # 是否正在处理

def select_video():
    global video_duration
    file_path = filedialog.askopenfilename(
        title="选择视频文件",
        filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv"), ("所有文件", "*.*")]
    )
    if file_path:
        entry_video.delete(0, tk.END)
        entry_video.insert(0, file_path)
        # 获取视频时长
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            import json
            data = json.loads(result.stdout)
            duration_str = data['format']['duration']
            video_duration = float(duration_str)
            label_duration.config(text=f"视频时长: {time.strftime('%H:%M:%S', time.gmtime(video_duration))}")
        except Exception as e:
            video_duration = 0.0
            label_duration.config(text="视频时长: 未知")
            print(f"获取视频时长失败: {e}")

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

# ...existing code...

def choose_watermark_color():
    color = colorchooser.askcolor(title="选择水印颜色")
    if color and color[1]:
        watermark_color_var.set(color[1])

def choose_sub1_color():
    color = colorchooser.askcolor(title="选择中文字幕颜色")
    if color and color[1]:
        sub1_color_var.set(color[1])

def choose_sub2_color():
    color = colorchooser.askcolor(title="选择英文字幕颜色")
    if color and color[1]:
        sub2_color_var.set(color[1])

def hex_color_to_ass(color):
    # 转为ASS字幕的&H00BBGGRR&格式（不含透明度）
    color = color.lstrip('#')
    if len(color) != 6:
        color = "FFFFFF"
    r = color[0:2]
    g = color[2:4]
    b = color[4:6]
    return f"&H00{b}{g}{r}&"

def hex_color_to_drawtext(color):
    color = color.lstrip('#')
    if len(color) != 6:
        color = "FFFFFF"
    return f"#{color}"

def merge_videos():
    global processing
    if processing:
        messagebox.showwarning("警告", "正在处理中，请等待完成。")
        return

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

    # 字幕样式参数
    # 中文
    font1 = "Microsoft YaHei"
    fontsize1 = sub1_fontsize_var.get()
    color1 = hex_color_to_ass(sub1_color_var.get())
    show_sub1 = sub1_show_var.get()
    marginv1 = 100
    style1 = (
        f"Fontname={font1},Fontsize={fontsize1},PrimaryColour={color1},"
        f"OutlineColour=&H00000000&,BorderStyle=1,Outline=2,Shadow=0,"
        f"Bold=1,Alignment=2,MarginV={marginv1}"
    )
    # 英文
    font2 = "Microsoft YaHei"
    fontsize2 = sub2_fontsize_var.get()
    color2 = hex_color_to_ass(sub2_color_var.get())
    show_sub2 = sub2_show_var.get()
    marginv2 = 50
    style2 = (
        f"Fontname={font2},Fontsize={fontsize2},PrimaryColour={color2},"
        f"OutlineColour=&H00000000&,BorderStyle=1,Outline=2,Shadow=0,"
        f"Bold=0,Alignment=2,MarginV={marginv2}"
    )

    # 水印参数
    show_watermark = watermark_show_var.get()
    watermark_text = watermark_text_var.get()
    watermark_alpha = watermark_alpha_var.get()  # 0-100
    watermark_color = watermark_color_var.get()  # "#RRGGBB"
    watermark_fontsize = watermark_fontsize_var.get()
    watermark_ff_color = hex_color_to_drawtext(watermark_color)
    alpha_value = round((100 - watermark_alpha) / 100, 2)  # 0=不透明, 1=全透明

    vf_filters = []
    if show_sub2:
        vf_filters.append(
            f"subtitles=filename='{sub2_path_ff}':force_style='{style2}'"
        )
    if show_sub1:
        vf_filters.append(
            f"subtitles=filename='{sub1_path_ff}':force_style='{style1}'"
        )
    if show_watermark:
        watermark_filter = (
            f"drawtext=text='{watermark_text}':"
            f"fontcolor={watermark_ff_color}:"
            f"alpha={alpha_value}:"
            f"fontsize={watermark_fontsize}:font='Microsoft YaHei':"
            f"x=w-tw-30:y=30:borderw=2:bordercolor=black"
        )
        vf_filters.append(watermark_filter)

    vf = ",".join(vf_filters)

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

    # 启动处理线程
    processing = True
    btn_merge.config(state=tk.DISABLED)
    progress_bar['value'] = 0
    label_elapsed.config(text="已用时间: 00:00:00")
    label_remaining.config(text="剩余时间: 未知")

    thread = threading.Thread(target=run_ffmpeg, args=(cmd, output_path))
    thread.start()

def run_ffmpeg(cmd, output_path):
    global processing, video_duration
    start_time = time.time()
    try:
        process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        duration_pattern = re.compile(r'Duration: (\d+):(\d+):(\d+\.\d+)')
        time_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')

        total_duration = video_duration if video_duration > 0 else None

        while True:
            line = process.stderr.readline()
            if not line:
                break
            line = line.strip()

            # 解析总时长（如果还没获取）
            if total_duration is None:
                match = duration_pattern.search(line)
                if match:
                    h, m, s = map(float, match.groups())
                    total_duration = h * 3600 + m * 60 + s

            # 解析当前时间
            match = time_pattern.search(line)
            if match:
                h, m, s = map(float, match.groups())
                current_time = h * 3600 + m * 60 + s

                if total_duration and total_duration > 0:
                    progress = (current_time / total_duration) * 100
                    elapsed = time.time() - start_time
                    remaining = (elapsed / current_time) * (total_duration - current_time) if current_time > 0 else 0

                    # 更新GUI
                    root.after(0, update_progress, progress, elapsed, remaining)

        process.wait()
        if process.returncode == 0:
            root.after(0, lambda: messagebox.showinfo("成功", f"视频合成成功！已保存为: {output_path}"))
        else:
            root.after(0, lambda: messagebox.showerror("FFmpeg错误", "FFmpeg 执行失败，详细错误已输出到终端窗口。"))
    except Exception as e:
        root.after(0, lambda: messagebox.showerror("错误", f"发生错误: {str(e)}\n请确保已安装 FFmpeg 并将其添加到系统 PATH 中。"))
    finally:
        processing = False
        root.after(0, lambda: btn_merge.config(state=tk.NORMAL))

def update_progress(progress, elapsed, remaining):
    progress_bar['value'] = progress
    label_elapsed.config(text=f"已用时间: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")
    if remaining > 0:
        label_remaining.config(text=f"剩余时间: {time.strftime('%H:%M:%S', time.gmtime(remaining))}")
    else:
        label_remaining.config(text="剩余时间: 计算中...")

root = tk.Tk()
root.title("双语字幕烧录工具（FFmpeg）")
root.geometry("800x520")

# 新增：水印参数变量（必须在root创建后）
watermark_text_var = tk.StringVar(value="字幕制作By老猿")
watermark_alpha_var = tk.DoubleVar(value=60.0)
watermark_color_var = tk.StringVar(value="#FFFFFF")
watermark_fontsize_var = tk.IntVar(value=24)
watermark_show_var = tk.BooleanVar(value=True)

# 字幕参数变量
sub1_fontsize_var = tk.IntVar(value=24)
sub1_color_var = tk.StringVar(value="#FFFF00")
sub1_show_var = tk.BooleanVar(value=True)
sub2_fontsize_var = tk.IntVar(value=24)
sub2_color_var = tk.StringVar(value="#FFFFFF")
sub2_show_var = tk.BooleanVar(value=True)

# 视频文件
tk.Label(root, text="视频文件:").grid(row=0, column=0, padx=10, pady=15, sticky="e")
entry_video = tk.Entry(root, width=55)
entry_video.grid(row=0, column=1, padx=5)
tk.Button(root, text="浏览", command=select_video).grid(row=0, column=2, padx=10)

# 字幕1（底部，中文，在英文字幕之上）
frame_sub1 = tk.LabelFrame(root, text="中文字幕（底部，之上）", padx=5, pady=5)
frame_sub1.grid(row=1, column=0, columnspan=3, padx=10, pady=5, sticky="we")
entry_sub1 = tk.Entry(frame_sub1, width=45)
entry_sub1.grid(row=0, column=0, padx=5)
tk.Button(frame_sub1, text="浏览", command=select_subtitle1).grid(row=0, column=1, padx=5)
tk.Label(frame_sub1, text="字号:").grid(row=0, column=2, padx=2)
tk.Spinbox(frame_sub1, from_=10, to=60, width=4, textvariable=sub1_fontsize_var).grid(row=0, column=3, padx=2)
tk.Label(frame_sub1, text="颜色:").grid(row=0, column=4, padx=2)
tk.Entry(frame_sub1, width=8, textvariable=sub1_color_var).grid(row=0, column=5, padx=2)
tk.Button(frame_sub1, text="选择", command=choose_sub1_color).grid(row=0, column=6, padx=2)
tk.Checkbutton(frame_sub1, text="显示", variable=sub1_show_var).grid(row=0, column=7, padx=5)

# 字幕2（底部，英文，最下方）
frame_sub2 = tk.LabelFrame(root, text="英文字幕（底部，最下方）", padx=5, pady=5)
frame_sub2.grid(row=2, column=0, columnspan=3, padx=10, pady=5, sticky="we")
entry_sub2 = tk.Entry(frame_sub2, width=45)
entry_sub2.grid(row=0, column=0, padx=5)
tk.Button(frame_sub2, text="浏览", command=select_subtitle2).grid(row=0, column=1, padx=5)
tk.Label(frame_sub2, text="字号:").grid(row=0, column=2, padx=2)
tk.Spinbox(frame_sub2, from_=10, to=60, width=4, textvariable=sub2_fontsize_var).grid(row=0, column=3, padx=2)
tk.Label(frame_sub2, text="颜色:").grid(row=0, column=4, padx=2)
tk.Entry(frame_sub2, width=8, textvariable=sub2_color_var).grid(row=0, column=5, padx=2)
tk.Button(frame_sub2, text="选择", command=choose_sub2_color).grid(row=0, column=6, padx=2)
tk.Checkbutton(frame_sub2, text="显示", variable=sub2_show_var).grid(row=0, column=7, padx=5)

# 水印设置区域
frame_watermark = tk.LabelFrame(root, text="水印设置（右上角）", padx=10, pady=5)
frame_watermark.grid(row=3, column=0, columnspan=3, padx=15, pady=5, sticky="we")

tk.Label(frame_watermark, text="水印文字:").grid(row=0, column=0, sticky="e")
entry_watermark = tk.Entry(frame_watermark, textvariable=watermark_text_var, width=25)
entry_watermark.grid(row=0, column=1, padx=5)

tk.Label(frame_watermark, text="字号:").grid(row=0, column=2, sticky="e")
tk.Spinbox(frame_watermark, from_=10, to=60, width=4, textvariable=watermark_fontsize_var).grid(row=0, column=3, padx=2)

tk.Label(frame_watermark, text="透明度(%):").grid(row=0, column=4, sticky="e")
scale_alpha = tk.Scale(frame_watermark, from_=0, to=100, orient=tk.HORIZONTAL, variable=watermark_alpha_var, length=100)
scale_alpha.grid(row=0, column=5, padx=5)

tk.Label(frame_watermark, text="颜色:").grid(row=0, column=6, sticky="e")
entry_color = tk.Entry(frame_watermark, textvariable=watermark_color_var, width=10)
entry_color.grid(row=0, column=7, padx=5)
btn_color = tk.Button(frame_watermark, text="选择", command=choose_watermark_color)
btn_color.grid(row=0, column=8, padx=5)

tk.Checkbutton(frame_watermark, text="显示", variable=watermark_show_var).grid(row=0, column=9, padx=10)

# 进度条和时间显示
frame_progress = tk.Frame(root)
frame_progress.grid(row=4, column=0, columnspan=3, pady=10)

progress_bar = ttk.Progressbar(frame_progress, orient=tk.HORIZONTAL, length=400, mode='determinate')
progress_bar.pack(pady=5)

label_duration = tk.Label(frame_progress, text="视频时长: 未知")
label_duration.pack()

label_elapsed = tk.Label(frame_progress, text="已用时间: 00:00:00")
label_elapsed.pack()

label_remaining = tk.Label(frame_progress, text="剩余时间: 未知")
label_remaining.pack()

# 合成按钮
btn_merge = tk.Button(root, text="开始烧录双语字幕", width=25, command=merge_videos)
btn_merge.grid(row=5, column=1, pady=25)

root.mainloop()