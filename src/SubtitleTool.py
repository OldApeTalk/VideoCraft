"""
合并字幕分割和添加功能的工具
将 SplitSubtitles.py 的字符宽度剪裁功能合并到 AddSubTitleToMovieWithFFMpeg.py 中，
提供统一的界面来处理字幕分割和视频字幕烧录。
"""

import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser, ttk
import os
import subprocess
import threading
import time
import re
import json
import srt
from datetime import timedelta

# 全局变量
video_duration = 0.0  # 视频总时长（秒）
processing = False  # 是否正在处理
encode_preset = "veryfast"  # 编码速度预设

def split_subtitle(sub, max_chars, is_chinese=False):
    """
    Split a subtitle into multiple if it exceeds max_chars.
    For English: split on sentences or commas, and avoid splitting words by finding last space/punctuation.
    For Chinese: split on punctuation or fixed length.
    Distribute time proportionally.
    """
    content = sub.content.strip()
    if len(content) <= max_chars:
        return [sub]
    
    new_subs = []
    start = sub.start
    end = sub.end
    total_duration = (end - start).total_seconds()
    
    # Simple semantic split: find natural breaks
    if is_chinese:
        # For Chinese, split on common punctuation
        breaks = [m.start() for m in re.finditer(r'[，。？！；]', content)] + [len(content)]
    else:
        # For English, split on sentence ends or commas
        breaks = [m.start() for m in re.finditer(r'[.?!,]', content)] + [len(content)]
    
    current_pos = 0
    while current_pos < len(content):
        # Aim for max_chars, but find the best split point <= max_chars
        split_pos = current_pos + max_chars
        if split_pos >= len(content):
            split_pos = len(content)
        else:
            # Find candidates from breaks within range
            candidates = [b + 1 for b in breaks if current_pos < b + 1 <= split_pos]
            if candidates:
                split_pos = max(candidates)
            else:
                # No punctuation break: find last space to avoid word split (for English)
                if not is_chinese:
                    last_space = content.rfind(' ', current_pos, split_pos)
                    if last_space > current_pos:
                        split_pos = last_space + 1  # Include the space or cut before it? Better to cut after space for clean trim.
                    # If no space, hard split (rare for English)
                # For Chinese, hard split is fine
        
        part_content = content[current_pos:split_pos].strip()
        if not part_content:
            break
        
        # Calculate time for this part
        part_duration = (len(part_content) / len(content)) * total_duration
        part_end = start + timedelta(seconds=part_duration)
        
        new_sub = srt.Subtitle(
            index=len(new_subs) + 1,  # Temporary index
            start=start,
            end=part_end,
            content=part_content
        )
        new_subs.append(new_sub)
        
        start = part_end
        current_pos = split_pos
    
    # Adjust total end to original end
    if new_subs:
        new_subs[-1].end = end
    
    return new_subs

def process_srt_split(input_path, max_chars, is_chinese=False):
    """
    Process SRT file to split subtitles, return the list of subtitles.
    """
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            subs = list(srt.parse(f))
        
        new_subs = []
        for sub in subs:
            new_subs.extend(split_subtitle(sub, max_chars, is_chinese))
        
        # Re-index
        for i, sub in enumerate(new_subs, 1):
            sub.index = i
        
        return new_subs
    except Exception as e:
        raise e

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
            # 首先检查ffprobe是否可用
            try:
                subprocess.run(['ffprobe', '-version'], capture_output=True, check=True, timeout=5)
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                messagebox.showerror("错误", "未找到ffprobe。请确保已安装FFmpeg并将其添加到系统PATH中。\n\n下载地址：https://ffmpeg.org/download.html")
                video_duration = 0.0
                label_duration.config(text="视频时长: 未知 (未安装FFmpeg)")
                return
            
            # 使用更简单的命令获取时长
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                # 尝试备用方法
                cmd2 = ['ffprobe', '-i', file_path, '-v', 'quiet', '-print_format', 'json', '-show_format']
                result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=10)
                if result2.returncode == 0:
                    data = json.loads(result2.stdout)
                    duration_str = data['format']['duration']
                else:
                    raise Exception(f"ffprobe命令失败: {result.stderr.strip()}")
            else:
                duration_str = result.stdout.strip()
            
            video_duration = float(duration_str)
            label_duration.config(text=f"视频时长: {time.strftime('%H:%M:%S', time.gmtime(video_duration))}")
            
        except subprocess.TimeoutExpired:
            video_duration = 0.0
            label_duration.config(text="视频时长: 未知 (超时)")
            messagebox.showwarning("警告", "获取视频时长超时。视频文件可能损坏或过大。")
        except ValueError as e:
            video_duration = 0.0
            label_duration.config(text="视频时长: 未知 (无效时长)")
            print(f"时长转换错误: {e}, 原始输出: {duration_str}")
        except json.JSONDecodeError as e:
            video_duration = 0.0
            label_duration.config(text="视频时长: 未知 (JSON解析错误)")
            print(f"JSON解析错误: {e}")
        except Exception as e:
            video_duration = 0.0
            label_duration.config(text="视频时长: 未知")
            error_msg = str(e)
            print(f"获取视频时长失败: {error_msg}")
            
            # 提供更详细的错误信息
            if "No such file or directory" in error_msg:
                messagebox.showwarning("警告", "视频文件路径无效或文件不存在。")
            elif "Permission denied" in error_msg:
                messagebox.showwarning("警告", "没有权限访问视频文件。")
            elif "Invalid data found" in error_msg:
                messagebox.showwarning("警告", "视频文件格式无效或损坏。")
            else:
                messagebox.showwarning("警告", f"获取视频时长失败: {error_msg}\n\n您可以继续使用，但进度条可能不准确。")

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

def get_video_resolution(video_path):
    """获取视频分辨率"""
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
               '-show_entries', 'stream=width,height', '-of', 'csv=p=0', video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            width, height = map(int, result.stdout.strip().split(','))
            return width, height
    except:
        pass
    return None, None

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

    # 处理字幕分割
    split_sub1 = split_sub1_var.get()
    split_sub2 = split_sub2_var.get()
    temp_sub1_path = sub1_path
    temp_sub2_path = sub2_path

    try:
        if split_sub1:
            max_chars1 = sub1_max_chars_var.get()
            is_chinese1 = sub1_is_chinese_var.get()
            subs1 = process_srt_split(sub1_path, max_chars1, is_chinese1)
            temp_sub1_path = sub1_path.replace('.srt', '_split.srt')
            with open(temp_sub1_path, 'w', encoding='utf-8') as f:
                f.write(srt.compose(subs1))

        if split_sub2:
            max_chars2 = sub2_max_chars_var.get()
            is_chinese2 = sub2_is_chinese_var.get()
            subs2 = process_srt_split(sub2_path, max_chars2, is_chinese2)
            temp_sub2_path = sub2_path.replace('.srt', '_split.srt')
            with open(temp_sub2_path, 'w', encoding='utf-8') as f:
                f.write(srt.compose(subs2))
    except Exception as e:
        messagebox.showerror("字幕分割错误", str(e))
        return

    # 路径处理
    video_path_abs = os.path.abspath(video_path)
    sub1_path_ff = escape_ffmpeg_path(temp_sub1_path)
    sub2_path_ff = escape_ffmpeg_path(temp_sub2_path)
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
    alpha_value = round(watermark_alpha / 100, 2)  # 0=不透明, 1=全透明

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
            f"fontcolor={watermark_ff_color}@{alpha_value}:"
            f"fontsize={watermark_fontsize}:font='Microsoft YaHei':"
            f"x=w-tw-30:y=30:borderw=2:bordercolor=black"
        )
        vf_filters.append(watermark_filter)

    vf = ",".join(vf_filters)

    # 获取视频分辨率以设置合适的缓冲区大小
    width, height = get_video_resolution(video_path_abs)
    
    # 根据分辨率设置缓冲区大小和最大码率
    if width and height:
        pixels = width * height
        if pixels >= 3840 * 2160:  # 4K或更高
            bufsize = '150M'
            maxrate = '150M'
        elif pixels >= 2560 * 1440:  # 2K
            bufsize = '80M'
            maxrate = '80M'
        elif pixels >= 1920 * 1080:  # 1080p
            bufsize = '50M'
            maxrate = '50M'
        else:  # 720p或更低
            bufsize = '30M'
            maxrate = '30M'
    else:
        # 无法获取分辨率时使用保守的大值
        bufsize = '100M'
        maxrate = '100M'
    
    # 获取编码预设
    preset = encode_preset_var.get()
    
    # 根据preset设置CRF值（更快的preset使用略高的CRF以保持合理文件大小）
    crf_map = {
        'ultrafast': '28',
        'superfast': '26',
        'veryfast': '25',
        'faster': '24',
        'fast': '23',
        'medium': '23'
    }
    crf = crf_map.get(preset, '25')
    
    cmd = [
        'ffmpeg',
        '-y',
        '-i', video_path_abs,
        '-vf', vf,
        '-c:v', 'libx264',
        '-preset', preset,           # 编码速度预设
        '-crf', crf,                 # 质量控制
        '-threads', '0',             # 使用所有CPU线程
        '-bufsize', bufsize,         # 根据分辨率动态设置的大缓冲区
        '-maxrate', maxrate,         # 根据分辨率动态设置的最大码率
        '-pix_fmt', 'yuv420p',       # 兼容性像素格式
        '-c:a', 'aac',
        '-b:a', '192k',              # 音频码率
        '-movflags', '+faststart',
        output_path
    ]

    # 启动处理线程
    processing = True
    btn_merge.config(state=tk.DISABLED)
    progress_bar['value'] = 0
    label_elapsed.config(text="已用时间: 00:00:00")
    label_remaining.config(text="剩余时间: 未知")

    thread = threading.Thread(target=run_ffmpeg, args=(cmd, output_path, temp_sub1_path, temp_sub2_path, sub1_path, sub2_path))
    thread.start()

def run_ffmpeg(cmd, output_path, temp_sub1, temp_sub2, orig_sub1, orig_sub2):
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
            # 清理临时文件
            if temp_sub1 != orig_sub1 and os.path.exists(temp_sub1):
                os.remove(temp_sub1)
            if temp_sub2 != orig_sub2 and os.path.exists(temp_sub2):
                os.remove(temp_sub2)
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

# GUI Setup
root = tk.Tk()
root.title("双语字幕工具（分割与烧录）")
root.geometry("900x650")

# 新增：水印参数变量
watermark_text_var = tk.StringVar(value="字幕制作By老猿")
watermark_alpha_var = tk.DoubleVar(value=60.0)
watermark_color_var = tk.StringVar(value="#00ffff")
watermark_fontsize_var = tk.IntVar(value=24)
watermark_show_var = tk.BooleanVar(value=True)

# 字幕参数变量
sub1_fontsize_var = tk.IntVar(value=24)
sub1_color_var = tk.StringVar(value="#FFFF00")
sub1_show_var = tk.BooleanVar(value=True)
sub2_fontsize_var = tk.IntVar(value=24)
sub2_color_var = tk.StringVar(value="#FFFFFF")
sub2_show_var = tk.BooleanVar(value=True)

# 分割参数变量
split_sub1_var = tk.BooleanVar(value=True)
sub1_max_chars_var = tk.IntVar(value=20)
sub1_is_chinese_var = tk.BooleanVar(value=True)
split_sub2_var = tk.BooleanVar(value=True)
sub2_max_chars_var = tk.IntVar(value=50)
sub2_is_chinese_var = tk.BooleanVar(value=False)

# 屏幕方向变量
orientation_var = tk.StringVar(value="horizontal")

# 编码速度预设变量
encode_preset_var = tk.StringVar(value="veryfast")

def update_split_settings():
    if orientation_var.get() == "horizontal":
        sub1_max_chars_var.set(20)
        sub2_max_chars_var.set(50)
        sub1_fontsize_var.set(24)
        sub2_fontsize_var.set(24)
    else:
        sub1_max_chars_var.set(10)
        sub2_max_chars_var.set(25)
        sub1_fontsize_var.set(14)
        sub2_fontsize_var.set(12)

# 视频文件
tk.Label(root, text="视频文件:").grid(row=0, column=0, padx=10, pady=15, sticky="e")
entry_video = tk.Entry(root, width=55)
entry_video.grid(row=0, column=1, padx=5)
tk.Button(root, text="浏览", command=select_video).grid(row=0, column=2, padx=10)

# 屏幕方向设置
frame_orientation = tk.LabelFrame(root, text="屏幕方向", padx=10, pady=5)
frame_orientation.grid(row=1, column=0, columnspan=3, padx=15, pady=5, sticky="we")

tk.Radiobutton(frame_orientation, text="横屏", variable=orientation_var, value="horizontal", command=update_split_settings).grid(row=0, column=0, padx=20)
tk.Radiobutton(frame_orientation, text="竖屏", variable=orientation_var, value="vertical", command=update_split_settings).grid(row=0, column=1, padx=20)

# 编码速度设置（放在屏幕方向设置的右侧）
tk.Label(frame_orientation, text="  |  编码速度:").grid(row=0, column=2, padx=(40, 5), sticky="e")
encode_preset_combo = ttk.Combobox(frame_orientation, textvariable=encode_preset_var, 
                                   values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"],
                                   width=12, state="readonly")
encode_preset_combo.grid(row=0, column=3, padx=5)

# 添加提示标签
tk.Label(frame_orientation, text="(高分辨率建议: veryfast或更快)", 
         font=("Arial", 8), fg="gray").grid(row=0, column=4, padx=5)

# 字幕1（底部，中文，在英文字幕之上）
frame_sub1 = tk.LabelFrame(root, text="中文字幕（底部，之上）", padx=5, pady=5)
frame_sub1.grid(row=2, column=0, columnspan=3, padx=10, pady=5, sticky="we")
entry_sub1 = tk.Entry(frame_sub1, width=35)
entry_sub1.grid(row=0, column=0, padx=5)
tk.Button(frame_sub1, text="浏览", command=select_subtitle1).grid(row=0, column=1, padx=5)
tk.Label(frame_sub1, text="字号:").grid(row=0, column=2, padx=2)
tk.Spinbox(frame_sub1, from_=10, to=60, width=4, textvariable=sub1_fontsize_var).grid(row=0, column=3, padx=2)
tk.Label(frame_sub1, text="颜色:").grid(row=0, column=4, padx=2)
tk.Entry(frame_sub1, width=8, textvariable=sub1_color_var).grid(row=0, column=5, padx=2)
tk.Button(frame_sub1, text="选择", command=choose_sub1_color).grid(row=0, column=6, padx=2)
tk.Checkbutton(frame_sub1, text="显示", variable=sub1_show_var).grid(row=0, column=7, padx=5)

# 分割选项 for sub1
tk.Checkbutton(frame_sub1, text="分割字幕", variable=split_sub1_var).grid(row=1, column=0, padx=5, pady=5, sticky="w")
tk.Label(frame_sub1, text="最大字符:").grid(row=1, column=1, padx=2)
tk.Spinbox(frame_sub1, from_=10, to=100, width=4, textvariable=sub1_max_chars_var).grid(row=1, column=2, padx=2)
tk.Checkbutton(frame_sub1, text="中文", variable=sub1_is_chinese_var).grid(row=1, column=3, padx=5)

# 字幕2（底部，英文，最下方）
frame_sub2 = tk.LabelFrame(root, text="英文字幕（底部，最下方）", padx=5, pady=5)
frame_sub2.grid(row=3, column=0, columnspan=3, padx=10, pady=5, sticky="we")
entry_sub2 = tk.Entry(frame_sub2, width=35)
entry_sub2.grid(row=0, column=0, padx=5)
tk.Button(frame_sub2, text="浏览", command=select_subtitle2).grid(row=0, column=1, padx=5)
tk.Label(frame_sub2, text="字号:").grid(row=0, column=2, padx=2)
tk.Spinbox(frame_sub2, from_=10, to=60, width=4, textvariable=sub2_fontsize_var).grid(row=0, column=3, padx=2)
tk.Label(frame_sub2, text="颜色:").grid(row=0, column=4, padx=2)
tk.Entry(frame_sub2, width=8, textvariable=sub2_color_var).grid(row=0, column=5, padx=2)
tk.Button(frame_sub2, text="选择", command=choose_sub2_color).grid(row=0, column=6, padx=2)
tk.Checkbutton(frame_sub2, text="显示", variable=sub2_show_var).grid(row=0, column=7, padx=5)

# 分割选项 for sub2
tk.Checkbutton(frame_sub2, text="分割字幕", variable=split_sub2_var).grid(row=1, column=0, padx=5, pady=5, sticky="w")
tk.Label(frame_sub2, text="最大字符:").grid(row=1, column=1, padx=2)
tk.Spinbox(frame_sub2, from_=10, to=100, width=4, textvariable=sub2_max_chars_var).grid(row=1, column=2, padx=2)
tk.Checkbutton(frame_sub2, text="中文", variable=sub2_is_chinese_var).grid(row=1, column=3, padx=5)

# 水印设置区域
frame_watermark = tk.LabelFrame(root, text="水印设置（右上角）", padx=10, pady=5)
frame_watermark.grid(row=4, column=0, columnspan=3, padx=15, pady=5, sticky="we")

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
frame_progress.grid(row=5, column=0, columnspan=3, pady=10)

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
btn_merge.grid(row=6, column=1, pady=25)

# 初始化分割设置
update_split_settings()

root.mainloop()