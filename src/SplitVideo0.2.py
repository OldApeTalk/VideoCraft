import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import ffmpeg
import subprocess
import json

def parse_timestamps_and_titles(file_path):
    """解析时间戳和标题"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    segments = []
    current_time = None
    current_title = None

    for line in lines:
        line = line.strip()
        # 匹配时间戳格式 (HH:MM:SS 或 MM:SS)
        time_match = re.match(r'(\d{2}:\d{2}:\d{2}|\d{2}:\d{2})', line)
        if time_match:
            if current_time is not None:
                # 保存上一段
                segments.append((current_time, current_title))
            current_time = time_match.group(0)
            current_title = line[len(current_time):].strip()
        # 跳过内容行（非时间戳行）

    # 添加最后一段
    if current_time and current_title:
        segments.append((current_time, current_title))

    return segments

def time_to_seconds(time_str):
    """将时间戳转换为秒"""
    parts = time_str.split(':')
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

def split_video(video_path, segments, output_dir, status_var=None):
    """根据时间戳切分视频 - 快速拷贝模式"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, (start_time, title) in enumerate(segments, 1):
        target_start = time_to_seconds(start_time)
        # 找到最近关键帧以避免播放问题
        start_seconds = get_closest_keyframe(video_path, target_start)
        
        duration = None
        if i < len(segments):
            next_start_seconds = time_to_seconds(segments[i][0])
            duration = next_start_seconds - start_seconds  # 调整 duration 以匹配新 start

        safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
        output_file = os.path.join(output_dir, f"{i:03d}_{safe_title}.mp4")

        msg = f"正在切分：{start_time} - {title} (从关键帧 {start_seconds}s 开始)"
        print(msg)
        if status_var is not None:
            status_var.set(msg)
        try:
            stream = ffmpeg.input(video_path, ss=start_seconds)
            if duration:
                stream = ffmpeg.output(
                    stream, output_file, t=duration,
                    c='copy',  # 快速拷贝
                    avoid_negative_ts='make_zero',  # 修复时间戳
                    movflags='faststart',  # 优化 MP4 for X/ web
                    loglevel='info'
                )
            else:
                stream = ffmpeg.output(
                    stream, output_file,
                    c='copy',
                    avoid_negative_ts='make_zero',
                    movflags='faststart',
                    loglevel='info'
                )
            ffmpeg.run(stream)
            print(f"完成：{output_file}")
        except ffmpeg.Error as e:
            print(f"错误：切分失败 - {title}，原因：{e.stderr.decode()}")

class SplitVideoApp:
    def __init__(self, master):
        self.master = master
        master.title("视频分段切割工具")
        master.geometry("650x300")
        master.resizable(False, False)

        # 视频文件
        tk.Label(master, text="选择视频文件:").grid(row=0, column=0, padx=10, pady=15, sticky="e")
        self.video_path_var = tk.StringVar()
        tk.Entry(master, textvariable=self.video_path_var, width=60).grid(row=0, column=1, sticky="w")
        tk.Button(master, text="浏览", command=self.select_video).grid(row=0, column=2, padx=10)

        # 分段描述文件
        tk.Label(master, text="分段描述文件:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.desc_path_var = tk.StringVar()
        tk.Entry(master, textvariable=self.desc_path_var, width=60).grid(row=1, column=1, sticky="w")
        tk.Button(master, text="浏览", command=self.select_desc).grid(row=1, column=2, padx=10)

        # 输出目录
        tk.Label(master, text="输出目录:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.output_dir_var = tk.StringVar()
        tk.Entry(master, textvariable=self.output_dir_var, width=60).grid(row=2, column=1, sticky="w")
        tk.Button(master, text="浏览", command=self.select_output_dir).grid(row=2, column=2, padx=10)

        # 状态栏
        self.status_var = tk.StringVar()
        tk.Label(master, textvariable=self.status_var, fg="blue").grid(row=4, column=0, columnspan=3, pady=10)

        # 开始切割按钮
        tk.Button(master, text="开始切割", command=self.start_split, width=20).grid(row=3, column=1, pady=20)

    def select_video(self):
        path = filedialog.askopenfilename(title="选择视频文件", filetypes=[("Video files", "*.mp4 *.mkv *.avi"), ("All files", "*.*")])
        if path:
            self.video_path_var.set(path)

    def select_desc(self):
        path = filedialog.askopenfilename(title="选择分段描述文件", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
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
            messagebox.showerror("错误", "请选择有效的视频文件")
            return
        if not desc_path or not os.path.exists(desc_path):
            messagebox.showerror("错误", "请选择有效的分段描述文件")
            return
        if not output_dir:
            messagebox.showerror("错误", "请选择输出目录")
            return
        segments = parse_timestamps_and_titles(desc_path)
        if not segments:
            messagebox.showerror("错误", "未找到有效的时间戳和标题")
            return
        self.status_var.set("开始切割...")
        self.master.update()
        split_video(video_path, segments, output_dir, self.status_var)
        self.status_var.set("全部切割完成！")
        messagebox.showinfo("完成", "视频分割已全部完成！")

if __name__ == "__main__":
    root = tk.Tk()
    app = SplitVideoApp(root)
    root.mainloop()