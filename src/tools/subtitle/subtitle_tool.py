"""
合并字幕分割和添加功能的工具
将 SplitSubtitles.py 的字符宽度剪裁功能合并到 AddSubTitleToMovieWithFFMpeg.py 中，
提供统一的界面来处理字幕分割和视频字幕烧录。
"""

from tools.base import ToolBase
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser, ttk
import os
import sys
import subprocess
import threading
import time
import re
import json
import srt
from datetime import timedelta, datetime
try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None  # fallback to plain Entry
from hub_logger import logger


# ── 纯工具函数（从 core 导入）───────────────────────────────────────────────

from core.subtitle_ops import (
    split_subtitle,
    process_srt_split,
    escape_ffmpeg_path,
    hex_color_to_ass,
    hex_color_to_drawtext,
)


def _infer_lang_tag(srt_path: str) -> str:
    """从 SRT 文件名末尾推断语言码（如 video_en.srt → 'en'），推断失败返回 'sub'。"""
    if not srt_path:
        return "sub"
    base = os.path.splitext(os.path.basename(srt_path))[0]
    parts = base.rsplit("_", 1)
    if len(parts) == 2 and 1 <= len(parts[1]) <= 5 and parts[1].replace("-", "").isalpha():
        return parts[1]
    return "sub"


def _build_sub_output_path(video_path: str, sub1_path: str, sub2_path: str = None) -> str:
    """根据视频路径和字幕路径生成烧录后输出文件名（如 video_sub_zh+en.mp4）。"""
    base = os.path.splitext(video_path)[0]
    tag1 = _infer_lang_tag(sub1_path) if sub1_path else None
    tag2 = _infer_lang_tag(sub2_path) if sub2_path else None
    if tag1 and tag2:
        return f"{base}_sub_{tag1}+{tag2}.mp4"
    elif tag1:
        return f"{base}_sub_{tag1}.mp4"
    elif tag2:
        return f"{base}_sub_{tag2}.mp4"
    return f"{base}_sub.mp4"


def get_video_resolution(video_path):
    """获取视频分辨率"""
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
               '-show_entries', 'stream=width,height', '-of', 'csv=p=0', video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            width, height = map(int, result.stdout.strip().split(','))
            return width, height
    except Exception:
        pass
    return None, None


# ── 主界面 class ─────────────────────────────────────────────────────────────

class SubtitleToolApp(ToolBase):
    """双语字幕烧录工具 — Toplevel 内嵌版。"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("双语字幕工具（分割与烧录）")
        master.geometry("900x650")

        # 状态变量
        self.video_duration = 0.0
        self.processing = False

        # Tk 变量
        self.watermark_text_var          = tk.StringVar(value="字幕By老猿@OldApeTalk")
        self.watermark_txt_alpha_var     = tk.DoubleVar(value=60.0)   # 文字透明度
        self.watermark_color_var         = tk.StringVar(value="#00ffff")
        self.watermark_fontsize_var      = tk.IntVar(value=48)
        self.watermark_show_var          = tk.BooleanVar(value=True)
        self.watermark_show_date_var     = tk.BooleanVar(value=False)
        self.watermark_date_var          = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.watermark_date_color_var    = tk.StringVar(value="#505050")
        self.watermark_date_fontsize_var = tk.IntVar(value=36)
        self.watermark_date_alpha_var    = tk.DoubleVar(value=80.0)   # 日期透明度
        # 图片/文字水印（单选）: "image" | "text"
        self.watermark_type_var          = tk.StringVar(value="image")
        self.watermark_img_path_var      = tk.StringVar(value=self._default_watermark_path())
        self.watermark_img_scale_var     = tk.DoubleVar(value=0.25)
        self.watermark_img_alpha_var     = tk.DoubleVar(value=100.0)  # 图片透明度

        self.sub1_fontsize_var  = tk.IntVar(value=24)
        self.sub1_color_var     = tk.StringVar(value="#FFFF00")
        self.sub1_show_var      = tk.BooleanVar(value=True)
        self.sub2_fontsize_var  = tk.IntVar(value=24)
        self.sub2_color_var     = tk.StringVar(value="#FFFFFF")
        self.sub2_show_var      = tk.BooleanVar(value=True)

        self.split_sub1_var     = tk.BooleanVar(value=True)
        self.sub1_max_chars_var = tk.IntVar(value=20)
        self.sub1_is_chinese_var = tk.BooleanVar(value=True)
        self.split_sub2_var     = tk.BooleanVar(value=True)
        self.sub2_max_chars_var = tk.IntVar(value=50)
        self.sub2_is_chinese_var = tk.BooleanVar(value=False)

        self.orientation_var    = tk.StringVar(value="horizontal")
        self.encode_preset_var  = tk.StringVar(value="veryfast")

        self._build_ui()
        self._update_split_settings()

        if initial_file and os.path.exists(initial_file):
            ext = os.path.splitext(initial_file)[1].lower()
            if ext == ".srt":
                self.entry_sub1.delete(0, tk.END)
                self.entry_sub1.insert(0, initial_file)
            elif ext in (".mp4", ".mkv", ".avi", ".mov"):
                self.entry_video.delete(0, tk.END)
                self.entry_video.insert(0, initial_file)

    def _build_ui(self):
        root = self.master

        # 视频文件
        tk.Label(root, text="视频文件:").grid(row=0, column=0, padx=10, pady=15, sticky="e")
        self.entry_video = tk.Entry(root, width=55)
        self.entry_video.grid(row=0, column=1, padx=5)
        tk.Button(root, text="浏览", command=self._select_video).grid(row=0, column=2, padx=10)

        # 屏幕方向设置
        frame_orientation = tk.LabelFrame(root, text="屏幕方向", padx=10, pady=5)
        frame_orientation.grid(row=1, column=0, columnspan=3, padx=15, pady=5, sticky="we")

        tk.Radiobutton(frame_orientation, text="横屏", variable=self.orientation_var,
                       value="horizontal", command=self._update_split_settings).grid(row=0, column=0, padx=20)
        tk.Radiobutton(frame_orientation, text="竖屏", variable=self.orientation_var,
                       value="vertical", command=self._update_split_settings).grid(row=0, column=1, padx=20)
        tk.Radiobutton(frame_orientation, text="方形", variable=self.orientation_var,
                       value="square", command=self._update_split_settings).grid(row=0, column=2, padx=20)

        tk.Label(frame_orientation, text="  |  编码速度:").grid(row=0, column=3, padx=(40, 5), sticky="e")
        encode_preset_combo = ttk.Combobox(
            frame_orientation, textvariable=self.encode_preset_var,
            values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"],
            width=12, state="readonly")
        encode_preset_combo.grid(row=0, column=4, padx=5)
        tk.Label(frame_orientation, text="(高分辨率建议: veryfast或更快)",
                 font=("Arial", 8), fg="gray").grid(row=0, column=5, padx=5)

        # 字幕1（中文）
        frame_sub1 = tk.LabelFrame(root, text="中文字幕（底部，之上）", padx=5, pady=5)
        frame_sub1.grid(row=2, column=0, columnspan=3, padx=10, pady=5, sticky="we")
        self.entry_sub1 = tk.Entry(frame_sub1, width=35)
        self.entry_sub1.grid(row=0, column=0, padx=5)
        tk.Button(frame_sub1, text="浏览", command=self._select_subtitle1).grid(row=0, column=1, padx=5)
        tk.Label(frame_sub1, text="字号:").grid(row=0, column=2, padx=2)
        tk.Spinbox(frame_sub1, from_=10, to=60, width=4, textvariable=self.sub1_fontsize_var).grid(row=0, column=3, padx=2)
        tk.Label(frame_sub1, text="颜色:").grid(row=0, column=4, padx=2)
        tk.Entry(frame_sub1, width=8, textvariable=self.sub1_color_var).grid(row=0, column=5, padx=2)
        tk.Button(frame_sub1, text="选择", command=self._choose_sub1_color).grid(row=0, column=6, padx=2)
        tk.Checkbutton(frame_sub1, text="显示", variable=self.sub1_show_var).grid(row=0, column=7, padx=5)

        tk.Checkbutton(frame_sub1, text="分割字幕", variable=self.split_sub1_var).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        tk.Label(frame_sub1, text="最大字符:").grid(row=1, column=1, padx=2)
        tk.Spinbox(frame_sub1, from_=10, to=100, width=4, textvariable=self.sub1_max_chars_var).grid(row=1, column=2, padx=2)
        tk.Checkbutton(frame_sub1, text="中文", variable=self.sub1_is_chinese_var).grid(row=1, column=3, padx=5)

        # 字幕2（英文）
        frame_sub2 = tk.LabelFrame(root, text="英文字幕（底部，最下方）", padx=5, pady=5)
        frame_sub2.grid(row=3, column=0, columnspan=3, padx=10, pady=5, sticky="we")
        self.entry_sub2 = tk.Entry(frame_sub2, width=35)
        self.entry_sub2.grid(row=0, column=0, padx=5)
        tk.Button(frame_sub2, text="浏览", command=self._select_subtitle2).grid(row=0, column=1, padx=5)
        tk.Label(frame_sub2, text="字号:").grid(row=0, column=2, padx=2)
        tk.Spinbox(frame_sub2, from_=10, to=60, width=4, textvariable=self.sub2_fontsize_var).grid(row=0, column=3, padx=2)
        tk.Label(frame_sub2, text="颜色:").grid(row=0, column=4, padx=2)
        tk.Entry(frame_sub2, width=8, textvariable=self.sub2_color_var).grid(row=0, column=5, padx=2)
        tk.Button(frame_sub2, text="选择", command=self._choose_sub2_color).grid(row=0, column=6, padx=2)
        tk.Checkbutton(frame_sub2, text="显示", variable=self.sub2_show_var).grid(row=0, column=7, padx=5)

        tk.Checkbutton(frame_sub2, text="分割字幕", variable=self.split_sub2_var).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        tk.Label(frame_sub2, text="最大字符:").grid(row=1, column=1, padx=2)
        tk.Spinbox(frame_sub2, from_=10, to=100, width=4, textvariable=self.sub2_max_chars_var).grid(row=1, column=2, padx=2)
        tk.Checkbutton(frame_sub2, text="中文", variable=self.sub2_is_chinese_var).grid(row=1, column=3, padx=5)

        # 水印设置
        frame_watermark = tk.LabelFrame(root, text="水印设置（右上角）", padx=10, pady=5)
        frame_watermark.grid(row=4, column=0, columnspan=3, padx=15, pady=5, sticky="we")

        # Row 0：图片水印（单选）
        tk.Radiobutton(frame_watermark, text="图片水印",
                       variable=self.watermark_type_var, value="image").grid(row=0, column=0, sticky="e")
        wm_img_files = self._scan_watermark_images()
        wm_img_names = [os.path.basename(f) for f in wm_img_files]
        self._wm_img_combo = ttk.Combobox(frame_watermark, values=wm_img_names, width=16, state="readonly")
        cur_name = os.path.basename(self.watermark_img_path_var.get())
        if cur_name in wm_img_names:
            self._wm_img_combo.set(cur_name)
        elif wm_img_names:
            self._wm_img_combo.set(wm_img_names[0])
        self._wm_img_combo.bind("<<ComboboxSelected>>", self._on_wm_img_selected)
        self._wm_img_combo.grid(row=0, column=1, padx=4)
        tk.Button(frame_watermark, text="浏览", command=self._select_watermark_image).grid(row=0, column=2, padx=3)
        tk.Label(frame_watermark, text="比例:").grid(row=0, column=3, sticky="e")
        tk.Spinbox(frame_watermark, from_=0.05, to=0.5, increment=0.05, width=5, format="%.2f",
                   textvariable=self.watermark_img_scale_var).grid(row=0, column=4, padx=2)
        tk.Label(frame_watermark, text="透明度(%):").grid(row=0, column=5, sticky="e")
        tk.Scale(frame_watermark, from_=0, to=100, orient=tk.HORIZONTAL,
                 variable=self.watermark_img_alpha_var, length=80).grid(row=0, column=6, padx=3)
        tk.Checkbutton(frame_watermark, text="显示",
                       variable=self.watermark_show_var).grid(row=0, column=7, padx=5)

        # Row 1：文字水印（单选）
        tk.Radiobutton(frame_watermark, text="文字水印",
                       variable=self.watermark_type_var, value="text").grid(row=1, column=0, sticky="e")
        ttk.Combobox(frame_watermark, textvariable=self.watermark_text_var, width=20,
                     values=["字幕By老猿@OldApeTalk", "字幕制作By 老猿",
                             "@VideoCraftNews"]).grid(row=1, column=1, padx=4)
        tk.Label(frame_watermark, text="字号:").grid(row=1, column=2, sticky="e")
        tk.Spinbox(frame_watermark, from_=10, to=100, width=4,
                   textvariable=self.watermark_fontsize_var).grid(row=1, column=3, padx=2)
        tk.Label(frame_watermark, text="颜色:").grid(row=1, column=4, sticky="e")
        tk.Entry(frame_watermark, textvariable=self.watermark_color_var, width=9).grid(row=1, column=5, padx=2)
        tk.Button(frame_watermark, text="选择",
                  command=self._choose_watermark_color).grid(row=1, column=6, padx=2)
        tk.Label(frame_watermark, text="透明度(%):").grid(row=1, column=7, sticky="e")
        tk.Scale(frame_watermark, from_=0, to=100, orient=tk.HORIZONTAL,
                 variable=self.watermark_txt_alpha_var, length=80).grid(row=1, column=8, padx=3)

        # Row 2：日期（独立字号 + 颜色 + 透明度）
        tk.Checkbutton(frame_watermark, text="显示日期",
                       variable=self.watermark_show_date_var).grid(row=2, column=0, sticky="e", padx=5)
        date_widget_cls = DateEntry if DateEntry else tk.Entry
        date_kwargs = (dict(textvariable=self.watermark_date_var, width=12,
                            background='darkblue', foreground='white', borderwidth=2,
                            date_pattern='yyyy-mm-dd')
                       if DateEntry else
                       dict(textvariable=self.watermark_date_var, width=12))
        date_widget_cls(frame_watermark, **date_kwargs).grid(row=2, column=1, sticky="w", padx=4)
        tk.Label(frame_watermark, text="字号:").grid(row=2, column=2, sticky="e")
        tk.Spinbox(frame_watermark, from_=10, to=100, width=4,
                   textvariable=self.watermark_date_fontsize_var).grid(row=2, column=3, padx=2)
        tk.Label(frame_watermark, text="颜色:").grid(row=2, column=4, sticky="e")
        tk.Entry(frame_watermark, textvariable=self.watermark_date_color_var, width=9).grid(row=2, column=5, padx=2)
        tk.Button(frame_watermark, text="选择",
                  command=self._choose_date_color).grid(row=2, column=6, padx=2)
        tk.Label(frame_watermark, text="透明度(%):").grid(row=2, column=7, sticky="e")
        tk.Scale(frame_watermark, from_=0, to=100, orient=tk.HORIZONTAL,
                 variable=self.watermark_date_alpha_var, length=80).grid(row=2, column=8, padx=3)

        # 进度
        frame_progress = tk.Frame(root)
        frame_progress.grid(row=5, column=0, columnspan=3, pady=10)
        self.progress_bar = ttk.Progressbar(frame_progress, orient=tk.HORIZONTAL,
                                            length=400, mode='determinate')
        self.progress_bar.pack(pady=5)
        self.label_duration  = tk.Label(frame_progress, text="视频时长: 未知")
        self.label_duration.pack()
        self.label_elapsed   = tk.Label(frame_progress, text="已用时间: 00:00:00")
        self.label_elapsed.pack()
        self.label_remaining = tk.Label(frame_progress, text="剩余时间: 未知")
        self.label_remaining.pack()

        # 开始按钮
        self.btn_merge = tk.Button(root, text="开始烧录双语字幕",
                                   width=25, command=self._merge_videos)
        self.btn_merge.grid(row=6, column=1, pady=25)

    # ── 图片水印辅助 ────────────────────────────────────────────────────────

    @staticmethod
    def _project_root():
        """返回项目根目录（Logo/ 所在目录）。"""
        # __file__ = .../src/tools/subtitle/subtitle_tool.py → 上移4级
        return os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))

    def _scan_watermark_images(self):
        """扫描 Logo/ 目录下所有 WaterMark*.png，返回绝对路径列表。"""
        import glob as _glob
        logo_dir = os.path.join(self._project_root(), "Logo")
        return sorted(_glob.glob(os.path.join(logo_dir, "WaterMark*.png")))

    def _default_watermark_path(self):
        """返回默认水印图片路径（优先 WaterMark1.png，否则取第一个）。"""
        files = self._scan_watermark_images()
        preferred = os.path.join(self._project_root(), "Logo", "WaterMark1.png")
        if preferred in files:
            return preferred
        return files[0] if files else ""

    def _select_watermark_image(self):
        path = filedialog.askopenfilename(
            title="选择水印图片",
            filetypes=[("PNG 图片", "*.png"), ("所有文件", "*.*")]
        )
        if path:
            self.watermark_img_path_var.set(path)
            # 同步刷新下拉列表
            self._refresh_wm_img_combo()

    def _refresh_wm_img_combo(self):
        """刷新水印图片 Combobox 列表，并尝试匹配当前路径。"""
        files = self._scan_watermark_images()
        names = [os.path.basename(f) for f in files]
        self._wm_img_combo['values'] = names
        cur = self.watermark_img_path_var.get()
        cur_name = os.path.basename(cur)
        if cur_name in names:
            self._wm_img_combo.set(cur_name)

    def _on_wm_img_selected(self, event=None):
        """Combobox 选中时更新完整路径。"""
        name = self._wm_img_combo.get()
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.watermark_img_path_var.set(os.path.join(base, "Logo", name))

    # ── 文件选择 ────────────────────────────────────────────────────────────

    def _select_video(self):
        file_path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv"), ("所有文件", "*.*")]
        )
        if not file_path:
            return
        self.entry_video.delete(0, tk.END)
        self.entry_video.insert(0, file_path)
        # 获取视频时长
        try:
            subprocess.run(['ffprobe', '-version'], capture_output=True, check=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            messagebox.showerror("错误", "未找到ffprobe。请确保已安装FFmpeg并将其添加到系统PATH中。")
            self.video_duration = 0.0
            self.label_duration.config(text="视频时长: 未知 (未安装FFmpeg)")
            return

        try:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                   '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                cmd2 = ['ffprobe', '-i', file_path, '-v', 'quiet',
                        '-print_format', 'json', '-show_format']
                result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=10)
                if result2.returncode == 0:
                    duration_str = json.loads(result2.stdout)['format']['duration']
                else:
                    raise Exception(f"ffprobe命令失败: {result.stderr.strip()}")
            else:
                duration_str = result.stdout.strip()
            self.video_duration = float(duration_str)
            self.label_duration.config(text=f"视频时长: {time.strftime('%H:%M:%S', time.gmtime(self.video_duration))}")
        except subprocess.TimeoutExpired:
            self.video_duration = 0.0
            self.label_duration.config(text="视频时长: 未知 (超时)")
            messagebox.showwarning("警告", "获取视频时长超时。")
        except Exception as e:
            self.video_duration = 0.0
            self.label_duration.config(text="视频时长: 未知")
            messagebox.showwarning("警告", f"获取视频时长失败: {e}\n您可以继续使用，但进度条可能不准确。")

    def _select_subtitle1(self):
        path = filedialog.askopenfilename(
            title="选择中文字幕文件（底部，位于英文字幕之上）",
            filetypes=[("SRT 字幕文件", "*.srt"), ("所有文件", "*.*")]
        )
        if path:
            self.entry_sub1.delete(0, tk.END)
            self.entry_sub1.insert(0, path)

    def _select_subtitle2(self):
        path = filedialog.askopenfilename(
            title="选择英文字幕文件（底部，最下方）",
            filetypes=[("SRT 字幕文件", "*.srt"), ("所有文件", "*.*")]
        )
        if path:
            self.entry_sub2.delete(0, tk.END)
            self.entry_sub2.insert(0, path)

    # ── 颜色选择 ────────────────────────────────────────────────────────────

    def _choose_watermark_color(self):
        color = colorchooser.askcolor(title="选择水印颜色")
        if color and color[1]:
            self.watermark_color_var.set(color[1])

    def _choose_date_color(self):
        color = colorchooser.askcolor(title="选择日期颜色")
        if color and color[1]:
            self.watermark_date_color_var.set(color[1])

    def _choose_sub1_color(self):
        color = colorchooser.askcolor(title="选择中文字幕颜色")
        if color and color[1]:
            self.sub1_color_var.set(color[1])

    def _choose_sub2_color(self):
        color = colorchooser.askcolor(title="选择英文字幕颜色")
        if color and color[1]:
            self.sub2_color_var.set(color[1])

    # ── 辅助 ────────────────────────────────────────────────────────────────

    def _update_split_settings(self):
        ori = self.orientation_var.get()
        if ori == "horizontal":
            self.sub1_max_chars_var.set(20)
            self.sub2_max_chars_var.set(50)
            self.sub1_fontsize_var.set(24)
            self.sub2_fontsize_var.set(24)
        elif ori == "square":
            self.sub1_max_chars_var.set(10)
            self.sub2_max_chars_var.set(25)
            self.sub1_fontsize_var.set(20)
            self.sub2_fontsize_var.set(16)
        else:  # vertical
            self.sub1_max_chars_var.set(10)
            self.sub2_max_chars_var.set(25)
            self.sub1_fontsize_var.set(14)
            self.sub2_fontsize_var.set(12)

    def _update_progress(self, progress, elapsed, remaining):
        self.progress_bar['value'] = progress
        self.label_elapsed.config(text=f"已用时间: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")
        if remaining > 0:
            self.label_remaining.config(text=f"剩余时间: {time.strftime('%H:%M:%S', time.gmtime(remaining))}")
        else:
            self.label_remaining.config(text="剩余时间: 计算中...")

    # ── 主流程 ──────────────────────────────────────────────────────────────

    def _merge_videos(self):
        if self.processing:
            messagebox.showwarning("警告", "正在处理中，请等待完成。")
            return

        video_path = self.entry_video.get()
        sub1_path  = self.entry_sub1.get()
        sub2_path  = self.entry_sub2.get()

        show_sub1 = self.sub1_show_var.get()
        show_sub2 = self.sub2_show_var.get()

        if not video_path:
            messagebox.showerror("错误", "请选择视频文件。")
            return
        if not os.path.exists(video_path):
            messagebox.showerror("错误", f"视频文件不存在: {video_path}")
            return
        if show_sub1 and not sub1_path:
            messagebox.showerror("错误", "已勾选显示字幕1，请选择对应 SRT 文件。")
            return
        if show_sub2 and not sub2_path:
            messagebox.showerror("错误", "已勾选显示字幕2，请选择对应 SRT 文件。")
            return
        if not show_sub1 and not show_sub2:
            messagebox.showerror("错误", "至少需要勾选一条字幕轨道。")
            return
        for p, name in ([(sub1_path, "字幕1")] if show_sub1 else []) + \
                       ([(sub2_path, "字幕2")] if show_sub2 else []):
            if not os.path.exists(p):
                messagebox.showerror("错误", f"{name}文件不存在: {p}")
                return

        # 字幕分割
        temp_sub1_path = sub1_path
        temp_sub2_path = sub2_path
        try:
            if show_sub1 and self.split_sub1_var.get():
                subs1 = process_srt_split(sub1_path, self.sub1_max_chars_var.get(),
                                          self.sub1_is_chinese_var.get())
                temp_sub1_path = sub1_path.replace('.srt', '_split.srt')
                with open(temp_sub1_path, 'w', encoding='utf-8') as f:
                    f.write(srt.compose(subs1))
            if show_sub2 and self.split_sub2_var.get():
                subs2 = process_srt_split(sub2_path, self.sub2_max_chars_var.get(),
                                          self.sub2_is_chinese_var.get())
                temp_sub2_path = sub2_path.replace('.srt', '_split.srt')
                with open(temp_sub2_path, 'w', encoding='utf-8') as f:
                    f.write(srt.compose(subs2))
        except Exception as e:
            messagebox.showerror("字幕分割错误", str(e))
            return

        # 路径处理
        video_path_abs = os.path.abspath(video_path)
        sub1_path_ff   = escape_ffmpeg_path(temp_sub1_path) if show_sub1 else None
        sub2_path_ff   = escape_ffmpeg_path(temp_sub2_path) if show_sub2 else None

        # 字幕样式
        font1 = "Microsoft YaHei"
        fontsize1 = self.sub1_fontsize_var.get()
        color1    = hex_color_to_ass(self.sub1_color_var.get())
        style1 = (f"Fontname={font1},Fontsize={fontsize1},PrimaryColour={color1},"
                  f"OutlineColour=&H00000000&,BorderStyle=1,Outline=2,Shadow=0,"
                  f"Bold=1,Alignment=2,MarginV=100")

        font2 = "Microsoft YaHei"
        fontsize2 = self.sub2_fontsize_var.get()
        color2    = hex_color_to_ass(self.sub2_color_var.get())
        style2 = (f"Fontname={font2},Fontsize={fontsize2},PrimaryColour={color2},"
                  f"OutlineColour=&H00000000&,BorderStyle=1,Outline=2,Shadow=0,"
                  f"Bold=0,Alignment=2,MarginV=50")

        output_path = _build_sub_output_path(
            video_path_abs,
            sub1_path if show_sub1 else None,
            sub2_path if show_sub2 else None,
        )

        width, height = get_video_resolution(video_path_abs)

        # 水印
        show_watermark           = self.watermark_show_var.get()
        wm_type                  = self.watermark_type_var.get()
        use_img_wm               = show_watermark and wm_type == "image"
        use_txt_wm               = show_watermark and wm_type == "text"
        show_date                = self.watermark_show_date_var.get()
        watermark_text           = self.watermark_text_var.get()
        watermark_color          = self.watermark_color_var.get()
        watermark_fontsize_base  = self.watermark_fontsize_var.get()
        watermark_ff_color       = hex_color_to_drawtext(watermark_color)
        txt_alpha                = round(self.watermark_txt_alpha_var.get() / 100, 2)
        img_alpha                = round(self.watermark_img_alpha_var.get() / 100, 2)
        watermark_fontsize       = int((height / 1080) * watermark_fontsize_base) if height else watermark_fontsize_base
        img_path                 = self.watermark_img_path_var.get()
        img_scale                = self.watermark_img_scale_var.get()
        img_exists               = use_img_wm and os.path.exists(img_path)

        date_ff_color            = hex_color_to_drawtext(self.watermark_date_color_var.get())
        date_fontsize_base       = self.watermark_date_fontsize_var.get()
        date_fontsize            = int((height / 1080) * date_fontsize_base) if height else date_fontsize_base
        date_alpha               = round(self.watermark_date_alpha_var.get() / 100, 2)

        # 文字水印 drawtext 片段
        def _txt_drawtext(y_expr="30"):
            return (f"drawtext=text='{watermark_text}':"
                    f"fontcolor={watermark_ff_color}@{txt_alpha}:"
                    f"fontsize={watermark_fontsize}:font='Microsoft YaHei':"
                    f"x=w-tw-30:y={y_expr}:borderw=2:bordercolor=black")

        # 日期 drawtext 片段（独立颜色/字号/透明度）
        def _date_drawtext(y_val):
            return (f"drawtext=text='{self.watermark_date_var.get()}':"
                    f"fontcolor={date_ff_color}@{date_alpha}:"
                    f"fontsize={date_fontsize}:font='Microsoft YaHei':"
                    f"x=w-tw-30:y={y_val}:borderw=2:bordercolor=black")

        use_filter_complex = img_exists

        # 精确计算日期 y 坐标（在主水印下方）
        if use_filter_complex:
            # 图片模式：用 PIL 读取图片实际尺寸计算缩放后高度
            try:
                from PIL import Image as _PILImg
                with _PILImg.open(img_path) as _im:
                    _orig_w, _orig_h = _im.size
                img_w_px = int((width or 1920) * img_scale)
                img_h_px = int(img_w_px * _orig_h / _orig_w)
            except Exception:
                img_w_px = int((width or 1920) * img_scale)
                img_h_px = img_w_px  # 无法读取时假设正方形
            date_y = 30 + img_h_px + 8
        else:
            # 文字模式：基于水印文字字号
            img_w_px = int((width or 1920) * img_scale)
            date_y = 30 + watermark_fontsize + 8

        if use_filter_complex:
            # ── filter_complex 路径（有图片水印）────────────────────────────
            img_path_ff = img_path.replace("\\", "/").replace(":", "\\:")
            fc_parts = []
            cur = "[0:v]"

            # 字幕滤镜
            if show_sub2 and sub2_path_ff:
                fc_parts.append(f"{cur}subtitles=filename='{sub2_path_ff}':force_style='{style2}'[s2]")
                cur = "[s2]"
            if show_sub1 and sub1_path_ff:
                fc_parts.append(f"{cur}subtitles=filename='{sub1_path_ff}':force_style='{style1}'[s1]")
                cur = "[s1]"

            # 图片水印源（含独立透明度）
            fc_parts.append(
                f"movie='{img_path_ff}',scale={img_w_px}:-1,"
                f"format=rgba,colorchannelmixer=aa={img_alpha}[wm]"
            )

            # overlay 链：图片叠加，日期独立追加
            overlay_chain = f"{cur}[wm]overlay=W-w-30:30"
            if show_date:
                overlay_chain += "," + _date_drawtext(date_y)
            overlay_chain += "[out]"
            fc_parts.append(overlay_chain)

            filter_complex = ";".join(fc_parts)
            vf = None
        else:
            # ── -vf 路径（文字水印或无水印）─────────────────────────────────
            filter_complex = None
            vf_filters = []
            if show_sub2 and sub2_path_ff:
                vf_filters.append(f"subtitles=filename='{sub2_path_ff}':force_style='{style2}'")
            if show_sub1 and sub1_path_ff:
                vf_filters.append(f"subtitles=filename='{sub1_path_ff}':force_style='{style1}'")
            if use_txt_wm and watermark_text.strip():
                vf_filters.append(_txt_drawtext("30"))
            if show_date:
                vf_filters.append(_date_drawtext(date_y))
            vf = ",".join(vf_filters)

        # 缓冲区
        if width and height:
            pixels = width * height
            if pixels >= 3840 * 2160:   bufsize = maxrate = '150M'
            elif pixels >= 2560 * 1440: bufsize = maxrate = '80M'
            elif pixels >= 1920 * 1080: bufsize = maxrate = '50M'
            else:                        bufsize = maxrate = '30M'
        else:
            bufsize = maxrate = '100M'

        crf_map = {'ultrafast': '28', 'superfast': '26', 'veryfast': '25',
                   'faster': '24', 'fast': '23', 'medium': '23'}
        preset = self.encode_preset_var.get()
        crf    = crf_map.get(preset, '25')

        cmd = ['ffmpeg', '-y', '-i', video_path_abs]
        if use_filter_complex and filter_complex:
            cmd += ['-filter_complex', filter_complex, '-map', '[out]', '-map', '0:a?']
        elif vf:
            cmd += ['-vf', vf]
        cmd += [
            '-c:v', 'libx264', '-preset', preset, '-crf', crf,
            '-threads', '0', '-bufsize', bufsize, '-maxrate', maxrate,
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart', output_path
        ]

        self.processing = True
        self.btn_merge.config(state=tk.DISABLED)
        self.progress_bar['value'] = 0
        self.label_elapsed.config(text="已用时间: 00:00:00")
        self.label_remaining.config(text="剩余时间: 未知")
        getattr(self.master, 'set_status', lambda _: None)("running")

        threading.Thread(
            target=self._run_ffmpeg,
            args=(cmd, output_path, temp_sub1_path, temp_sub2_path, sub1_path, sub2_path),
            daemon=True
        ).start()

    def _run_ffmpeg(self, cmd, output_path, temp_sub1, temp_sub2, orig_sub1, orig_sub2):
        start_time = time.time()
        try:
            process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, encoding='utf-8')
            duration_pattern = re.compile(r'Duration: (\d+):(\d+):(\d+\.\d+)')
            time_pattern     = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
            total_duration   = self.video_duration if self.video_duration > 0 else None

            while True:
                line = process.stderr.readline()
                if not line:
                    break
                line = line.strip()
                if total_duration is None:
                    m = duration_pattern.search(line)
                    if m:
                        h, mi, s = map(float, m.groups())
                        total_duration = h * 3600 + mi * 60 + s
                m = time_pattern.search(line)
                if m:
                    h, mi, s = map(float, m.groups())
                    current_time = h * 3600 + mi * 60 + s
                    if total_duration and total_duration > 0:
                        progress  = (current_time / total_duration) * 100
                        elapsed   = time.time() - start_time
                        remaining = (elapsed / current_time) * (total_duration - current_time) if current_time > 0 else 0
                        self.master.after(0, self._update_progress, progress, elapsed, remaining)

            process.wait()
            if process.returncode == 0:
                # 清理临时文件
                for tmp, orig in [(temp_sub1, orig_sub1), (temp_sub2, orig_sub2)]:
                    if tmp != orig and os.path.exists(tmp):
                        os.remove(tmp)
                logger.info(f"字幕烧录完成 → {os.path.basename(output_path)}")
            else:
                logger.error(f"字幕烧录失败: FFmpeg 执行失败（返回码 {process.returncode}）")
        except Exception as e:
            logger.error(f"字幕烧录失败: {e}")
        finally:
            self.processing = False
            self.master.after(0, lambda: self.btn_merge.config(state=tk.NORMAL))
            self.master.after(0, lambda: getattr(self.master, 'set_status', lambda _: None)("done"))


if __name__ == "__main__":
    root = tk.Tk()
    initial = None
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        initial = sys.argv[1]
    app = SubtitleToolApp(root, initial_file=initial)
    root.mainloop()
