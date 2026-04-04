# 这里汇集处理视频的工具，当然也包含音频的一些小功能
# 1、音频提取mp3，可以选择不同的码率
# 2、转换mp3的码率
# 3、调整音量，范围+-20dB，支持音频和视频文件
# 4、提取视频片段，根据起始和结束时间提取视频片段，可同时提取对应字幕
# 5、自动分割视频
#
# This collection includes video processing tools, and of course includes some small audio functions
# 1. Audio extraction to MP3, can choose different bitrates
# 2. Convert MP3 bitrate
# 3. Adjust volume, range +-20dB, supports audio and video files
# 4. Extract video clip, extract video segment based on start and end time, with optional subtitle extraction
# 5. Auto split video

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

def get_video_duration(input_video):
    """
    获取视频时长（秒）
    """
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
           '-of', 'default=noprint_wrappers=1:nokey=1', input_video]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        duration = float(result.stdout.strip())
        return duration
    except:
        return 0

def get_keyframe_times(input_video):
    """
    获取视频的关键帧时间点列表
    """
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
           '-show_entries', 'packet=pts_time,flags', 
           '-of', 'csv=print_section=0', input_video]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        keyframes = []
        for line in result.stdout.strip().split('\n'):
            parts = line.split(',')
            if len(parts) == 2 and 'K' in parts[1]:  # K 表示关键帧
                try:
                    keyframes.append(float(parts[0]))
                except:
                    pass
        return keyframes
    except:
        return []

def find_nearest_keyframe(target_time, keyframes):
    """
    找到最接近目标时间的关键帧
    """
    if not keyframes:
        return target_time
    return min(keyframes, key=lambda x: abs(x - target_time))

def auto_split_video(input_video, output_dir, num_segments, progress_callback, use_keyframes=True):
    """
    自动均匀分割视频
    
    参数：
        input_video: 输入视频文件路径
        output_dir: 输出目录
        num_segments: 分割段数
        progress_callback: 进度回调函数
        use_keyframes: 是否使用关键帧对齐（推荐）
    
    返回：
        (success, message, output_files)
    """
    try:
        # 获取视频时长
        duration = get_video_duration(input_video)
        if duration <= 0:
            return (False, "无法获取视频时长", [])
        
        # 计算每段的理论时长
        segment_duration = duration / num_segments
        
        # 获取关键帧（如果需要）
        keyframes = []
        if use_keyframes:
            keyframes = get_keyframe_times(input_video)
        
        # 计算分割点
        split_points = [0]  # 起始点
        for i in range(1, num_segments):
            target_time = i * segment_duration
            if use_keyframes and keyframes:
                # 找到最近的关键帧
                split_time = find_nearest_keyframe(target_time, keyframes)
            else:
                split_time = target_time
            split_points.append(split_time)
        split_points.append(duration)  # 结束点
        
        # 准备输出文件名
        base_name = os.path.splitext(os.path.basename(input_video))[0]
        ext = os.path.splitext(input_video)[1]
        output_files = []
        
        # 分割视频
        for i in range(num_segments):
            start_time = split_points[i]
            end_time = split_points[i + 1]
            segment_duration_actual = end_time - start_time
            
            output_file = os.path.join(output_dir, f"{base_name}_part{i+1:02d}{ext}")
            output_files.append(output_file)
            
            # 使用快速模式（stream copy）进行分割
            # 当使用关键帧对齐时，stream copy 模式效果很好
            cmd = [
                'ffmpeg',
                '-ss', str(start_time),
                '-i', input_video,
                '-t', str(segment_duration_actual),
                '-c', 'copy',
                '-avoid_negative_ts', 'make_zero',
                output_file,
                '-y'
            ]
            
            process = subprocess.Popen(cmd, stderr=subprocess.PIPE, 
                                      universal_newlines=True, encoding='utf-8', errors='ignore')
            
            # 监控进度
            for line in process.stderr:
                if 'time=' in line and segment_duration_actual > 0:
                    time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                    if time_match:
                        h, m, s = map(float, time_match.groups())
                        current_time = h * 3600 + m * 60 + s
                        segment_progress = min((current_time / segment_duration_actual) * 100, 100)
                        # 计算总进度
                        total_progress = (i / num_segments) * 100 + (segment_progress / num_segments)
                        progress_callback(total_progress)
            
            process.wait()
            if process.returncode != 0:
                return (False, f"分割第 {i+1} 段时出错", output_files[:i])
        
        progress_callback(100)
        return (True, "分割完成！", output_files)
    
    except Exception as e:
        return (False, f"分割出错: {str(e)}", [])

def extract_video_clip(input_video, output_video, start_time, end_time, progress_callback, accurate_mode=True):
    """
    从视频中提取指定时间段的片段
    
    Args:
        input_video: 输入视频文件路径
        output_video: 输出视频文件路径
        start_time: 起始时间，格式：HH:MM:SS 或 HH:MM:SS.mmm
        end_time: 结束时间，格式：HH:MM:SS 或 HH:MM:SS.mmm
        progress_callback: 进度回调函数
        accurate_mode: True=精确模式(重新编码)，False=快速模式(可能不精确)
    """
    # 解析时间字符串为秒
    def parse_time(time_str):
        parts = time_str.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
        return 0
    
    clip_duration = parse_time(end_time) - parse_time(start_time)
    
    if accurate_mode:
        # 精确模式：将 -ss 放在 -i 之前实现快速定位，然后重新编码确保精确性
        # 使用两次 -ss：第一次快速定位到附近关键帧，第二次精确定位
        # -t 参数指定持续时间而不是结束时间，更准确
        cmd = [
            'ffmpeg',
            '-ss', start_time,           # 快速定位到起始时间附近的关键帧
            '-i', input_video,           # 输入文件
            '-t', str(clip_duration),    # 持续时间（比 -to 更精确）
            '-c:v', 'libx264',           # 视频编码器
            '-preset', 'medium',         # 编码速度预设（可选：ultrafast, fast, medium, slow）
            '-crf', '23',                # 质量参数（18-28，越小质量越好）
            '-c:a', 'aac',               # 音频编码器
            '-b:a', '192k',              # 音频码率
            '-avoid_negative_ts', 'make_zero',  # 避免时间戳问题
            output_video,
            '-y'
        ]
    else:
        # 快速模式：使用 stream copy，速度快但可能不精确（受关键帧限制）
        cmd = [
            'ffmpeg',
            '-ss', start_time,           # 放在 -i 之前以加快处理速度
            '-i', input_video,
            '-t', str(clip_duration),
            '-c', 'copy',                # 复制流，不重新编码
            '-avoid_negative_ts', 'make_zero',  # 处理时间戳
            output_video,
            '-y'
        ]
    
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='ignore')
    
    for line in process.stderr:
        if 'time=' in line and clip_duration > 0:
            time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
            if time_match:
                h, m, s = map(float, time_match.groups())
                current_time = h * 3600 + m * 60 + s
                progress = min((current_time / clip_duration) * 100, 100)
                progress_callback(progress)
    
    process.wait()
    if process.returncode == 0:
        progress_callback(100)
        mode_text = "精确模式" if accurate_mode else "快速模式"
        messagebox.showinfo("成功", f"视频片段提取成功！({mode_text})")
    else:
        messagebox.showerror("错误", "提取失败")


def extract_subtitle_clip(input_srt, output_srt, start_time_str, end_time_str):
    """
    根据起止时间提取字幕片段，并重新计算时间戳（偏移到从0开始）
    
    Args:
        input_srt: 输入字幕文件路径 (.srt)
        output_srt: 输出字幕文件路径 (.srt)
        start_time_str: 起始时间，格式：HH:MM:SS 或 HH:MM:SS.mmm
        end_time_str: 结束时间，格式：HH:MM:SS 或 HH:MM:SS.mmm
    
    Returns:
        (success, message, count) - 是否成功、消息、提取的字幕条数
    """
    def parse_time_to_seconds(time_str):
        """将 HH:MM:SS 或 HH:MM:SS.mmm 格式转为秒"""
        parts = time_str.strip().split(':')
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
        return 0

    def parse_srt_timestamp(ts):
        """将 SRT 时间戳 (HH:MM:SS,mmm) 转为秒"""
        ts = ts.strip().replace(',', '.')
        parts = ts.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
        return 0

    def seconds_to_srt_timestamp(total_seconds):
        """将秒数转为 SRT 时间戳格式 (HH:MM:SS,mmm)"""
        if total_seconds < 0:
            total_seconds = 0
        h = int(total_seconds // 3600)
        m = int((total_seconds % 3600) // 60)
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')

    try:
        start_seconds = parse_time_to_seconds(start_time_str)
        end_seconds = parse_time_to_seconds(end_time_str)

        # 读取 SRT 文件
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1']
        content = None
        for enc in encodings:
            try:
                with open(input_srt, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        if content is None:
            return (False, "无法读取字幕文件，编码不支持", 0)

        # 解析 SRT 条目
        # SRT 格式: 序号\n时间戳\n文本\n\n
        blocks = re.split(r'\n\s*\n', content.strip())
        extracted = []

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 2:
                continue
            
            # 查找时间戳行 (包含 -->)
            ts_line_idx = None
            for i, line in enumerate(lines):
                if '-->' in line:
                    ts_line_idx = i
                    break
            
            if ts_line_idx is None:
                continue

            ts_match = re.match(
                r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})', 
                lines[ts_line_idx].strip()
            )
            if not ts_match:
                continue

            sub_start = parse_srt_timestamp(ts_match.group(1))
            sub_end = parse_srt_timestamp(ts_match.group(2))
            text_lines = lines[ts_line_idx + 1:]

            # 字幕与提取范围有交集则保留
            if sub_end <= start_seconds or sub_start >= end_seconds:
                continue

            # 裁剪并偏移时间戳
            new_start = max(sub_start, start_seconds) - start_seconds
            new_end = min(sub_end, end_seconds) - start_seconds

            extracted.append({
                'start': new_start,
                'end': new_end,
                'text': '\n'.join(text_lines)
            })

        if not extracted:
            return (True, "指定时间范围内没有找到字幕", 0)

        # 写入新的 SRT 文件
        with open(output_srt, 'w', encoding='utf-8') as f:
            for idx, item in enumerate(extracted, 1):
                f.write(f"{idx}\n")
                f.write(f"{seconds_to_srt_timestamp(item['start'])} --> {seconds_to_srt_timestamp(item['end'])}\n")
                f.write(f"{item['text']}\n\n")

        return (True, f"成功提取 {len(extracted)} 条字幕", len(extracted))

    except Exception as e:
        return (False, f"字幕提取出错: {str(e)}", 0)


# ===================== 独立操作窗口（每个 Tab 拆为单窗口）=====================

class ExtractAudioApp:
    """Tab 1：提取 MP3 — 独立窗口版。"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("提取 MP3")
        master.geometry("620x280")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.bitrate_var = tk.StringVar(value="128k")
        self.status_var = tk.StringVar()
        if initial_file:
            self.input_var.set(initial_file)
            self.output_var.set(os.path.splitext(initial_file)[0] + ".mp3")
        self._build_ui()

    def _build_ui(self):
        f = self.master
        tk.Label(f, text="输入视频文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Entry(f, textvariable=self.input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_input).grid(row=0, column=2, padx=10)

        tk.Label(f, text="输出MP3文件:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        tk.Entry(f, textvariable=self.output_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_output).grid(row=1, column=2, padx=10)

        tk.Label(f, text="选择码率:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        br_frame = tk.Frame(f)
        br_frame.grid(row=2, column=1, sticky="w")
        ttk.Combobox(br_frame, textvariable=self.bitrate_var,
                     values=["64k", "128k", "192k", "256k", "320k"],
                     state="readonly", width=15).pack(side=tk.LEFT)
        tk.Label(br_frame, text="(推荐: 128k 或 192k)", font=("Arial", 9), fg="gray").pack(side=tk.LEFT, padx=10)

        self._btn = tk.Button(f, text="开始提取", command=self._run, width=20)
        self._btn.grid(row=3, column=1, pady=25)

        self._progress = ttk.Progressbar(f, orient="horizontal", length=500, mode="determinate")
        self._progress.grid(row=4, column=0, columnspan=3, pady=10, padx=20)

        tk.Label(f, textvariable=self.status_var, fg="blue").grid(row=5, column=0, columnspan=3)

    def _select_input(self):
        path = filedialog.askopenfilename(
            filetypes=[("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv")])
        if path:
            self.input_var.set(path)
            self.output_var.set(os.path.splitext(path)[0] + ".mp3")

    def _select_output(self):
        path = filedialog.asksaveasfilename(defaultextension=".mp3",
                                            filetypes=[("MP3文件", "*.mp3")])
        if path:
            self.output_var.set(path)

    def _run(self):
        src, dst = self.input_var.get(), self.output_var.get()
        if not src or not dst:
            messagebox.showerror("错误", "请选择输入和输出文件")
            return
        self._btn.config(state="disabled")
        self._progress["value"] = 0
        self.status_var.set("正在提取音频...")

        def _progress_cb(v):
            self._progress["value"] = v
            self.master.update_idletasks()

        def _work():
            extract_audio_to_mp3(src, dst, self.bitrate_var.get(), _progress_cb)
            self._btn.config(state="normal")
            self.status_var.set("提取完成！")

        threading.Thread(target=_work, daemon=True).start()


class ConvertBitrateApp:
    """Tab 2：码率转换 — 独立窗口版。"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("码率转换")
        master.geometry("620x280")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.bitrate_var = tk.StringVar(value="192k")
        self.status_var = tk.StringVar()
        if initial_file:
            self.input_var.set(initial_file)
            base, ext = os.path.splitext(initial_file)
            self.output_var.set(base + "_converted" + ext)
        self._build_ui()

    def _build_ui(self):
        f = self.master
        tk.Label(f, text="输入MP3文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Entry(f, textvariable=self.input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_input).grid(row=0, column=2, padx=10)

        tk.Label(f, text="输出MP3文件:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        tk.Entry(f, textvariable=self.output_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_output).grid(row=1, column=2, padx=10)

        tk.Label(f, text="目标码率:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        br_frame = tk.Frame(f)
        br_frame.grid(row=2, column=1, sticky="w")
        ttk.Combobox(br_frame, textvariable=self.bitrate_var,
                     values=["64k", "128k", "192k", "256k", "320k"],
                     state="readonly", width=15).pack(side=tk.LEFT)
        tk.Label(br_frame, text="(选择要转换到的码率)", font=("Arial", 9), fg="gray").pack(side=tk.LEFT, padx=10)

        self._btn = tk.Button(f, text="开始转换", command=self._run, width=20)
        self._btn.grid(row=3, column=1, pady=25)

        self._progress = ttk.Progressbar(f, orient="horizontal", length=500, mode="determinate")
        self._progress.grid(row=4, column=0, columnspan=3, pady=10, padx=20)

        tk.Label(f, textvariable=self.status_var, fg="blue").grid(row=5, column=0, columnspan=3)

    def _select_input(self):
        path = filedialog.askopenfilename(filetypes=[("MP3文件", "*.mp3")])
        if path:
            self.input_var.set(path)
            base, ext = os.path.splitext(path)
            self.output_var.set(base + "_converted" + ext)

    def _select_output(self):
        path = filedialog.asksaveasfilename(defaultextension=".mp3",
                                            filetypes=[("MP3文件", "*.mp3")])
        if path:
            self.output_var.set(path)

    def _run(self):
        src, dst = self.input_var.get(), self.output_var.get()
        if not src or not dst:
            messagebox.showerror("错误", "请选择输入和输出文件")
            return
        self._btn.config(state="disabled")
        self._progress["value"] = 0
        self.status_var.set("正在转换码率...")

        def _progress_cb(v):
            self._progress["value"] = v
            self.master.update_idletasks()

        def _work():
            convert_mp3_bitrate(src, dst, self.bitrate_var.get(), _progress_cb)
            self._btn.config(state="normal")
            self.status_var.set("转换完成！")

        threading.Thread(target=_work, daemon=True).start()


class AdjustVolumeApp:
    """Tab 3：调整音量 — 独立窗口版。"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("调整音量")
        master.geometry("620x320")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.volume_var = tk.DoubleVar(value=0.0)
        self.status_var = tk.StringVar()
        if initial_file:
            self.input_var.set(initial_file)
            base, ext = os.path.splitext(initial_file)
            self.output_var.set(base + "_vol" + ext)
        self._build_ui()

    def _build_ui(self):
        f = self.master
        tk.Label(f, text="输入文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Entry(f, textvariable=self.input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_input).grid(row=0, column=2, padx=10)

        tk.Label(f, text="输出文件:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        tk.Entry(f, textvariable=self.output_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_output).grid(row=1, column=2, padx=10)

        tk.Label(f, text="音量调整:").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        vol_frame = tk.Frame(f)
        vol_frame.grid(row=2, column=1, sticky="w", pady=10)
        self._vol_label = tk.Label(vol_frame, text="0.0 dB", font=("Arial", 10, "bold"))
        self._vol_label.pack()
        tk.Scale(vol_frame, from_=-20, to=20, orient=tk.HORIZONTAL, resolution=0.5,
                 variable=self.volume_var, length=400,
                 command=lambda v: self._vol_label.config(text=f"{float(v):.1f} dB")).pack()
        tk.Label(vol_frame, text="(-20dB ~ +20dB，正值增大音量，负值减小音量)",
                 font=("Arial", 8), fg="gray").pack()

        self._btn = tk.Button(f, text="开始调整", command=self._run, width=20)
        self._btn.grid(row=3, column=1, pady=20)

        self._progress = ttk.Progressbar(f, orient="horizontal", length=500, mode="determinate")
        self._progress.grid(row=4, column=0, columnspan=3, pady=10, padx=20)

        tk.Label(f, textvariable=self.status_var, fg="blue").grid(row=5, column=0, columnspan=3)

    def _select_input(self):
        path = filedialog.askopenfilename(
            filetypes=[("视频/音频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.mp3 *.wav *.flac")])
        if path:
            self.input_var.set(path)
            base, ext = os.path.splitext(path)
            self.output_var.set(base + "_vol" + ext)

    def _select_output(self):
        src = self.input_var.get()
        if src and src.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv')):
            ft, defext = [("视频文件", "*.mp4")], ".mp4"
        else:
            ft, defext = [("音频文件", "*.mp3")], ".mp3"
        path = filedialog.asksaveasfilename(defaultextension=defext, filetypes=ft)
        if path:
            self.output_var.set(path)

    def _run(self):
        src, dst = self.input_var.get(), self.output_var.get()
        if not src or not dst:
            messagebox.showerror("错误", "请选择输入和输出文件")
            return
        db = self.volume_var.get()
        self._btn.config(state="disabled")
        self._progress["value"] = 0
        self.status_var.set(f"正在调整音量 ({db:+.1f} dB)...")

        def _progress_cb(v):
            self._progress["value"] = v
            self.master.update_idletasks()

        def _work():
            adjust_volume(src, dst, db, _progress_cb)
            self._btn.config(state="normal")
            self.status_var.set("音量调整完成！")

        threading.Thread(target=_work, daemon=True).start()


class ExtractClipApp:
    """Tab 4：视频片段提取 — 独立窗口版。"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("视频片段提取")
        master.geometry("650x420")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.start_var = tk.StringVar(value="00:00:00")
        self.end_var = tk.StringVar(value="00:00:10")
        self.mode_var = tk.StringVar(value="accurate")
        self.srt_input_var = tk.StringVar()
        self.status_var = tk.StringVar()
        if initial_file:
            self.input_var.set(initial_file)
            base, ext = os.path.splitext(initial_file)
            self.output_var.set(base + "_clip" + ext)
        self._build_ui()

    def _build_ui(self):
        f = self.master
        tk.Label(f, text="输入视频文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Entry(f, textvariable=self.input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_input).grid(row=0, column=2, padx=10)

        tk.Label(f, text="起始时间:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        sf = tk.Frame(f)
        sf.grid(row=1, column=1, sticky="w")
        tk.Entry(sf, textvariable=self.start_var, width=15).pack(side=tk.LEFT)
        tk.Label(sf, text="(格式: HH:MM:SS 或 HH:MM:SS.mmm)",
                 font=("Arial", 9), fg="gray").pack(side=tk.LEFT, padx=10)

        tk.Label(f, text="结束时间:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        ef = tk.Frame(f)
        ef.grid(row=2, column=1, sticky="w")
        tk.Entry(ef, textvariable=self.end_var, width=15).pack(side=tk.LEFT)
        tk.Label(ef, text="(格式: HH:MM:SS 或 HH:MM:SS.mmm)",
                 font=("Arial", 9), fg="gray").pack(side=tk.LEFT, padx=10)

        tk.Label(f, text="提取模式:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        mf = tk.Frame(f)
        mf.grid(row=3, column=1, sticky="w")
        tk.Radiobutton(mf, text="精确模式 (推荐)", variable=self.mode_var,
                       value="accurate").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(mf, text="快速模式", variable=self.mode_var,
                       value="fast").pack(side=tk.LEFT, padx=5)
        self._mode_hint = tk.Label(mf, text="", font=("Arial", 8), fg="gray")
        self._mode_hint.pack(side=tk.LEFT, padx=10)
        self.mode_var.trace_add('write', lambda *_: self._update_mode_hint())
        self._update_mode_hint()

        tk.Label(f, text="输入字幕文件:").grid(row=4, column=0, padx=10, pady=5, sticky="e")
        srtf = tk.Frame(f)
        srtf.grid(row=4, column=1, sticky="w")
        tk.Entry(srtf, textvariable=self.srt_input_var, width=40).pack(side=tk.LEFT)
        tk.Button(srtf, text="浏览", command=lambda: self._select_srt()).pack(side=tk.LEFT, padx=5)
        tk.Label(srtf, text="(可选)", font=("Arial", 9), fg="gray").pack(side=tk.LEFT)

        tk.Label(f, text="输出视频文件:").grid(row=5, column=0, padx=10, pady=5, sticky="e")
        tk.Entry(f, textvariable=self.output_var, width=50).grid(row=5, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_output).grid(row=5, column=2, padx=10)

        self._btn = tk.Button(f, text="开始提取", command=self._run, width=20)
        self._btn.grid(row=6, column=1, pady=20)

        self._progress = ttk.Progressbar(f, orient="horizontal", length=500, mode="determinate")
        self._progress.grid(row=7, column=0, columnspan=3, pady=10, padx=20)

        tk.Label(f, textvariable=self.status_var, fg="blue").grid(row=8, column=0, columnspan=3)

    def _update_mode_hint(self):
        if self.mode_var.get() == "accurate":
            self._mode_hint.config(text="精确剪切，时间准确，需重新编码（稍慢）", fg="green")
        else:
            self._mode_hint.config(text="快速剪切，可能受关键帧影响", fg="orange")

    def _select_input(self):
        path = filedialog.askopenfilename(
            filetypes=[("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv")])
        if path:
            self.input_var.set(path)
            base, ext = os.path.splitext(path)
            self.output_var.set(base + "_clip" + ext)

    def _select_srt(self):
        path = filedialog.askopenfilename(filetypes=[("字幕文件", "*.srt")])
        if path:
            self.srt_input_var.set(path)

    def _select_output(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("视频文件", "*.mp4"), ("所有视频", "*.avi *.mkv *.mov")])
        if path:
            self.output_var.set(path)

    def _run(self):
        src, dst = self.input_var.get(), self.output_var.get()
        start, end = self.start_var.get(), self.end_var.get()
        if not src or not dst:
            messagebox.showerror("错误", "请选择输入和输出文件")
            return
        time_pattern = r'^\d{1,2}:\d{2}:\d{2}(\.\d{1,3})?$'
        if not re.match(time_pattern, start) or not re.match(time_pattern, end):
            messagebox.showerror("错误", "时间格式不正确，请使用 HH:MM:SS 或 HH:MM:SS.mmm 格式")
            return
        input_srt = self.srt_input_var.get().strip()
        if input_srt and not os.path.isfile(input_srt):
            messagebox.showerror("错误", "指定的字幕文件不存在")
            return
        accurate = (self.mode_var.get() == "accurate")
        mode_text = "精确模式" if accurate else "快速模式"
        self._btn.config(state="disabled")
        self._progress["value"] = 0
        self.status_var.set(f"正在提取视频片段 ({mode_text})...")

        def _progress_cb(v):
            self._progress["value"] = v
            self.master.update_idletasks()

        def _work():
            extract_video_clip(src, dst, start, end, _progress_cb, accurate)
            srt_msg = ""
            if input_srt:
                out_srt = os.path.splitext(dst)[0] + '.srt'
                ok, msg, count = extract_subtitle_clip(input_srt, out_srt, start, end)
                srt_msg = f"\n字幕：{msg}" + (f"，已保存到 {os.path.basename(out_srt)}" if ok and count > 0 else "")
            self._btn.config(state="normal")
            self.status_var.set(f"✓ 视频片段提取完成！({mode_text}){srt_msg}")

        threading.Thread(target=_work, daemon=True).start()


class AutoSplitApp:
    """Tab 5：自动分割视频 — 独立窗口版。"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("自动分割视频")
        master.geometry("650x380")
        self.input_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.segments_var = tk.IntVar(value=3)
        self.keyframe_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar()
        if initial_file:
            self.input_var.set(initial_file)
            self.output_dir_var.set(os.path.dirname(initial_file))
        self._build_ui()

    def _build_ui(self):
        f = self.master
        tk.Label(f, text="输入视频文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Entry(f, textvariable=self.input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_input).grid(row=0, column=2, padx=10)

        tk.Label(f, text="输出目录:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        tk.Entry(f, textvariable=self.output_dir_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(f, text="浏览", command=self._select_dir).grid(row=1, column=2, padx=10)

        tk.Label(f, text="分割段数:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        seg_frame = tk.Frame(f)
        seg_frame.grid(row=2, column=1, sticky="w")
        tk.Spinbox(seg_frame, from_=2, to=20, textvariable=self.segments_var, width=10).pack(side=tk.LEFT)
        tk.Label(seg_frame, text="(将视频均匀分割为几段，默认3段)",
                 font=("Arial", 9), fg="gray").pack(side=tk.LEFT, padx=10)

        tk.Label(f, text="分割模式:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        kf_frame = tk.Frame(f)
        kf_frame.grid(row=3, column=1, sticky="w")
        tk.Checkbutton(kf_frame, text="关键帧对齐 (推荐)",
                       variable=self.keyframe_var).pack(side=tk.LEFT, padx=5)
        self._kf_hint = tk.Label(kf_frame, text="", font=("Arial", 8), fg="gray")
        self._kf_hint.pack(side=tk.LEFT, padx=10)
        self.keyframe_var.trace_add('write', lambda *_: self._update_kf_hint())
        self._update_kf_hint()

        info = ("功能说明：\n"
                "• 自动将视频均匀分割为指定的段数\n"
                "• 关键帧对齐模式：在最近的关键帧处分割，速度快，无需重新编码\n"
                "• 输出文件将自动命名为：原文件名_part01, _part02, ...\n"
                "• 推荐使用关键帧对齐模式以获得最佳性能")
        tk.Label(f, text=info, justify=tk.LEFT, font=("Arial", 9),
                 fg="darkblue", bg="#f0f8ff").grid(row=4, column=0, columnspan=3, pady=10, padx=20)

        self._btn = tk.Button(f, text="开始分割", command=self._run, width=20)
        self._btn.grid(row=5, column=1, pady=20)

        self._progress = ttk.Progressbar(f, orient="horizontal", length=500, mode="determinate")
        self._progress.grid(row=6, column=0, columnspan=3, pady=10, padx=20)

        tk.Label(f, textvariable=self.status_var, fg="blue").grid(row=7, column=0, columnspan=3)

    def _update_kf_hint(self):
        if self.keyframe_var.get():
            self._kf_hint.config(text="在关键帧处分割，速度快且无需重新编码", fg="green")
        else:
            self._kf_hint.config(text="按精确时间分割，可能稍慢", fg="orange")

    def _select_input(self):
        path = filedialog.askopenfilename(
            filetypes=[("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv")])
        if path:
            self.input_var.set(path)
            self.output_dir_var.set(os.path.dirname(path))

    def _select_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.output_dir_var.set(d)

    def _run(self):
        src = self.input_var.get()
        out_dir = self.output_dir_var.get()
        n = self.segments_var.get()
        use_kf = self.keyframe_var.get()
        if not src or not out_dir:
            messagebox.showerror("错误", "请选择输入文件和输出目录")
            return
        if n < 2:
            messagebox.showerror("错误", "分割段数至少为2段")
            return
        if not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir)
            except Exception:
                messagebox.showerror("错误", "无法创建输出目录")
                return
        mode_text = "关键帧对齐" if use_kf else "精确时间"
        self._btn.config(state="disabled")
        self._progress["value"] = 0
        self.status_var.set(f"正在分割视频为 {n} 段 ({mode_text})...")

        def _progress_cb(v):
            self._progress["value"] = v
            self.master.update_idletasks()

        def _work():
            success, message, output_files = auto_split_video(src, out_dir, n, _progress_cb, use_kf)
            self._btn.config(state="normal")
            if success:
                self.status_var.set(f"✓ 分割完成！已生成 {len(output_files)} 个文件")
                result = f"✓ {message}\n生成了 {len(output_files)} 个文件：\n"
                for fp in output_files:
                    result += f"  • {os.path.basename(fp)}\n"
                messagebox.showinfo("成功", result)
            else:
                self.status_var.set(f"✗ 分割失败：{message}")
                messagebox.showerror("错误", message)

        threading.Thread(target=_work, daemon=True).start()


# ===================== GUI 主界面（保留，向后兼容）=====================
class VideoToolsGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VideoTools - 视频音频工具")
        self.root.geometry("700x450")
        self.root.resizable(False, False)

        # 创建标签页
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # 创建各个功能标签页
        self.create_extract_audio_tab()
        self.create_convert_bitrate_tab()
        self.create_adjust_volume_tab()
        self.create_extract_clip_tab()
        self.create_auto_split_tab()

    def create_extract_audio_tab(self):
        """创建音频提取标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="音频提取")

        # 输入文件
        tk.Label(tab, text="输入视频文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.extract_input_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.extract_input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=lambda: self.select_file(
            self.extract_input_var,
            [("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv")]
        )).grid(row=0, column=2, padx=10)

        # 输出文件
        tk.Label(tab, text="输出MP3文件:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.extract_output_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.extract_output_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=lambda: self.save_file(
            self.extract_output_var,
            [("MP3文件", "*.mp3")],
            ".mp3"
        )).grid(row=1, column=2, padx=10)

        # 码率选择
        tk.Label(tab, text="选择码率:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.extract_bitrate_var = tk.StringVar(value="128k")
        bitrate_frame = tk.Frame(tab)
        bitrate_frame.grid(row=2, column=1, sticky="w")
        ttk.Combobox(bitrate_frame, textvariable=self.extract_bitrate_var, 
                     values=["64k", "128k", "192k", "256k", "320k"], 
                     state="readonly", width=15).pack(side=tk.LEFT)
        tk.Label(bitrate_frame, text="(推荐: 128k 或 192k)", font=("Arial", 9), fg="gray").pack(side=tk.LEFT, padx=10)

        # 执行按钮
        self.extract_btn = tk.Button(tab, text="开始提取", command=self.execute_extract_audio, width=20)
        self.extract_btn.grid(row=3, column=1, pady=25)

        # 进度条
        self.extract_progress = ttk.Progressbar(tab, orient="horizontal", length=500, mode="determinate")
        self.extract_progress.grid(row=4, column=0, columnspan=3, pady=10, padx=20)

        # 状态提示
        self.extract_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.extract_status_var, fg="blue").grid(row=5, column=0, columnspan=3)

    def create_convert_bitrate_tab(self):
        """创建码率转换标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="码率转换")

        # 输入文件
        tk.Label(tab, text="输入MP3文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.convert_input_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.convert_input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=lambda: self.select_file(
            self.convert_input_var,
            [("MP3文件", "*.mp3")]
        )).grid(row=0, column=2, padx=10)

        # 输出文件
        tk.Label(tab, text="输出MP3文件:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.convert_output_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.convert_output_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=lambda: self.save_file(
            self.convert_output_var,
            [("MP3文件", "*.mp3")],
            ".mp3"
        )).grid(row=1, column=2, padx=10)

        # 码率选择
        tk.Label(tab, text="目标码率:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.convert_bitrate_var = tk.StringVar(value="192k")
        bitrate_frame = tk.Frame(tab)
        bitrate_frame.grid(row=2, column=1, sticky="w")
        ttk.Combobox(bitrate_frame, textvariable=self.convert_bitrate_var, 
                     values=["64k", "128k", "192k", "256k", "320k"], 
                     state="readonly", width=15).pack(side=tk.LEFT)
        tk.Label(bitrate_frame, text="(选择要转换到的码率)", font=("Arial", 9), fg="gray").pack(side=tk.LEFT, padx=10)

        # 执行按钮
        self.convert_btn = tk.Button(tab, text="开始转换", command=self.execute_convert_bitrate, width=20)
        self.convert_btn.grid(row=3, column=1, pady=25)

        # 进度条
        self.convert_progress = ttk.Progressbar(tab, orient="horizontal", length=500, mode="determinate")
        self.convert_progress.grid(row=4, column=0, columnspan=3, pady=10, padx=20)

        # 状态提示
        self.convert_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.convert_status_var, fg="blue").grid(row=5, column=0, columnspan=3)

    def create_adjust_volume_tab(self):
        """创建音量调整标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="音量调整")

        # 输入文件
        tk.Label(tab, text="输入文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.volume_input_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.volume_input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=lambda: self.select_file(
            self.volume_input_var,
            [("视频/音频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.mp3 *.wav *.flac")]
        )).grid(row=0, column=2, padx=10)

        # 输出文件
        tk.Label(tab, text="输出文件:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.volume_output_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.volume_output_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_volume_output).grid(row=1, column=2, padx=10)

        # 音量调整
        tk.Label(tab, text="音量调整:").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        volume_frame = tk.Frame(tab)
        volume_frame.grid(row=2, column=1, sticky="w", pady=10)
        
        self.volume_var = tk.DoubleVar(value=0.0)
        self.volume_label = tk.Label(volume_frame, text="0.0 dB", font=("Arial", 10, "bold"))
        self.volume_label.pack()
        
        volume_scale = tk.Scale(volume_frame, from_=-20, to=20, orient=tk.HORIZONTAL, 
                               resolution=0.5, variable=self.volume_var, length=400,
                               command=self.update_volume_label)
        volume_scale.pack()
        
        tk.Label(volume_frame, text="(-20dB ~ +20dB，正值增大音量，负值减小音量)", 
                font=("Arial", 8), fg="gray").pack()

        # 执行按钮
        self.volume_btn = tk.Button(tab, text="开始调整", command=self.execute_adjust_volume, width=20)
        self.volume_btn.grid(row=3, column=1, pady=25)

        # 进度条
        self.volume_progress = ttk.Progressbar(tab, orient="horizontal", length=500, mode="determinate")
        self.volume_progress.grid(row=4, column=0, columnspan=3, pady=10, padx=20)

        # 状态提示
        self.volume_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.volume_status_var, fg="blue").grid(row=5, column=0, columnspan=3)

    def create_extract_clip_tab(self):
        """创建视频片段提取标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="视频片段提取")

        # 输入文件
        tk.Label(tab, text="输入视频文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.clip_input_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.clip_input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=lambda: self.select_file(
            self.clip_input_var,
            [("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv")]
        )).grid(row=0, column=2, padx=10)

        # 起始时间
        tk.Label(tab, text="起始时间:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        time_start_frame = tk.Frame(tab)
        time_start_frame.grid(row=1, column=1, sticky="w")
        self.clip_start_var = tk.StringVar(value="00:00:00")
        tk.Entry(time_start_frame, textvariable=self.clip_start_var, width=15).pack(side=tk.LEFT)
        tk.Label(time_start_frame, text="(格式: HH:MM:SS 或 HH:MM:SS.mmm)", 
                font=("Arial", 9), fg="gray").pack(side=tk.LEFT, padx=10)

        # 结束时间
        tk.Label(tab, text="结束时间:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        time_end_frame = tk.Frame(tab)
        time_end_frame.grid(row=2, column=1, sticky="w")
        self.clip_end_var = tk.StringVar(value="00:00:10")
        tk.Entry(time_end_frame, textvariable=self.clip_end_var, width=15).pack(side=tk.LEFT)
        tk.Label(time_end_frame, text="(格式: HH:MM:SS 或 HH:MM:SS.mmm)", 
                font=("Arial", 9), fg="gray").pack(side=tk.LEFT, padx=10)

        # 提取模式选择
        tk.Label(tab, text="提取模式:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        mode_frame = tk.Frame(tab)
        mode_frame.grid(row=3, column=1, sticky="w")
        
        self.clip_mode_var = tk.StringVar(value="accurate")
        tk.Radiobutton(mode_frame, text="精确模式 (推荐)", variable=self.clip_mode_var, 
                      value="accurate").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(mode_frame, text="快速模式", variable=self.clip_mode_var, 
                      value="fast").pack(side=tk.LEFT, padx=5)
        
        mode_hint = tk.Label(mode_frame, text="", font=("Arial", 8), fg="gray")
        mode_hint.pack(side=tk.LEFT, padx=10)
        
        # 添加模式说明更新
        def update_mode_hint(*args):
            if self.clip_mode_var.get() == "accurate":
                mode_hint.config(text="精确剪切，时间准确，需重新编码（稍慢）", fg="green")
            else:
                mode_hint.config(text="快速剪切，可能受关键帧影响", fg="orange")
        
        self.clip_mode_var.trace_add('write', lambda *args: update_mode_hint())
        update_mode_hint()  # 初始化显示

        # 输入字幕文件（可选）
        tk.Label(tab, text="输入字幕文件:").grid(row=4, column=0, padx=10, pady=5, sticky="e")
        srt_input_frame = tk.Frame(tab)
        srt_input_frame.grid(row=4, column=1, sticky="w")
        self.clip_srt_input_var = tk.StringVar()
        tk.Entry(srt_input_frame, textvariable=self.clip_srt_input_var, width=40).pack(side=tk.LEFT)
        tk.Button(srt_input_frame, text="浏览", command=lambda: self.select_file(
            self.clip_srt_input_var,
            [("字幕文件", "*.srt")]
        )).pack(side=tk.LEFT, padx=5)
        tk.Label(srt_input_frame, text="(可选)", font=("Arial", 9), fg="gray").pack(side=tk.LEFT)

        # 输出视频文件
        tk.Label(tab, text="输出视频文件:").grid(row=5, column=0, padx=10, pady=5, sticky="e")
        self.clip_output_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.clip_output_var, width=50).grid(row=5, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=lambda: self.save_file(
            self.clip_output_var,
            [("视频文件", "*.mp4"), ("所有视频", "*.avi *.mkv *.mov")],
            ".mp4"
        )).grid(row=5, column=2, padx=10)

        # 执行按钮
        self.clip_btn = tk.Button(tab, text="开始提取", command=self.execute_extract_clip, width=20)
        self.clip_btn.grid(row=6, column=1, pady=25)

        # 进度条
        self.clip_progress = ttk.Progressbar(tab, orient="horizontal", length=500, mode="determinate")
        self.clip_progress.grid(row=7, column=0, columnspan=3, pady=10, padx=20)

        # 状态提示
        self.clip_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.clip_status_var, fg="blue").grid(row=8, column=0, columnspan=3)

    def create_auto_split_tab(self):
        """创建自动分割视频标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="自动分割视频")

        # 输入文件
        tk.Label(tab, text="输入视频文件:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.split_input_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.split_input_var, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=lambda: self.select_file(
            self.split_input_var,
            [("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv")]
        )).grid(row=0, column=2, padx=10)

        # 输出目录
        tk.Label(tab, text="输出目录:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.split_output_dir_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.split_output_dir_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_output_dir).grid(row=1, column=2, padx=10)

        # 分割段数
        tk.Label(tab, text="分割段数:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        segments_frame = tk.Frame(tab)
        segments_frame.grid(row=2, column=1, sticky="w")
        self.split_segments_var = tk.IntVar(value=3)
        segment_spinbox = tk.Spinbox(segments_frame, from_=2, to=20, 
                                     textvariable=self.split_segments_var, width=10)
        segment_spinbox.pack(side=tk.LEFT)
        tk.Label(segments_frame, text="(将视频均匀分割为几段，默认3段)", 
                font=("Arial", 9), fg="gray").pack(side=tk.LEFT, padx=10)

        # 关键帧对齐选项
        tk.Label(tab, text="分割模式:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        keyframe_frame = tk.Frame(tab)
        keyframe_frame.grid(row=3, column=1, sticky="w")
        
        self.split_keyframe_var = tk.BooleanVar(value=True)
        tk.Checkbutton(keyframe_frame, text="关键帧对齐 (推荐)", 
                      variable=self.split_keyframe_var).pack(side=tk.LEFT, padx=5)
        
        keyframe_hint = tk.Label(keyframe_frame, text="", font=("Arial", 8), fg="gray")
        keyframe_hint.pack(side=tk.LEFT, padx=10)
        
        # 添加模式说明更新
        def update_keyframe_hint(*args):
            if self.split_keyframe_var.get():
                keyframe_hint.config(text="在关键帧处分割，速度快且无需重新编码", fg="green")
            else:
                keyframe_hint.config(text="按精确时间分割，可能稍慢", fg="orange")
        
        self.split_keyframe_var.trace_add('write', lambda *args: update_keyframe_hint())
        update_keyframe_hint()  # 初始化显示

        # 说明文本
        info_frame = tk.Frame(tab)
        info_frame.grid(row=4, column=0, columnspan=3, pady=10, padx=20)
        info_text = (
            "功能说明：\n"
            "• 自动将视频均匀分割为指定的段数\n"
            "• 关键帧对齐模式：在最近的关键帧处分割，速度快，无需重新编码\n"
            "• 输出文件将自动命名为：原文件名_part01, _part02, ...\n"
            "• 推荐使用关键帧对齐模式以获得最佳性能"
        )
        tk.Label(info_frame, text=info_text, justify=tk.LEFT, 
                font=("Arial", 9), fg="darkblue", bg="#f0f8ff").pack()

        # 执行按钮
        self.split_btn = tk.Button(tab, text="开始分割", command=self.execute_auto_split, width=20)
        self.split_btn.grid(row=5, column=1, pady=25)

        # 进度条
        self.split_progress = ttk.Progressbar(tab, orient="horizontal", length=500, mode="determinate")
        self.split_progress.grid(row=6, column=0, columnspan=3, pady=10, padx=20)

        # 状态提示
        self.split_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.split_status_var, fg="blue").grid(row=7, column=0, columnspan=3)

    # 工具方法
    def select_file(self, var, filetypes):
        """选择输入文件"""
        file_path = filedialog.askopenfilename(filetypes=filetypes)
        if file_path:
            var.set(file_path)

    def save_file(self, var, filetypes, defaultextension):
        """选择输出文件"""
        file_path = filedialog.asksaveasfilename(defaultextension=defaultextension, filetypes=filetypes)
        if file_path:
            var.set(file_path)

    def select_volume_output(self):
        """为音量调整选择输出文件（根据输入类型自动判断）"""
        input_file = self.volume_input_var.get()
        if input_file:
            if input_file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv')):
                defaultextension = ".mp4"
                filetypes = [("视频文件", "*.mp4")]
            else:
                defaultextension = ".mp3"
                filetypes = [("音频文件", "*.mp3")]
        else:
            defaultextension = ".mp4"
            filetypes = [("视频/音频文件", "*.mp4 *.mp3")]
        
        self.save_file(self.volume_output_var, filetypes, defaultextension)

    def select_output_dir(self):
        """选择输出目录"""
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.split_output_dir_var.set(dir_path)

    def update_volume_label(self, value):
        """更新音量标签显示"""
        self.volume_label.config(text=f"{float(value):.1f} dB")

    # 执行方法
    def execute_extract_audio(self):
        """执行音频提取"""
        input_file = self.extract_input_var.get()
        output_file = self.extract_output_var.get()
        bitrate = self.extract_bitrate_var.get()

        if not input_file or not output_file:
            messagebox.showerror("错误", "请选择输入和输出文件")
            return

        self.extract_btn.config(state="disabled")
        self.extract_progress["value"] = 0
        self.extract_status_var.set("正在提取音频...")

        def update_progress(value):
            self.extract_progress["value"] = value
            self.root.update_idletasks()

        def run():
            extract_audio_to_mp3(input_file, output_file, bitrate, update_progress)
            self.extract_btn.config(state="normal")
            self.extract_status_var.set("提取完成！")

        threading.Thread(target=run, daemon=True).start()

    def execute_convert_bitrate(self):
        """执行码率转换"""
        input_file = self.convert_input_var.get()
        output_file = self.convert_output_var.get()
        bitrate = self.convert_bitrate_var.get()

        if not input_file or not output_file:
            messagebox.showerror("错误", "请选择输入和输出文件")
            return

        self.convert_btn.config(state="disabled")
        self.convert_progress["value"] = 0
        self.convert_status_var.set("正在转换码率...")

        def update_progress(value):
            self.convert_progress["value"] = value
            self.root.update_idletasks()

        def run():
            convert_mp3_bitrate(input_file, output_file, bitrate, update_progress)
            self.convert_btn.config(state="normal")
            self.convert_status_var.set("转换完成！")

        threading.Thread(target=run, daemon=True).start()

    def execute_adjust_volume(self):
        """执行音量调整"""
        input_file = self.volume_input_var.get()
        output_file = self.volume_output_var.get()
        db_change = self.volume_var.get()

        if not input_file or not output_file:
            messagebox.showerror("错误", "请选择输入和输出文件")
            return

        self.volume_btn.config(state="disabled")
        self.volume_progress["value"] = 0
        self.volume_status_var.set(f"正在调整音量 ({db_change:+.1f} dB)...")

        def update_progress(value):
            self.volume_progress["value"] = value
            self.root.update_idletasks()

        def run():
            adjust_volume(input_file, output_file, db_change, update_progress)
            self.volume_btn.config(state="normal")
            self.volume_status_var.set("音量调整完成！")

        threading.Thread(target=run, daemon=True).start()

    def execute_extract_clip(self):
        """执行视频片段提取"""
        input_file = self.clip_input_var.get()
        output_file = self.clip_output_var.get()
        start_time = self.clip_start_var.get()
        end_time = self.clip_end_var.get()
        accurate_mode = (self.clip_mode_var.get() == "accurate")
        input_srt = self.clip_srt_input_var.get().strip()

        if not input_file or not output_file:
            messagebox.showerror("错误", "请选择输入和输出文件")
            return

        # 验证时间格式
        time_pattern = r'^\d{1,2}:\d{2}:\d{2}(\.\d{1,3})?$'
        if not re.match(time_pattern, start_time) or not re.match(time_pattern, end_time):
            messagebox.showerror("错误", "时间格式不正确，请使用 HH:MM:SS 或 HH:MM:SS.mmm 格式")
            return

        # 验证字幕文件（如果提供了）
        if input_srt and not os.path.isfile(input_srt):
            messagebox.showerror("错误", "指定的字幕文件不存在")
            return

        self.clip_btn.config(state="disabled")
        self.clip_progress["value"] = 0
        mode_text = "精确模式" if accurate_mode else "快速模式"
        self.clip_status_var.set(f"正在提取视频片段 ({mode_text})...")

        def update_progress(value):
            self.clip_progress["value"] = value
            self.root.update_idletasks()

        def run():
            extract_video_clip(input_file, output_file, start_time, end_time, update_progress, accurate_mode)
            
            # 如果提供了字幕文件，同时提取对应字幕
            srt_msg = ""
            if input_srt:
                # 自动生成输出字幕文件名（与输出视频同名，扩展名改为.srt）
                output_srt = os.path.splitext(output_file)[0] + '.srt'
                success, msg, count = extract_subtitle_clip(input_srt, output_srt, start_time, end_time)
                if success and count > 0:
                    srt_msg = f"\n字幕：{msg}，已保存到 {os.path.basename(output_srt)}"
                elif success:
                    srt_msg = f"\n字幕：{msg}"
                else:
                    srt_msg = f"\n字幕提取失败：{msg}"
            
            self.clip_btn.config(state="normal")
            self.clip_status_var.set(f"✓ 视频片段提取完成！({mode_text}){srt_msg}")

        threading.Thread(target=run, daemon=True).start()

    def execute_auto_split(self):
        """执行自动分割视频"""
        input_file = self.split_input_var.get()
        output_dir = self.split_output_dir_var.get()
        num_segments = self.split_segments_var.get()
        use_keyframes = self.split_keyframe_var.get()

        if not input_file or not output_dir:
            messagebox.showerror("错误", "请选择输入文件和输出目录")
            return

        if num_segments < 2:
            messagebox.showerror("错误", "分割段数至少为2段")
            return

        # 确保输出目录存在
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except:
                messagebox.showerror("错误", "无法创建输出目录")
                return

        self.split_btn.config(state="disabled")
        self.split_progress["value"] = 0
        mode_text = "关键帧对齐" if use_keyframes else "精确时间"
        self.split_status_var.set(f"正在分割视频为 {num_segments} 段 ({mode_text})...")

        def update_progress(value):
            self.split_progress["value"] = value
            self.root.update_idletasks()

        def run():
            success, message, output_files = auto_split_video(
                input_file, output_dir, num_segments, update_progress, use_keyframes
            )
            self.split_btn.config(state="normal")
            
            if success:
                result_text = f"✓ {message}\n生成了 {len(output_files)} 个文件：\n"
                for f in output_files:
                    result_text += f"  • {os.path.basename(f)}\n"
                self.split_status_var.set(f"✓ 分割完成！已生成 {len(output_files)} 个文件")
                messagebox.showinfo("成功", result_text)
            else:
                self.split_status_var.set(f"✗ 分割失败：{message}")
                messagebox.showerror("错误", message)

        threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoToolsGUI(root)
    root.mainloop()
