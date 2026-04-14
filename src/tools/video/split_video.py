from tools.base import ToolBase
import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, ttk
import ffmpeg
import subprocess
import json
from hub_logger import logger

def normalize_timestamp(raw_time):
    """规范化时间戳，支持 H:MM:SS、HH:MM:SS、MM:SS，并容错重复冒号。"""
    if not raw_time:
        return None

    # 兼容类似 0::01:00 这种输入
    candidate = re.sub(r':{2,}', ':', raw_time.strip())
    parts = candidate.split(':')

    if len(parts) not in (2, 3) or not all(part.isdigit() for part in parts):
        return None

    nums = [int(part) for part in parts]
    if len(nums) == 3:
        h, m, s = nums
        if m >= 60 or s >= 60:
            return None
        return f"{h}:{m:02d}:{s:02d}"

    m, s = nums
    if s >= 60:
        return None
    return f"{m}:{s:02d}"

def parse_timestamps_and_titles(file_path):
    """解析时间戳和标题"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    segments = []
    current_time = None
    current_title = None

    for line in lines:
        line = line.strip()
        # 匹配行首的时间串，再进行规范化校验
        time_match = re.match(r'^([0-9:]+)', line)
        if time_match:
            raw_time = time_match.group(1)
            normalized_time = normalize_timestamp(raw_time)
        else:
            normalized_time = None

        if normalized_time:
            if current_time is not None:
                # 保存上一段
                segments.append((current_time, current_title))
            current_time = normalized_time
            current_title = line[len(raw_time):].strip()
        # 跳过内容行（非时间戳行）

    # 添加最后一段
    if current_time and current_title:
        segments.append((current_time, current_title))

    return segments

def time_to_seconds(time_str):
    """将时间戳转换为秒"""
    normalized = normalize_timestamp(time_str)
    if not normalized:
        return 0

    parts = normalized.split(':')
    if len(parts) == 3:  # HH:MM:SS
        h, m, s = map(int, parts)
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:  # MM:SS
        m, s = map(int, parts)
        return m * 60 + s
    return 0

def get_closest_keyframe(video_path, target_time):
    """找到目标时间前最近的关键帧时间（秒）"""
    try:
        # 使用 ffprobe 获取所有关键帧的时间戳
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'packet=pts_time,flags',
            '-of', 'json',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        keyframes = [float(pkt['pts_time']) for pkt in data.get('packets', []) if 'K' in pkt.get('flags', '')]
        
        # 找到 <= target_time 的最大关键帧时间
        closest = max((t for t in keyframes if t <= target_time), default=0)
        print(f"目标时间 {target_time}s 的最近关键帧: {closest}s")
        return closest
    except Exception as e:
        print(f"警告：无法获取关键帧，使用原时间。错误：{e}")
        return target_time

def _next_subs_dir(video_path):
    """Return <video_dir>/subs, or subs1/subs2/... if already exists."""
    base = os.path.join(os.path.dirname(os.path.abspath(video_path)), "subs")
    if not os.path.exists(base):
        return base
    i = 1
    while os.path.exists(f"{base}{i}"):
        i += 1
    return f"{base}{i}"


def split_video(video_path, segments, output_dir, progress_cb=None):
    """Split video by timestamps - stream copy mode.

    progress_cb(current, total) is called after each segment completes.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    total = len(segments)
    for i, (start_time, title) in enumerate(segments, 1):
        target_start = time_to_seconds(start_time)
        start_seconds = get_closest_keyframe(video_path, target_start)

        duration = None
        if i < total:
            next_start_seconds = time_to_seconds(segments[i][0])
            duration = next_start_seconds - start_seconds

        safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
        output_file = os.path.join(output_dir, f"{i:03d}_{safe_title}.mp4")

        print(f"Splitting segment {i}/{total}: {start_time} - {title} (keyframe {start_seconds}s)")
        if progress_cb:
            progress_cb(i - 1, total)  # notify "starting segment i"

        try:
            stream = ffmpeg.input(video_path, ss=start_seconds)
            kwargs = dict(c="copy", avoid_negative_ts="make_zero", movflags="faststart", loglevel="error")
            if duration:
                stream = ffmpeg.output(stream, output_file, t=duration, **kwargs)
            else:
                stream = ffmpeg.output(stream, output_file, **kwargs)
            ffmpeg.run(stream, overwrite_output=True)
            print(f"Done: {output_file}")
        except ffmpeg.Error as e:
            stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
            print(f"Error splitting '{title}': {stderr}")

        if progress_cb:
            progress_cb(i, total)  # notify "segment i done"

class SplitVideoApp(ToolBase):
    def __init__(self, master, initial_file: str = None):
        self.master = master
        master.title("视频分段切割工具")
        master.geometry("680x360")
        master.resizable(False, False)

        # Video file
        tk.Label(master, text="视频文件:").grid(row=0, column=0, padx=10, pady=12, sticky="e")
        self.video_path_var = tk.StringVar()
        tk.Entry(master, textvariable=self.video_path_var, width=60).grid(row=0, column=1, sticky="w")
        tk.Button(master, text="浏览", command=self.select_video).grid(row=0, column=2, padx=10)

        # Segment description file
        tk.Label(master, text="分段描述文件:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.desc_path_var = tk.StringVar()
        tk.Entry(master, textvariable=self.desc_path_var, width=60).grid(row=1, column=1, sticky="w")
        tk.Button(master, text="浏览", command=self.select_desc).grid(row=1, column=2, padx=10)

        # Output directory
        tk.Label(master, text="输出目录:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.output_dir_var = tk.StringVar()
        tk.Entry(master, textvariable=self.output_dir_var, width=60).grid(row=2, column=1, sticky="w")
        tk.Button(master, text="浏览", command=self.select_output_dir).grid(row=2, column=2, padx=10)

        # Start button
        self._btn_start = tk.Button(master, text="开始切割", command=self.start_split, width=20)
        self._btn_start.grid(row=3, column=1, pady=16)

        # Progress bar
        self._progress = ttk.Progressbar(master, mode="determinate", maximum=100, length=500)
        self._progress.grid(row=4, column=0, columnspan=3, padx=10, sticky="ew")

        # Status label
        self.status_var = tk.StringVar()
        tk.Label(master, textvariable=self.status_var, fg="blue", wraplength=600).grid(
            row=5, column=0, columnspan=3, pady=6)

        if initial_file:
            self.video_path_var.set(initial_file)
            self.output_dir_var.set(_next_subs_dir(initial_file))

    def select_video(self):
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("Video files", "*.mp4 *.mkv *.avi"), ("All files", "*.*")]
        )
        if path:
            self.video_path_var.set(path)
            self.output_dir_var.set(_next_subs_dir(path))

    def select_desc(self):
        path = filedialog.askopenfilename(
            title="选择分段描述文件",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            self.desc_path_var.set(path)

    def select_output_dir(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_dir_var.set(path)

    def start_split(self):
        video_path = self.video_path_var.get()
        desc_path = self.desc_path_var.get()
        output_dir = self.output_dir_var.get()

        if not video_path or not os.path.exists(video_path):
            self.status_var.set("⚠ 请选择有效的视频文件")
            return
        if not desc_path or not os.path.exists(desc_path):
            self.status_var.set("⚠ 请选择有效的分段描述文件")
            return
        if not output_dir:
            self.status_var.set("⚠ 请选择输出目录")
            return

        segments = parse_timestamps_and_titles(desc_path)
        if not segments:
            self.status_var.set("⚠ 未找到有效的时间戳和标题")
            return

        total = len(segments)
        self.status_var.set(f"共 {total} 段，准备开始...")
        self._progress["value"] = 0
        self._btn_start.config(state="disabled")
        self.set_busy()

        def _progress_cb(done, total_):
            pct = int(done / total_ * 100)
            def _update():
                self._progress["value"] = pct
                if done < total_:
                    self.status_var.set(f"正在分割第 {done + 1}/{total_} 段...")
                else:
                    self.status_var.set(f"✓ 全部 {total_} 段切割完成！→ {output_dir}")
            self.master.after(0, _update)

        def _run():
            try:
                split_video(video_path, segments, output_dir, progress_cb=_progress_cb)
                logger.info(f"Split complete: {len(segments)} segments ({os.path.basename(video_path)}) → {output_dir}")
                self.set_done()
            except Exception as e:
                self.master.after(0, lambda: self.status_var.set(f"✗ 切割失败: {e}"))
                self.set_error(f"视频切割失败: {e}")
            finally:
                self.master.after(0, lambda: self._btn_start.config(state="normal"))

        threading.Thread(target=_run, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = SplitVideoApp(root)
    root.mainloop()