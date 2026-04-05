"""
text2Video.py - 文字转视频工具集

三个独立工具：
  TTSApp         - 文字合成语音（Fish Audio TTS，支持单角色/多角色）
  SRTFromTextApp - 按文本+音频生成字幕 SRT（文本已知，按字符比例分配时间轴）
  AudioVideoApp  - 音频+图片合成视频（ffmpeg）
"""

import os
import tkinter as tk
from tkinter import filedialog, ttk
import threading
import subprocess
import tempfile

try:
    from fish_audio_sdk import Session, TTSRequest
    FISH_AUDIO_AVAILABLE = True
except ImportError:
    FISH_AUDIO_AVAILABLE = False

from ai_router import router
from router_manager import open_router_manager


# ══════════════════════════════════════════════════════════════════════════════
# 工具1：文字合成语音
# ══════════════════════════════════════════════════════════════════════════════

class TTSApp:
    def __init__(self, master):
        self.master = master
        master.title("VideoCraft - 文字合成语音")
        master.geometry("820x680")
        master.resizable(True, True)

        self._stop_flag = False
        self._last_output = ""   # 记录最后生成的音频路径，供其他工具使用

        self._build_ui()
        self._refresh_api_status()

    def _build_ui(self):
        tab = self.master
        tab.columnconfigure(1, weight=1)

        row = 0
        tk.Label(tab, text="Fish Audio:").grid(row=row, column=0, padx=10, pady=8, sticky="e")
        self.api_status_var = tk.StringVar(value="未配置")
        self.api_status_lbl = tk.Label(tab, textvariable=self.api_status_var, fg="red", width=32, anchor="w")
        self.api_status_lbl.grid(row=row, column=1, sticky="w")
        tk.Button(tab, text="Router 管理",
                  command=lambda: open_router_manager(self.master)).grid(row=row, column=2, padx=10)

        row += 1
        mode_frame = tk.LabelFrame(tab, text="模式", padx=8, pady=6)
        mode_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=6, sticky="ew")
        self.mode_var = tk.StringVar(value="single")
        tk.Radiobutton(mode_frame, text="单角色朗读", variable=self.mode_var,
                       value="single", command=self._on_mode_change).pack(side=tk.LEFT, padx=15)
        tk.Radiobutton(mode_frame, text="多角色对话（访谈/剧本）", variable=self.mode_var,
                       value="multi", command=self._on_mode_change).pack(side=tk.LEFT, padx=15)

        # 单角色
        self.single_frame = tk.LabelFrame(tab, text="单角色朗读", padx=10, pady=8)
        self.single_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=4, sticky="ew")
        self.single_frame.columnconfigure(1, weight=1)
        tk.Label(self.single_frame, text="Voice ID:").grid(row=0, column=0, padx=5, pady=6, sticky="e")
        self.voice_id_var = tk.StringVar()
        tk.Entry(self.single_frame, textvariable=self.voice_id_var, width=45).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Label(self.single_frame, text="在 fish.audio 社区搜索音色，复制 model ID 填入",
                 fg="gray", font=("Arial", 8)).grid(row=1, column=1, sticky="w", padx=5)
        tk.Label(self.single_frame, text="输入文本:").grid(row=2, column=0, padx=5, pady=6, sticky="ne")
        self.single_text = tk.Text(self.single_frame, height=8, width=55, wrap=tk.WORD)
        self.single_text.grid(row=2, column=1, columnspan=2, sticky="ew", padx=5)
        self.single_text.insert(tk.END, "请在此输入要朗读的文本内容。")

        # 多角色
        self.multi_frame = tk.LabelFrame(tab, text="多角色对话", padx=10, pady=8)
        self.multi_frame.grid(row=3, column=0, columnspan=3, padx=10, pady=4, sticky="ew")
        self.multi_frame.columnconfigure(1, weight=1)
        hdr = tk.Frame(self.multi_frame)
        hdr.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 4))
        tk.Label(hdr, text="角色名", width=12, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=4)
        tk.Label(hdr, text="Voice ID（fish.audio model ID）", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=4)
        self.roles = []
        self.roles_frame = tk.Frame(self.multi_frame)
        self.roles_frame.grid(row=1, column=0, columnspan=4, sticky="ew")
        self._add_role("主持人", "")
        self._add_role("嘉宾", "")
        tk.Button(self.multi_frame, text="＋ 添加角色",
                  command=lambda: self._add_role("", "")).grid(row=2, column=0, pady=6, sticky="w")
        tk.Label(self.multi_frame, text="对话文本:").grid(row=3, column=0, padx=5, pady=6, sticky="ne")
        self.multi_text = tk.Text(self.multi_frame, height=8, width=55, wrap=tk.WORD)
        self.multi_text.grid(row=3, column=1, columnspan=3, sticky="ew", padx=5)
        self.multi_text.insert(tk.END,
            "主持人：欢迎收看今天的节目。\n嘉宾：谢谢邀请，很高兴来到这里。\n主持人：请问您对这个话题怎么看？")
        tk.Label(self.multi_frame, text='格式：每行 "角色名：台词"，角色名须与上方一致',
                 fg="gray", font=("Arial", 8)).grid(row=4, column=1, sticky="w", padx=5)

        # 公共参数
        row = 4
        common = tk.Frame(tab)
        common.grid(row=row, column=0, columnspan=3, padx=10, pady=4, sticky="ew")
        tk.Label(common, text="输出格式:").pack(side=tk.LEFT, padx=(0, 4))
        self.audio_format_var = tk.StringVar(value="mp3")
        ttk.Combobox(common, textvariable=self.audio_format_var,
                     values=["mp3", "wav", "opus"], state="readonly", width=8).pack(side=tk.LEFT, padx=(0, 20))
        tk.Label(common, text="语速:").pack(side=tk.LEFT, padx=(0, 4))
        self.speed_var = tk.DoubleVar(value=1.0)
        tk.Scale(common, variable=self.speed_var, from_=0.5, to=2.0, resolution=0.1,
                 orient=tk.HORIZONTAL, length=160).pack(side=tk.LEFT)
        self.speed_lbl = tk.Label(common, text="1.0x", width=5)
        self.speed_lbl.pack(side=tk.LEFT)
        self.speed_var.trace('w', lambda *_: self.speed_lbl.config(text=f"{self.speed_var.get():.1f}x"))

        row = 5
        tk.Label(tab, text="输出文件:").grid(row=row, column=0, padx=10, pady=6, sticky="e")
        self.output_path_var = tk.StringVar(value="output.mp3")
        tk.Entry(tab, textvariable=self.output_path_var, width=50).grid(row=row, column=1, sticky="ew")
        tk.Button(tab, text="浏览", command=self._select_output).grid(row=row, column=2, padx=10)

        row = 6
        btn_frame = tk.Frame(tab)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=10)
        self.generate_btn = tk.Button(btn_frame, text="生成语音", command=self.start_generation,
                                      width=18, bg="#2196F3", fg="white", font=("Arial", 10, "bold"))
        self.generate_btn.pack(side=tk.LEFT, padx=8)
        self.stop_btn = tk.Button(btn_frame, text="停止", command=self._stop_generation,
                                  width=8, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=4)

        row = 7
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(tab, variable=self.progress_var, maximum=100, length=500).grid(
            row=row, column=0, columnspan=3, padx=10, pady=(4, 0), sticky="ew")
        row = 8
        self.status_var = tk.StringVar(value="")
        tk.Label(tab, textvariable=self.status_var, fg="blue", anchor="w").grid(
            row=row, column=0, columnspan=3, padx=10, pady=4, sticky="ew")

        self._on_mode_change()

    def _add_role(self, name="", voice_id=""):
        f = tk.Frame(self.roles_frame)
        f.pack(fill="x", pady=2)
        name_var = tk.StringVar(value=name)
        voice_var = tk.StringVar(value=voice_id)
        tk.Entry(f, textvariable=name_var, width=12).pack(side=tk.LEFT, padx=4)
        tk.Entry(f, textvariable=voice_var, width=42).pack(side=tk.LEFT, padx=4)
        role = (name_var, voice_var, f)
        self.roles.append(role)
        tk.Button(f, text="✕", command=lambda r=role: self._remove_role(r), width=2).pack(side=tk.LEFT)

    def _remove_role(self, role):
        if len(self.roles) <= 1:
            return
        role[2].destroy()
        self.roles.remove(role)

    def _on_mode_change(self):
        if self.mode_var.get() == "single":
            self.single_frame.grid()
            self.multi_frame.grid_remove()
        else:
            self.single_frame.grid_remove()
            self.multi_frame.grid()

    def _select_output(self):
        fmt = self.audio_format_var.get()
        path = filedialog.asksaveasfilename(
            title="选择输出文件",
            defaultextension=f".{fmt}",
            filetypes=[(f"{fmt.upper()} files", f"*.{fmt}"), ("All files", "*.*")]
        )
        if path:
            self.output_path_var.set(path)

    def _refresh_api_status(self):
        key = router.get_tts_key("fish_audio")
        if key:
            masked = key[:6] + "****" + key[-4:]
            self.api_status_var.set(f"已配置 ({masked})")
            self.api_status_lbl.config(fg="green")
        else:
            self.api_status_var.set("未配置 — 请在 Router 管理中设置")
            self.api_status_lbl.config(fg="red")

    def start_generation(self):
        if not FISH_AUDIO_AVAILABLE:
            self._show_error("请先安装 Fish Audio SDK：\npip install fish-audio-sdk")
            return
        if not router.get_tts_key("fish_audio"):
            self._show_error("Fish Audio API Key 未配置，请点击「Router 管理」→ TTS Providers 设置")
            return
        self._stop_flag = False
        self.generate_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.progress_var.set(0)
        self.status_var.set("正在准备...")
        t = threading.Thread(
            target=self._run_single if self.mode_var.get() == "single" else self._run_multi,
            daemon=True)
        t.start()

    def _stop_generation(self):
        self._stop_flag = True
        self.status_var.set("正在停止...")

    def _finish_generation(self):
        self.generate_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def _run_single(self):
        try:
            voice_id = self.voice_id_var.get().strip()
            text = self.single_text.get("1.0", tk.END).strip()
            output = self.output_path_var.get().strip()
            if not voice_id:
                self._show_error("请填写 Voice ID"); return
            if not text:
                self._show_error("请输入文本"); return
            if not output:
                self._show_error("请指定输出文件路径"); return

            self.status_var.set("正在调用 Fish Audio API...")
            self.progress_var.set(10)
            session = Session(router.get_tts_key("fish_audio"))
            with session.tts(TTSRequest(
                reference_id=voice_id, text=text, format=self.audio_format_var.get(),
            )) as resp:
                with open(output, "wb") as f:
                    total = 0
                    for chunk in resp.iter_bytes():
                        if self._stop_flag:
                            self.status_var.set("已停止"); return
                        f.write(chunk)
                        total += len(chunk)
                        self.progress_var.set(min(90, 10 + total // 1024))
            self._last_output = output
            self.progress_var.set(100)
            self.status_var.set(f"完成！已保存：{output}")
        except Exception as e:
            self.status_var.set(f"失败：{e}")
            self._show_error(str(e))
        finally:
            self._finish_generation()

    def _run_multi(self):
        try:
            role_map = {nv.get().strip(): vv.get().strip()
                        for nv, vv, _ in self.roles
                        if nv.get().strip() and vv.get().strip()}
            if not role_map:
                self._show_error("请为至少一个角色填写名称和 Voice ID"); return
            raw = self.multi_text.get("1.0", tk.END).strip()
            segments = self._parse_dialogue(raw, role_map)
            if not segments:
                self._show_error('未识别到有效台词。\n格式：每行以"角色名："开头，角色名须与上方定义一致。'); return
            output = self.output_path_var.get().strip()
            if not output:
                self._show_error("请指定输出文件路径"); return

            session = Session(router.get_tts_key("fish_audio"))
            total = len(segments)
            tmp_files = []
            for i, (role, text) in enumerate(segments):
                if self._stop_flag:
                    self.status_var.set("已停止")
                    self._cleanup_temps(tmp_files); return
                self.status_var.set(f"生成第 {i+1}/{total} 段（{role}）...")
                self.progress_var.set(int(i / total * 85))
                fmt = self.audio_format_var.get()
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{fmt}")
                tmp.close()
                tmp_files.append(tmp.name)
                with session.tts(TTSRequest(
                    reference_id=role_map[role], text=text, format=fmt,
                )) as resp:
                    with open(tmp.name, "wb") as f:
                        for chunk in resp.iter_bytes():
                            if self._stop_flag:
                                self.status_var.set("已停止")
                                self._cleanup_temps(tmp_files); return
                            f.write(chunk)

            self.status_var.set("正在合并音频...")
            self.progress_var.set(90)
            self._concat_audio(tmp_files, output)
            self._cleanup_temps(tmp_files)
            self._last_output = output
            self.progress_var.set(100)
            self.status_var.set(f"完成！{total} 段已合并：{output}")
        except Exception as e:
            self.status_var.set(f"失败：{e}")
            self._show_error(str(e))
        finally:
            self._finish_generation()

    def _parse_dialogue(self, raw, role_map):
        segments = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            for role in role_map:
                for sep in ['：', ':']:
                    if line.startswith(role + sep):
                        text = line[len(role) + 1:].strip()
                        if text:
                            if segments and segments[-1][0] == role:
                                segments[-1] = (role, segments[-1][1] + " " + text)
                            else:
                                segments.append((role, text))
                        break
        return segments

    def _concat_audio(self, files, output):
        lf = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8')
        for f in files:
            lf.write(f"file '{f}'\n")
        lf.close()
        try:
            subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                            '-i', lf.name, '-c', 'copy', output],
                           capture_output=True, check=True)
        finally:
            os.unlink(lf.name)

    def _cleanup_temps(self, files):
        for f in files:
            try: os.unlink(f)
            except Exception: pass

    def _show_error(self, msg):
        self.master.after(0, lambda: __import__('tkinter').messagebox.showerror(
            "错误", msg, parent=self.master))


# ══════════════════════════════════════════════════════════════════════════════
# 工具2：文本 → SRT 字幕
# ══════════════════════════════════════════════════════════════════════════════

class SRTFromTextApp:
    """
    文本已知（来自 TTS 工具），根据音频总时长按字符比例分配时间轴，生成 SRT。
    不需要 ASR，适合文字视频制作流水线的字幕步骤。
    """

    def __init__(self, master):
        self.master = master
        master.title("VideoCraft - 生成字幕 SRT")
        master.geometry("780x620")
        master.resizable(True, True)
        self._build_ui()

    def _build_ui(self):
        tab = self.master
        tab.columnconfigure(1, weight=1)

        row = 0
        tk.Label(tab, text="音频文件:").grid(row=row, column=0, padx=10, pady=8, sticky="e")
        self.audio_var = tk.StringVar()
        tk.Entry(tab, textvariable=self.audio_var, width=50, state='readonly').grid(
            row=row, column=1, sticky="ew")
        tk.Button(tab, text="选择", command=self._select_audio).grid(row=row, column=2, padx=10)

        row += 1
        self.duration_var = tk.StringVar(value="")
        tk.Label(tab, textvariable=self.duration_var, fg="gray",
                 font=("Arial", 8)).grid(row=row, column=1, sticky="w", padx=4)

        row += 1
        tk.Label(tab, text="文本内容:").grid(row=row, column=0, padx=10, pady=8, sticky="ne")
        self.text_box = tk.Text(tab, height=12, width=55, wrap=tk.WORD)
        self.text_box.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(0, 10))
        self.text_box.insert(tk.END,
            "主持人：欢迎收看今天的节目。\n嘉宾：谢谢邀请，很高兴来到这里。\n主持人：请问您对这个话题怎么看？")

        row += 1
        hint_frame = tk.Frame(tab)
        hint_frame.grid(row=row, column=1, sticky="w", padx=4, pady=2)
        tk.Label(hint_frame, text='支持 "角色名：台词" 格式（多角色）或纯文本（单角色）',
                 fg="gray", font=("Arial", 8)).pack(side=tk.LEFT)

        row += 1
        opt_frame = tk.LabelFrame(tab, text="分段设置", padx=10, pady=6)
        opt_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=6, sticky="ew")

        tk.Label(opt_frame, text="每段最大字符数:").pack(side=tk.LEFT, padx=(0, 4))
        self.max_chars_var = tk.IntVar(value=30)
        tk.Spinbox(opt_frame, textvariable=self.max_chars_var, from_=10, to=100,
                   width=6).pack(side=tk.LEFT, padx=(0, 20))
        tk.Label(opt_frame, text="段间停顿(秒):").pack(side=tk.LEFT, padx=(0, 4))
        self.gap_var = tk.DoubleVar(value=0.3)
        tk.Spinbox(opt_frame, textvariable=self.gap_var, from_=0.0, to=2.0,
                   increment=0.1, format="%.1f", width=6).pack(side=tk.LEFT)

        row += 1
        tk.Label(tab, text="输出 SRT:").grid(row=row, column=0, padx=10, pady=8, sticky="e")
        self.output_var = tk.StringVar(value="output.srt")
        tk.Entry(tab, textvariable=self.output_var, width=50).grid(row=row, column=1, sticky="ew")
        tk.Button(tab, text="浏览", command=self._select_output).grid(row=row, column=2, padx=10)

        row += 1
        tk.Button(tab, text="生成 SRT", command=self._generate,
                  bg="#FF9800", fg="white", width=18, font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=3, pady=14)

        row += 1
        self.status_var = tk.StringVar(value="")
        tk.Label(tab, textvariable=self.status_var, fg="blue", anchor="w").grid(
            row=row, column=0, columnspan=3, padx=10, pady=4, sticky="ew")

    def _select_audio(self):
        path = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[("音频文件", "*.mp3 *.wav *.m4a *.aac *.ogg *.flac"), ("所有文件", "*.*")]
        )
        if path:
            self.audio_var.set(path)
            dur = self._get_duration(path)
            if dur > 0:
                self.duration_var.set(f"时长：{dur:.2f} 秒")
            else:
                self.duration_var.set("无法读取时长")

    def _select_output(self):
        path = filedialog.asksaveasfilename(
            title="保存 SRT 文件", defaultextension=".srt",
            filetypes=[("SRT files", "*.srt"), ("All files", "*.*")]
        )
        if path:
            self.output_var.set(path)

    def _get_duration(self, audio_path):
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
                capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _generate(self):
        audio = self.audio_var.get().strip()
        if not audio or not os.path.exists(audio):
            self.status_var.set("请先选择有效的音频文件")
            return
        raw = self.text_box.get("1.0", tk.END).strip()
        if not raw:
            self.status_var.set("请输入文本内容")
            return
        output = self.output_var.get().strip()
        if not output:
            self.status_var.set("请指定输出 SRT 路径")
            return

        duration = self._get_duration(audio)
        if duration <= 0:
            self.status_var.set("无法获取音频时长，请检查 ffprobe 是否可用")
            return

        segments = self._split_to_segments(raw, self.max_chars_var.get())
        srt_content = self._build_srt(segments, duration, self.gap_var.get())

        with open(output, 'w', encoding='utf-8') as f:
            f.write(srt_content)

        self.status_var.set(f"完成！共 {len(segments)} 条字幕 → {output}")

    def _split_to_segments(self, raw, max_chars):
        """将文本分割为字幕段落（支持角色格式和纯文本）"""
        import re
        lines = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            # 去掉角色名前缀（保留台词）
            m = re.match(r'^.{1,15}[：:](.+)', line)
            if m:
                line = m.group(1).strip()
            # 按句子分割
            sentences = re.split(r'(?<=[。！？!?\.…])', line)
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                # 超长句子按 max_chars 切分
                while len(s) > max_chars:
                    lines.append(s[:max_chars])
                    s = s[max_chars:]
                if s:
                    lines.append(s)
        return [l for l in lines if l]

    def _build_srt(self, segments, total_duration, gap):
        """按字符比例分配时间轴，生成 SRT 字符串"""
        if not segments:
            return ""
        total_chars = sum(len(s) for s in segments)
        # 总有效时长（扣除段间停顿）
        total_gap = gap * (len(segments) - 1)
        speech_time = max(total_duration - total_gap, total_duration * 0.8)

        srt_lines = []
        cursor = 0.0
        for i, seg in enumerate(segments):
            seg_dur = (len(seg) / total_chars) * speech_time
            start = cursor
            end = cursor + seg_dur
            srt_lines.append(f"{i+1}")
            srt_lines.append(f"{self._fmt_time(start)} --> {self._fmt_time(end)}")
            srt_lines.append(seg)
            srt_lines.append("")
            cursor = end + gap
        return "\n".join(srt_lines)

    @staticmethod
    def _fmt_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ══════════════════════════════════════════════════════════════════════════════
# 工具3：音频 + 图片 合成视频
# ══════════════════════════════════════════════════════════════════════════════

from core.subtitle_ops import (
    split_srt_to_file,
    build_subtitle_style,
    escape_ffmpeg_path,
    LAYOUT_DEFAULTS,
    hex_color_to_ass,
)


class AudioVideoApp:
    def __init__(self, master):
        self.master = master
        master.title("VideoCraft - 音频合成视频")
        master.geometry("1060x760")
        master.resizable(True, True)
        self._build_ui()

    def _build_ui(self):
        tab = self.master
        left_frame = tk.Frame(tab)
        left_frame.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        right_frame = tk.Frame(tab)
        right_frame.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

        # ── 左侧：文件选择 + 视频参数 ──
        file_frame = tk.LabelFrame(left_frame, text="文件选择", padx=8, pady=8)
        file_frame.pack(fill="both", padx=4, pady=4)
        file_frame.columnconfigure(1, weight=1)

        def _file_row(parent, row, label, var, cmd, readonly=True, info_var=None):
            tk.Label(parent, text=label).grid(row=row, column=0, padx=4, pady=6, sticky="e")
            state = 'readonly' if readonly else 'normal'
            tk.Entry(parent, textvariable=var, width=36, state=state).grid(
                row=row, column=1, sticky="ew", padx=4)
            tk.Button(parent, text="选择" if readonly else "浏览", command=cmd,
                      width=7).grid(row=row, column=2, padx=4)
            if info_var is not None:
                tk.Label(parent, textvariable=info_var, fg="gray",
                         font=("Arial", 8)).grid(row=row+1, column=1, sticky="w", padx=4)

        self.audio_path_var = tk.StringVar()
        self.audio_info_var = tk.StringVar(value="未选择音频文件")
        _file_row(file_frame, 0, "音频文件:", self.audio_path_var,
                  self._select_audio, info_var=self.audio_info_var)

        self.image_path_var = tk.StringVar()
        self.image_info_var = tk.StringVar(value="未选择图片文件")
        _file_row(file_frame, 2, "图片文件:", self.image_path_var,
                  self._select_image, info_var=self.image_info_var)

        self.srt_path_var = tk.StringVar()
        _file_row(file_frame, 4, "字幕 SRT:", self.srt_path_var, self._select_srt)
        tk.Label(file_frame, text="（可选）若已生成 SRT 可直接烧录",
                 fg="gray", font=("Arial", 8)).grid(row=5, column=1, sticky="w", padx=4)

        self.video_output_var = tk.StringVar(value="output.mp4")
        _file_row(file_frame, 6, "输出视频:", self.video_output_var,
                  self._select_video_output, readonly=False)

        # 视频参数
        cfg = tk.LabelFrame(left_frame, text="视频配置", padx=8, pady=8)
        cfg.pack(fill="both", padx=4, pady=4)

        tk.Label(cfg, text="视频方向:", font=("Arial", 9, "bold")).grid(
            row=0, column=0, padx=4, pady=4, sticky="w")
        self.orientation_var = tk.StringVar(value="horizontal")
        ori_f = tk.Frame(cfg)
        ori_f.grid(row=0, column=1, columnspan=2, sticky="w", padx=4)
        tk.Radiobutton(ori_f, text="横屏 (16:9)", variable=self.orientation_var,
                       value="horizontal", command=self._on_orientation).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(ori_f, text="竖屏 (9:16)", variable=self.orientation_var,
                       value="vertical", command=self._on_orientation).pack(side=tk.LEFT, padx=5)

        tk.Label(cfg, text="分辨率:").grid(row=1, column=0, padx=4, pady=4, sticky="e")
        self.resolution_var = tk.StringVar(value="1920x1080 (1080p)")
        self.resolution_combo = ttk.Combobox(cfg, textvariable=self.resolution_var,
                                              state="readonly", width=28)
        self._update_resolution()
        self.resolution_combo.grid(row=1, column=1, columnspan=2, sticky="w", padx=4)

        tk.Label(cfg, text="背景填充色:").grid(row=2, column=0, padx=4, pady=4, sticky="e")
        bg_f = tk.Frame(cfg)
        bg_f.grid(row=2, column=1, columnspan=2, sticky="w", padx=4)
        self.bg_color_var = tk.StringVar(value="#000000")
        tk.Entry(bg_f, textvariable=self.bg_color_var, width=9, state='readonly').pack(side=tk.LEFT, padx=2)
        self.bg_preview = tk.Canvas(bg_f, width=22, height=18, bg="#000000",
                                    relief=tk.SUNKEN, borderwidth=1)
        self.bg_preview.pack(side=tk.LEFT, padx=2)
        tk.Button(bg_f, text="选择", command=self._choose_bg, width=7).pack(side=tk.LEFT, padx=2)

        tk.Label(cfg, text="帧率:").grid(row=3, column=0, padx=4, pady=4, sticky="e")
        self.fps_var = tk.StringVar(value="30")
        ttk.Combobox(cfg, textvariable=self.fps_var, values=["24", "25", "30", "60"],
                     state="readonly", width=8).grid(row=3, column=1, sticky="w", padx=4)

        tk.Label(cfg, text="视频编码:").grid(row=4, column=0, padx=4, pady=4, sticky="e")
        self.codec_var = tk.StringVar(value="libx264")
        ttk.Combobox(cfg, textvariable=self.codec_var,
                     values=["libx264 (H.264)", "libx265 (H.265/HEVC)", "mpeg4"],
                     state="readonly", width=22).grid(row=4, column=1, columnspan=2, sticky="w", padx=4)

        # ── 右侧：字幕样式 + 水印 ──

        # 字幕设置
        sub_frame = tk.LabelFrame(right_frame, text="字幕设置", padx=8, pady=8)
        sub_frame.pack(fill="both", padx=4, pady=4)
        sub_frame.columnconfigure(1, weight=1)

        self.sub_split_var = tk.BooleanVar(value=True)
        tk.Checkbutton(sub_frame, text="自动换行分割 SRT",
                       variable=self.sub_split_var,
                       font=("Arial", 9, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

        tk.Label(sub_frame, text="每行最大字符:").grid(row=1, column=0, padx=4, pady=5, sticky="e")
        self.sub_max_chars_var = tk.IntVar(value=20)
        tk.Spinbox(sub_frame, textvariable=self.sub_max_chars_var,
                   from_=5, to=80, width=6).grid(row=1, column=1, sticky="w", padx=4)
        self.sub_maxchars_hint = tk.Label(sub_frame, text="(横屏推荐 20，竖屏推荐 10)",
                                          fg="gray", font=("Arial", 8))
        self.sub_maxchars_hint.grid(row=1, column=2, sticky="w")

        self.sub_is_chinese_var = tk.BooleanVar(value=True)
        tk.Checkbutton(sub_frame, text="中文断句优先（按标点）",
                       variable=self.sub_is_chinese_var).grid(
            row=2, column=0, columnspan=3, sticky="w", padx=4, pady=2)

        tk.Label(sub_frame, text="字幕颜色:").grid(row=3, column=0, padx=4, pady=5, sticky="e")
        sub_color_f = tk.Frame(sub_frame)
        sub_color_f.grid(row=3, column=1, columnspan=2, sticky="w", padx=4)
        self.sub_color_var = tk.StringVar(value="#FFFFFF")
        tk.Entry(sub_color_f, textvariable=self.sub_color_var, width=9, state='readonly').pack(side=tk.LEFT, padx=2)
        self.sub_color_preview = tk.Canvas(sub_color_f, width=22, height=18, bg="#FFFFFF",
                                            relief=tk.SUNKEN, borderwidth=1)
        self.sub_color_preview.pack(side=tk.LEFT, padx=2)
        tk.Button(sub_color_f, text="选择", command=self._choose_sub_color, width=7).pack(side=tk.LEFT, padx=2)

        tk.Label(sub_frame, text="字幕字号:").grid(row=4, column=0, padx=4, pady=5, sticky="e")
        self.sub_fontsize_var = tk.IntVar(value=28)
        tk.Spinbox(sub_frame, textvariable=self.sub_fontsize_var,
                   from_=10, to=72, width=6).grid(row=4, column=1, sticky="w", padx=4)
        tk.Label(sub_frame, text="(横屏推荐 28，竖屏推荐 20)",
                 fg="gray", font=("Arial", 8)).grid(row=4, column=2, sticky="w")

        tk.Label(sub_frame, text="底部边距:").grid(row=5, column=0, padx=4, pady=5, sticky="e")
        self.sub_margin_v_var = tk.IntVar(value=80)
        tk.Spinbox(sub_frame, textvariable=self.sub_margin_v_var,
                   from_=10, to=300, width=6).grid(row=5, column=1, sticky="w", padx=4)
        tk.Label(sub_frame, text="像素（横屏推荐 80，竖屏推荐 60）",
                 fg="gray", font=("Arial", 8)).grid(row=5, column=2, sticky="w")

        # 水印设置
        wm_frame = tk.LabelFrame(right_frame, text="水印设置", padx=8, pady=8)
        wm_frame.pack(fill="both", padx=4, pady=4)
        wm_frame.columnconfigure(1, weight=1)

        self.watermark_enabled_var = tk.BooleanVar(value=True)
        tk.Checkbutton(wm_frame, text="启用水印", variable=self.watermark_enabled_var,
                       font=("Arial", 9, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

        tk.Label(wm_frame, text="水印文字:").grid(row=1, column=0, padx=4, pady=5, sticky="e")
        self.watermark_text_var = tk.StringVar(value="老猿世界观察")
        tk.Entry(wm_frame, textvariable=self.watermark_text_var, width=28).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=4)

        tk.Label(wm_frame, text="文字颜色:").grid(row=2, column=0, padx=4, pady=5, sticky="e")
        wm_color_f = tk.Frame(wm_frame)
        wm_color_f.grid(row=2, column=1, columnspan=2, sticky="w", padx=4)
        self.watermark_color_var = tk.StringVar(value="#80ffff")
        tk.Entry(wm_color_f, textvariable=self.watermark_color_var, width=9, state='readonly').pack(side=tk.LEFT, padx=2)
        self.wm_color_preview = tk.Canvas(wm_color_f, width=22, height=18, bg="#80ffff",
                                           relief=tk.SUNKEN, borderwidth=1)
        self.wm_color_preview.pack(side=tk.LEFT, padx=2)
        tk.Button(wm_color_f, text="选择", command=self._choose_wm_color, width=7).pack(side=tk.LEFT, padx=2)

        tk.Label(wm_frame, text="透明度:").grid(row=3, column=0, padx=4, pady=5, sticky="e")
        self.watermark_opacity_var = tk.DoubleVar(value=0.5)
        tk.Scale(wm_frame, from_=0.1, to=1.0, resolution=0.1, orient=tk.HORIZONTAL,
                 variable=self.watermark_opacity_var, length=200).grid(
            row=3, column=1, columnspan=2, sticky="ew", padx=4)

        tk.Label(wm_frame, text="位置:").grid(row=4, column=0, padx=4, pady=5, sticky="e")
        self.watermark_position_var = tk.StringVar(value="右上角 (topright)")
        ttk.Combobox(wm_frame, textvariable=self.watermark_position_var,
                     values=["右上角 (topright)", "左上角 (topleft)",
                             "右下角 (bottomright)", "左下角 (bottomleft)"],
                     state="readonly", width=24).grid(row=4, column=1, columnspan=2, sticky="ew", padx=4)

        # ── 底部：按钮 + 进度 ──
        bottom = tk.Frame(tab)
        bottom.grid(row=1, column=0, columnspan=2, pady=8, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        btn_row = tk.Frame(bottom)
        btn_row.grid(row=0, column=0)
        self.generate_btn = tk.Button(btn_row, text="合成视频", command=self._start,
                                      width=22, height=2, bg="#4CAF50", fg="white",
                                      font=("Arial", 11, "bold"))
        self.generate_btn.pack(side=tk.LEFT, padx=10)
        self.stop_btn = tk.Button(btn_row, text="停止", command=self._stop,
                                  width=8, height=2, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=4)

        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(bottom, variable=self.progress_var, maximum=100, length=600).grid(
            row=1, column=0, padx=12, pady=(6, 0), sticky="ew")

        self.status_var = tk.StringVar(value="")
        tk.Label(bottom, textvariable=self.status_var, fg="blue",
                 font=("Arial", 9), anchor="w").grid(
            row=2, column=0, padx=12, pady=2, sticky="ew")

        self._ffmpeg_proc = None

    def _select_audio(self):
        path = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[("音频文件", "*.mp3 *.wav *.m4a *.aac *.ogg *.flac"), ("所有文件", "*.*")])
        if path:
            self.audio_path_var.set(path)
            dur = self._get_duration(path)
            self.audio_info_var.set(
                f"{os.path.basename(path)} | {dur:.1f} 秒" if dur > 0
                else os.path.basename(path))

    def _select_image(self):
        path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.webp"), ("所有文件", "*.*")])
        if path:
            self.image_path_var.set(path)
            try:
                from PIL import Image as _Img
                img = _Img.open(path)
                self.image_info_var.set(f"{os.path.basename(path)} | {img.width}×{img.height}")
            except Exception:
                self.image_info_var.set(os.path.basename(path))

    def _select_srt(self):
        path = filedialog.askopenfilename(
            title="选择字幕文件",
            filetypes=[("SRT files", "*.srt"), ("所有文件", "*.*")])
        if path:
            self.srt_path_var.set(path)

    def _select_video_output(self):
        path = filedialog.asksaveasfilename(
            title="输出视频", defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("所有文件", "*.*")])
        if path:
            self.video_output_var.set(path)

    def _on_orientation(self):
        """方向切换时同步更新分辨率和字幕默认参数"""
        self._update_resolution()
        ori = self.orientation_var.get()
        d = LAYOUT_DEFAULTS.get(ori, LAYOUT_DEFAULTS["horizontal"])
        self.sub_max_chars_var.set(d["max_chars_zh"])
        self.sub_fontsize_var.set(d["fontsize"])
        self.sub_margin_v_var.set(d["margin_v"])

    def _update_resolution(self):
        if self.orientation_var.get() == "horizontal":
            opts = ["1920x1080 (1080p)", "1280x720 (720p)", "3840x2160 (4K)", "2560x1440 (2K)"]
            default = "1920x1080 (1080p)"
        else:
            opts = ["1080x1920 (竖屏1080p)", "720x1280 (竖屏720p)",
                    "2160x3840 (竖屏4K)", "1440x2560 (竖屏2K)"]
            default = "1080x1920 (竖屏1080p)"
        self.resolution_combo['values'] = opts
        if self.resolution_var.get() not in opts:
            self.resolution_var.set(default)

    def _choose_bg(self):
        from tkinter import colorchooser
        c = colorchooser.askcolor(title="背景填充色", initialcolor=self.bg_color_var.get())
        if c[1]:
            self.bg_color_var.set(c[1]); self.bg_preview.config(bg=c[1])

    def _choose_sub_color(self):
        from tkinter import colorchooser
        c = colorchooser.askcolor(title="字幕颜色", initialcolor=self.sub_color_var.get())
        if c[1]:
            self.sub_color_var.set(c[1]); self.sub_color_preview.config(bg=c[1])

    def _choose_wm_color(self):
        from tkinter import colorchooser
        c = colorchooser.askcolor(title="水印颜色", initialcolor=self.watermark_color_var.get())
        if c[1]:
            self.watermark_color_var.set(c[1]); self.wm_color_preview.config(bg=c[1])

    def _get_duration(self, path):
        try:
            r = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', path],
                capture_output=True, text=True, check=True)
            return float(r.stdout.strip())
        except Exception:
            return 0.0

    def _start(self):
        audio = self.audio_path_var.get()
        image = self.image_path_var.get()
        output = self.video_output_var.get()
        mb = __import__('tkinter').messagebox
        if not audio or not os.path.exists(audio):
            mb.showerror("错误", "请选择有效的音频文件"); return
        if not image or not os.path.exists(image):
            mb.showerror("错误", "请选择有效的图片文件"); return
        if not output:
            mb.showerror("错误", "请指定输出视频文件路径"); return
        self.generate_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.progress_var.set(0)
        self.status_var.set("正在准备...")
        threading.Thread(target=self._generate,
                         args=(audio, image, output), daemon=True).start()

    def _stop(self):
        if self._ffmpeg_proc and self._ffmpeg_proc.poll() is None:
            self._ffmpeg_proc.terminate()
            self.status_var.set("已停止")

    def _generate(self, audio, image, output):
        tmp_srt = None
        try:
            res_str = self.resolution_var.get().split(" ")[0]
            width, height = map(int, res_str.split('x'))
            fps = int(self.fps_var.get())
            codec = self.codec_var.get().split(" ")[0]
            bg = self._hex_to_ffmpeg(self.bg_color_var.get())
            orientation = self.orientation_var.get()

            # 获取音频总时长，用于进度计算
            total_dur = self._get_duration(audio)

            vf = [
                f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={bg}",
            ]

            # SRT 字幕处理
            srt_path = self.srt_path_var.get().strip()
            if srt_path and os.path.exists(srt_path):
                burn_srt = srt_path
                # 如果启用换行分割，先处理 SRT
                if self.sub_split_var.get():
                    self.status_var.set("正在分割字幕...")
                    try:
                        tmp_srt = srt_path.replace('.srt', '_tmp_split.srt')
                        split_srt_to_file(
                            srt_path,
                            max_chars=self.sub_max_chars_var.get(),
                            is_chinese=self.sub_is_chinese_var.get(),
                            output_path=tmp_srt,
                        )
                        burn_srt = tmp_srt
                    except Exception as e:
                        self.status_var.set(f"字幕分割失败，使用原始 SRT：{e}")
                        burn_srt = srt_path

                # 构建字幕样式
                style = build_subtitle_style(
                    orientation=orientation,
                    fontsize=self.sub_fontsize_var.get(),
                    color=self.sub_color_var.get(),
                    margin_v=self.sub_margin_v_var.get(),
                )
                srt_ff = escape_ffmpeg_path(burn_srt)
                vf.append(f"subtitles='{srt_ff}':force_style='{style}'")

            # 水印
            if self.watermark_enabled_var.get():
                wf = self._build_watermark(height)
                if wf:
                    vf.append(wf)

            cmd = [
                'ffmpeg', '-loop', '1', '-i', image, '-i', audio,
                '-vf', ",".join(vf),
                '-c:v', codec, '-c:a', 'aac', '-b:a', '192k',
                '-shortest', '-r', str(fps), '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart', '-y', output,
            ]

            self.status_var.set("正在合成视频...")
            import re as _re
            self._ffmpeg_proc = subprocess.Popen(
                cmd, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')

            for line in self._ffmpeg_proc.stderr:
                m = _re.search(r'time=(\d+):(\d+):([\d.]+)', line)
                if m and total_dur > 0:
                    elapsed = (int(m.group(1)) * 3600 +
                               int(m.group(2)) * 60 +
                               float(m.group(3)))
                    self.progress_var.set(min(99, elapsed / total_dur * 100))

            self._ffmpeg_proc.wait()
            if self._ffmpeg_proc.returncode != 0:
                raise RuntimeError("ffmpeg 返回非零退出码，请检查参数")

            self.progress_var.set(100)
            self.status_var.set(f"完成！已保存：{output}")
            __import__('tkinter').messagebox.showinfo("成功", f"视频已保存到：\n{output}")

        except Exception as e:
            self.status_var.set("生成失败")
            __import__('tkinter').messagebox.showerror("错误", f"视频生成失败：\n{e}")
        finally:
            self.generate_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self._ffmpeg_proc = None
            if tmp_srt and os.path.exists(tmp_srt):
                try: os.unlink(tmp_srt)
                except Exception: pass

    def _hex_to_ffmpeg(self, hex_color):
        h = hex_color.lstrip('#')
        if len(h) == 3:
            h = ''.join(c*2 for c in h)
        return f"0x{h.upper()}"

    def _build_watermark(self, height):
        text = self.watermark_text_var.get().strip()
        if not text:
            return None
        color = self.watermark_color_var.get().lstrip('#')
        font_size = int(36 * height / 1080)
        opacity = self.watermark_opacity_var.get()
        pos_raw = self.watermark_position_var.get()
        pos = pos_raw.split('(')[1].split(')')[0] if '(' in pos_raw else pos_raw
        margin = int(30 * height / 1080)
        coords = {
            "topright":    (f"w-tw-{margin}", str(margin)),
            "topleft":     (str(margin), str(margin)),
            "bottomright": (f"w-tw-{margin}", f"h-th-{margin}"),
            "bottomleft":  (str(margin), f"h-th-{margin}"),
        }
        x, y = coords.get(pos, coords["topright"])
        escaped = text.replace(":", "\\:").replace("'", "")
        return (f"drawtext=text='{escaped}':fontcolor={color}@{opacity}:"
                f"fontsize={font_size}:font='Microsoft YaHei':x={x}:y={y}:"
                f"borderw=2:bordercolor=black")


# ── 兼容旧入口（Hub 直接引用 Text2VideoApp 时不报错）──────────────────────────
Text2VideoApp = TTSApp


if __name__ == "__main__":
    import sys
    tool = sys.argv[1] if len(sys.argv) > 1 else "tts"
    root = tk.Tk()
    if tool == "srt":
        SRTFromTextApp(root)
    elif tool == "video":
        AudioVideoApp(root)
    else:
        TTSApp(root)
    root.mainloop()
