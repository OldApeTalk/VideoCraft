"""
VideoCraftHub.py - VS Code 风格主界面

布局：Menu 菜单栏 + 左侧 Sidebar 文件浏览器 + 右侧内容区 + 底部状态栏
工具以 tk.Toplevel 弹窗方式打开（有类的工具），或 subprocess（无类的工具）。
"""

import importlib.util
import io
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Windows GBK stdout/stderr → UTF-8，防止工具内 print(emoji) 抛 UnicodeEncodeError
if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from project import Project, add_recent_project, get_recent_projects, file_icon
from router_manager import open_router_manager
from operations import get_operations

# ── 工具注册表 ────────────────────────────────────────────────────────────────
# class: None → 用 subprocess 启动；有 class 名 → Toplevel 内嵌

_SRC = os.path.dirname(os.path.abspath(__file__))

TOOL_MAP = {
    "yt-dlp":      {"file": "tools/download/yt_dlp_tool.py",      "class": "YouTubeDownloader"},
    "speech2text": {"file": "tools/speech/speech2text.py",         "class": "Speech2TextApp"},
    "translate":   {"file": "tools/translate/translate_srt.py",    "class": "TranslateApp"},
    "subtitle":    {"file": "tools/subtitle/subtitle_tool.py",     "class": "SubtitleToolApp"},
    "word-subtitle": {"file": "tools/subtitle/word_subtitle.py",   "class": "WordSubtitleApp"},
    "srttools":               {"file": "tools/subtitle/srt_tools.py", "class": "YouTubeSegmentsApp"},
    "srt-extract-subtitles":  {"file": "tools/subtitle/srt_tools.py", "class": "SrtExtractSubtitlesApp"},
    "srt-gen-segments":       {"file": "tools/subtitle/srt_tools.py", "class": "SrtGenerateSegmentsApp"},
    "srt-extract-paragraphs": {"file": "tools/subtitle/srt_tools.py", "class": "SrtExtractParagraphsApp"},
    "srt-refine":             {"file": "tools/subtitle/srt_tools.py", "class": "SrtRefineSegmentsApp"},
    "srt-gen-titles":         {"file": "tools/subtitle/srt_tools.py", "class": "SrtGenerateTitlesApp"},
    "splitvideo":  {"file": "tools/video/split_video.py",          "class": "SplitVideoApp"},
    "videotools":       {"file": "tools/video/video_tools.py", "class": "VideoToolsGUI"},
    "extract-audio":    {"file": "tools/video/video_tools.py", "class": "ExtractAudioApp"},
    "convert-bitrate":  {"file": "tools/video/video_tools.py", "class": "ConvertBitrateApp"},
    "adjust-volume":    {"file": "tools/video/video_tools.py", "class": "AdjustVolumeApp"},
    "extract-clip":     {"file": "tools/video/video_tools.py", "class": "ExtractClipApp"},
    "auto-split":       {"file": "tools/video/video_tools.py", "class": "AutoSplitApp"},
    "tts":            {"file": "tools/text2video/text2video.py", "class": "TTSApp"},
    "tts-srt":        {"file": "tools/text2video/text2video.py", "class": "SRTFromTextApp"},
    "tts-video":      {"file": "tools/text2video/text2video.py", "class": "AudioVideoApp"},
    "daily-news":     {"file": "tools/text2video/text2video.py", "class": "DailyNewsApp"},
    "tiktok-publish":   {"file": "tools/publish/tiktok_publish.py",  "class": "TikTokPublishApp"},
    "youtube-publish":  {"file": "tools/publish/youtube_publish.py", "class": "YouTubePublishApp"},
}

# ── Tab 状态颜色 ──────────────────────────────────────────────────────────────

STATUS_COLORS = {
    "idle":    "#9e9e9e",   # 灰：待命
    "running": "#ffc107",   # 黄：运行中
    "done":    "#4caf50",   # 绿：完成
}


class ToolFrame(ttk.Frame):
    """
    工具容器。作为 master 传入工具类，静默吸收 Toplevel 专属方法
    (geometry / title / resizable)，并提供 set_status() 供工具回调。
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._tool_title = ""
        self._set_status_cb = None          # 由 Hub 在创建后注入

    def geometry(self, spec=None):
        return ""

    def title(self, string=None):
        if string is not None:
            self._tool_title = string
        return self._tool_title

    def resizable(self, width=None, height=None):
        pass

    def set_status(self, status: str):
        """工具调用：set_status('running') / set_status('done')"""
        if self._set_status_cb:
            self._set_status_cb(status)


class TabBar(tk.Frame):
    """
    自定义横向 Tab 栏。每个 Tab 含彩色状态圆点 + 标题 + 关闭按钮。
    """
    def __init__(self, master, on_select, on_close, **kwargs):
        super().__init__(master, bg="#e8e8e8", height=34, **kwargs)
        self.pack_propagate(False)
        self._on_select = on_select
        self._on_close  = on_close
        self._tabs: dict[str, dict] = {}    # key → {frame, dot, title_lbl}
        self._active_key: str | None = None

    def add_tab(self, key: str, title: str, status: str = "idle") -> None:
        btn = tk.Frame(self, bg="#d0d0d0", cursor="hand2", padx=6, pady=0)
        btn.pack(side="left", padx=(4, 0), pady=3)

        dot = tk.Label(btn, text="●", fg=STATUS_COLORS[status],
                       bg="#d0d0d0", font=("", 8))
        dot.pack(side="left", pady=4)

        lbl = tk.Label(btn, text=f" {title} ", bg="#d0d0d0",
                       font=("Segoe UI", 9))
        lbl.pack(side="left", pady=4)

        cls_btn = tk.Label(btn, text=" × ", bg="#d0d0d0",
                           font=("Segoe UI", 10), cursor="hand2",
                           fg="#666")
        cls_btn.pack(side="left", pady=4)

        for w in (btn, dot, lbl):
            w.bind("<Button-1>", lambda e, k=key: self._on_select(k))
        cls_btn.bind("<Button-1>", lambda e, k=key: self._on_close(k))
        cls_btn.bind("<Enter>",    lambda e, w=cls_btn: w.configure(fg="#c00"))
        cls_btn.bind("<Leave>",    lambda e, w=cls_btn: w.configure(fg="#666"))

        self._tabs[key] = {"frame": btn, "dot": dot, "title": lbl,
                           "close": cls_btn}
        self.set_active(key)

    def set_active(self, key: str) -> None:
        for k, t in self._tabs.items():
            is_active = (k == key)
            bg = "#ffffff" if is_active else "#d0d0d0"
            for w in t["frame"].winfo_children():
                w.configure(bg=bg)
            t["frame"].configure(bg=bg)
        self._active_key = key

    def set_status(self, key: str, status: str) -> None:
        if key in self._tabs:
            color = STATUS_COLORS.get(status, STATUS_COLORS["idle"])
            self._tabs[key]["dot"].configure(fg=color)

    def remove_tab(self, key: str) -> "str | None":
        """删除 Tab，返回应激活的下一个 key（无则返回 None）。"""
        if key not in self._tabs:
            return None
        self._tabs[key]["frame"].destroy()
        del self._tabs[key]
        remaining = list(self._tabs.keys())
        if remaining:
            nxt = remaining[-1]
            self.set_active(nxt)
            return nxt
        return None


# ── Hub 主类 ──────────────────────────────────────────────────────────────────

class VideoCraftHub:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("VideoCraft")
        self.root.geometry("900x600")
        self.root.minsize(600, 400)
        self.root.state("zoomed")   # 启动最大化

        self.project: Project | None = None
        self._recent_menu: tk.Menu | None = None
        self._tool_instances: list = []   # 防止工具实例被 GC 回收
        self._last_snapshot: set = set()  # 上次文件夹快照，用于自动刷新检测
        self._status_var = tk.StringVar() # 状态栏变量（保持向后兼容）

        # Tab 系统
        self._tab_registry: dict[str, str] = {}      # tool_key → tool_key
        self._tab_frames: dict[str, ToolFrame] = {}  # tool_key → ToolFrame
        self._tab_bar: TabBar | None = None
        self._content_area: tk.Frame | None = None   # Tab 内容切换区
        self._welcome_frame: tk.Frame | None = None

        self._build_menu()
        self._build_layout()
        self._show_welcome()
        self._schedule_auto_refresh()

    # ── 菜单 ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Folder...",
                              command=self.open_folder, accelerator="Ctrl+O")
        self._recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Recent Projects", menu=self._recent_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        file_menu.bind("<Map>", lambda e: self._rebuild_recent_menu())
        self.root.bind("<Control-o>", lambda e: self.open_folder())

        # Download
        dl_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="下载", menu=dl_menu)
        dl_menu.add_command(label="yt-dlp 下载器",
                            command=lambda: self.open_tool(
                                "yt-dlp",
                                initial_file=self.project.folder if self.project else None))

        # 语音转字幕
        stt_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="语音转字幕", menu=stt_menu)
        stt_menu.add_command(label="LemonFox API",
                             command=lambda: self.open_tool("speech2text"))

        # 翻译
        tr_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="翻译", menu=tr_menu)
        tr_menu.add_command(label="Gemini 翻译",
                            command=lambda: self.open_tool("translate"))

        # 视频
        vid_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="视频", menu=vid_menu)
        vid_menu.add_command(label="字幕烧录",
                             command=lambda: self.open_tool("subtitle"))
        vid_menu.add_command(label="逐字字幕",
                             command=lambda: self.open_tool("word-subtitle"))
        vid_menu.add_command(label="视频分段",
                             command=lambda: self.open_tool("splitvideo"))
        vid_menu.add_separator()
        vid_menu.add_command(label="提取 MP3",
                             command=lambda: self.open_tool("extract-audio"))
        vid_menu.add_command(label="调整音量",
                             command=lambda: self.open_tool("adjust-volume"))
        vid_menu.add_command(label="视频片段提取",
                             command=lambda: self.open_tool("extract-clip"))
        vid_menu.add_command(label="自动分割视频",
                             command=lambda: self.open_tool("auto-split"))
        vid_menu.add_command(label="码率转换",
                             command=lambda: self.open_tool("convert-bitrate"))

        # 字幕
        sub_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="字幕", menu=sub_menu)
        sub_menu.add_command(label="提取字幕文字",
                             command=lambda: self.open_tool("srt-extract-subtitles"))
        sub_menu.add_command(label="生成分段描述",
                             command=lambda: self.open_tool("srt-gen-segments"))
        sub_menu.add_command(label="提取段落内容",
                             command=lambda: self.open_tool("srt-extract-paragraphs"))
        sub_menu.add_command(label="精炼分段",
                             command=lambda: self.open_tool("srt-refine"))
        sub_menu.add_command(label="生成标题",
                             command=lambda: self.open_tool("srt-gen-titles"))

        # 文字转视频
        t2v_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文字转视频", menu=t2v_menu)
        t2v_menu.add_command(label="① 文字合成语音",
                             command=lambda: self.open_tool("tts"))
        t2v_menu.add_command(label="② 生成字幕 SRT",
                             command=lambda: self.open_tool("tts-srt"))
        t2v_menu.add_command(label="③ 合成视频",
                             command=lambda: self.open_tool("tts-video"))
        t2v_menu.add_separator()
        t2v_menu.add_command(label="每日要闻合成",
                             command=lambda: self.open_tool("daily-news"))

        # AI
        ai_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="AI", menu=ai_menu)
        ai_menu.add_command(label="Router 管理",
                            command=lambda: open_router_manager(self.root))

        # 发布
        pub_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="发布", menu=pub_menu)
        pub_menu.add_command(label="TikTok 发布",
                             command=lambda: self.open_tool("tiktok-publish"))
        pub_menu.add_command(label="YouTube 发布",
                             command=lambda: self.open_tool("youtube-publish"))

        # Help
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="关于 VideoCraft",
                              command=self._show_about)

    def _rebuild_recent_menu(self):
        self._recent_menu.delete(0, "end")
        recents = get_recent_projects()
        if not recents:
            self._recent_menu.add_command(label="（无历史记录）", state="disabled")
        else:
            for path in recents:
                self._recent_menu.add_command(
                    label=path,
                    command=lambda p=path: self.open_folder(p)
                )

    # ── 布局 ──────────────────────────────────────────────────────────────────

    def _build_layout(self):
        # PanedWindow：左 Sidebar + 右内容区
        self._pane = ttk.PanedWindow(self.root, orient="horizontal")
        self._pane.pack(fill="both", expand=True)

        # ── 左：Sidebar ──
        sidebar_frame = tk.Frame(self._pane, width=320, bg="#f5f5f5")
        sidebar_frame.pack_propagate(False)
        self._pane.add(sidebar_frame, weight=0)

        # Sidebar 顶部工具栏
        sb_top = tk.Frame(sidebar_frame, bg="#e8e8e8")
        sb_top.pack(fill="x")
        tk.Label(sb_top, text="资源管理器", font=("", 9, "bold"),
                 bg="#e8e8e8", fg="#555").pack(side="left", padx=8, pady=4)
        tk.Button(sb_top, text="⟳", width=3, relief="flat",
                  command=self.refresh_sidebar,
                  bg="#e8e8e8").pack(side="right", padx=4, pady=2)

        # Treeview
        tree_frame = tk.Frame(sidebar_frame)
        tree_frame.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        self._tree = ttk.Treeview(tree_frame, show="tree",
                                  yscrollcommand=vsb.set, selectmode="browse")
        vsb.config(command=self._tree.yview)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._tree.bind("<Double-1>", self._on_tree_double_click)
        self._tree.bind("<Button-3>", self._on_tree_right_click)
        self._tree.bind("<<TreeviewOpen>>", self._on_tree_open)

        # ── 右：内容区 ──
        self._content = tk.Frame(self._pane, bg="white")
        self._pane.add(self._content, weight=1)

        # Tab 栏（首次打开工具前隐藏）
        self._tab_bar = TabBar(self._content,
                               on_select=self._select_tab,
                               on_close=self._close_tab)
        # 工具内容切换区
        self._content_area = tk.Frame(self._content, bg="white")

        # ── 底部日志面板 ──
        self._build_logpanel()

    # ── 欢迎页 ────────────────────────────────────────────────────────────────

    def _show_welcome(self):
        """隐藏 Tab 系统，显示欢迎页（懒加载）。"""
        self._tab_bar.pack_forget()
        self._content_area.pack_forget()
        if self._welcome_frame is None:
            self._welcome_frame = tk.Frame(self._content, bg="white")
            inner = tk.Frame(self._welcome_frame, bg="white")
            inner.place(relx=0.5, rely=0.45, anchor="center")
            tk.Label(inner, text="VideoCraft", font=("", 22, "bold"),
                     bg="white", fg="#333").pack(pady=(0, 6))
            tk.Label(inner, text="打开一个文件夹以开始工作",
                     font=("", 11), bg="white", fg="#888").pack(pady=(0, 20))
            tk.Button(inner, text="  打开文件夹  ", font=("", 11),
                      command=self.open_folder,
                      bg="#0078d4", fg="white", relief="flat",
                      padx=10, pady=6).pack()
        self._welcome_frame.pack(fill="both", expand=True)

    def _show_tabs(self):
        """隐藏欢迎页，显示 Tab 栏 + 内容区。"""
        if self._welcome_frame:
            self._welcome_frame.pack_forget()
        self._tab_bar.pack(side="top", fill="x")
        self._content_area.pack(fill="both", expand=True)

    def _select_tab(self, key: str):
        """切换到指定 Tab。"""
        for tf in self._tab_frames.values():
            tf.pack_forget()
        if key in self._tab_frames:
            self._tab_frames[key].pack(fill="both", expand=True)
        self._tab_bar.set_active(key)

    def _close_tab(self, key: str):
        """关闭指定 Tab；若无剩余 Tab 则恢复欢迎页。"""
        if key in self._tab_frames:
            self._tab_frames[key].destroy()
            del self._tab_frames[key]
        self._tab_registry.pop(key, None)
        # 从 _tool_instances 中移除对应实例（无法精确匹配时保持原样）
        nxt = self._tab_bar.remove_tab(key)
        if nxt:
            self._select_tab(nxt)
        else:
            self._show_welcome()

    # ── Project 操作 ──────────────────────────────────────────────────────────

    def open_folder(self, path: str = None):
        if path is None:
            path = filedialog.askdirectory(title="打开文件夹")
            if not path:
                return

        if not os.path.isdir(path):
            messagebox.showerror("错误", f"文件夹不存在：\n{path}")
            return

        self.project = Project.open(path)
        add_recent_project(path)
        self.root.title(f"VideoCraft — {self.project.name}")
        self._status_var.set(self.project.folder)
        self._last_snapshot = self._folder_snapshot(self.project.folder)
        self.refresh_sidebar()

    def refresh_sidebar(self):
        self._tree.delete(*self._tree.get_children())
        if self.project is None:
            return

        root_node = self._tree.insert(
            "", "end",
            text=f"  {self.project.name}",
            open=True,
            tags=("folder",)
        )
        for entry in self.project.get_files():
            icon = entry["icon"]
            label = f"  {icon}  {entry['name']}"
            node = self._tree.insert(root_node, "end", text=label,
                                     values=(entry["path"],),
                                     tags=("dir" if entry["is_dir"] else "file",))
            if entry["is_dir"]:
                self._tree.insert(node, "end", tags=("_placeholder",))

    def _schedule_auto_refresh(self):
        """每 2 秒检查文件夹变化，有变化时自动刷新 Sidebar。"""
        if self.project and os.path.isdir(self.project.folder):
            snapshot = self._folder_snapshot(self.project.folder)
            if snapshot != self._last_snapshot:
                self._last_snapshot = snapshot
                self.refresh_sidebar()
        self.root.after(2000, self._schedule_auto_refresh)

    def _folder_snapshot(self, folder: str) -> set:
        """返回文件夹内所有条目的 (名称, 大小, 修改时间) 集合。"""
        result = set()
        try:
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                try:
                    st = os.stat(path)
                    result.add((name, st.st_size, round(st.st_mtime)))
                except OSError:
                    result.add((name,))
        except OSError:
            pass
        return result

    def _on_tree_double_click(self, event):
        item = self._tree.focus()
        vals = self._tree.item(item, "values")
        if vals:
            path = vals[0]
            if os.path.isfile(path):
                os.startfile(path)
            elif os.path.isdir(path):
                is_open = self._tree.item(item, "open")
                self._tree.item(item, open=not is_open)

    def _on_tree_open(self, _event):
        item = self._tree.focus()
        children = self._tree.get_children(item)
        # 如果只有一个占位子节点，替换为真实内容
        if len(children) == 1 and "_placeholder" in self._tree.item(children[0], "tags"):
            self._tree.delete(children[0])
            vals = self._tree.item(item, "values")
            if not vals:
                return
            path = vals[0]
            try:
                names = sorted(os.listdir(path), key=lambda s: s.lower())
            except OSError:
                return
            for name in names:
                full = os.path.join(path, name)
                is_dir = os.path.isdir(full)
                icon = file_icon(name, is_dir)
                node = self._tree.insert(item, "end", text=f"  {icon}  {name}",
                                         values=(full,),
                                         tags=("dir" if is_dir else "file",))
                if is_dir:
                    self._tree.insert(node, "end", tags=("_placeholder",))

    def _on_tree_right_click(self, event):
        item = self._tree.identify_row(event.y)
        if not item:
            return
        self._tree.selection_set(item)
        self._tree.focus(item)

        vals = self._tree.item(item, "values")
        if not vals:
            return
        file_path = vals[0]

        menu = tk.Menu(self.root, tearoff=0)
        ops = get_operations(file_path)

        for op in ops:
            if op.separator_before and menu.index("end") is not None:
                menu.add_separator()
            menu.add_command(
                label=op.label,
                command=lambda o=op, fp=file_path: self._run_operation(o, fp)
            )

        menu.add_separator()
        menu.add_command(
            label="删除",
            command=lambda fp=file_path: self._delete_item(fp)
        )

        menu.tk_popup(event.x_root, event.y_root)

    def _delete_item(self, file_path: str):
        name = os.path.basename(file_path)
        kind = "文件夹" if os.path.isdir(file_path) else "文件"
        confirmed = messagebox.askyesno(
            "确认删除",
            f"将 {kind} 移至回收站：\n\n{name}\n\n确定吗？",
            default="no"
        )
        if not confirmed:
            return
        try:
            import send2trash
            send2trash.send2trash(file_path)
        except ImportError:
            # send2trash 未安装，回退到 Windows Shell API
            import ctypes
            from ctypes import wintypes
            class SHFILEOPSTRUCT(ctypes.Structure):
                _fields_ = [
                    ("hwnd",    wintypes.HWND),
                    ("wFunc",   ctypes.c_uint),
                    ("pFrom",   ctypes.c_wchar_p),
                    ("pTo",     ctypes.c_wchar_p),
                    ("fFlags",  ctypes.c_ushort),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", ctypes.c_wchar_p),
                ]
            FO_DELETE  = 0x0003
            FOF_ALLOWUNDO      = 0x0040
            FOF_NOCONFIRMATION = 0x0010
            FOF_SILENT         = 0x0004
            op = SHFILEOPSTRUCT()
            op.wFunc  = FO_DELETE
            op.pFrom  = file_path + "\0"
            op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
            ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        except Exception as e:
            messagebox.showerror("删除失败", str(e))
            return
        self.refresh_sidebar()

    def _run_operation(self, op, file_path: str):
        if op.handler in ("quick", "common"):
            self._run_quick(op, file_path)
        else:
            self.open_tool(op.tool_key, initial_file=file_path)

    def _run_quick(self, op, file_path: str):
        def task():
            try:
                result = op.func(file_path,
                                 progress_callback=self._update_status)
                if result:
                    self.root.after(0, lambda r=result: self._status_var.set(
                        f"完成: {os.path.basename(r)}"))
            except Exception as e:
                from hub_logger import logger
                self.root.after(0, lambda err=str(e): logger.error(err))
        threading.Thread(target=task, daemon=True).start()

    # ── 日志面板 ─────────────────────────────────────────────────────────────

    def _build_logpanel(self):
        """替代原单行状态栏，显示多行彩色日志。"""
        from hub_logger import logger

        frame = tk.Frame(self.root, bd=1, relief="sunken", bg="#1e1e1e", height=90)
        frame.pack(fill="x", side="bottom")
        frame.pack_propagate(False)

        # 标题行
        title_bar = tk.Frame(frame, bg="#2d2d2d")
        title_bar.pack(fill="x")
        tk.Label(title_bar, text="日志", bg="#2d2d2d", fg="#aaa",
                 font=("", 9), padx=6).pack(side="left")
        tk.Button(title_bar, text="清空", bg="#2d2d2d", fg="#888",
                  relief="flat", font=("", 8), cursor="hand2",
                  command=self._clear_log).pack(side="right", padx=4, pady=1)

        # 日志文本区
        self._log_text = tk.Text(
            frame, bg="#1e1e1e", fg="#d4d4d4",
            font=("Consolas", 9), state="disabled",
            wrap="word", height=4, relief="flat",
            selectbackground="#264f78",
        )
        vsb = tk.Scrollbar(frame, command=self._log_text.yview, bg="#2d2d2d")
        self._log_text.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True, padx=2, pady=(0, 2))

        # 颜色 tag
        self._log_text.tag_configure("ts",      foreground="#555")
        self._log_text.tag_configure("info",    foreground="#d4d4d4")
        self._log_text.tag_configure("warning", foreground="#f0a500")
        self._log_text.tag_configure("error",   foreground="#f44747")

        # 注册 logger 回调
        logger.register_handler(self._on_log)

    def _on_log(self, level: str, msg: str, ts: str):
        """logger 回调（可能来自任意线程），转到主线程追加。"""
        self.root.after(0, self._append_log, level, msg, ts)

    def _append_log(self, level: str, msg: str, ts: str):
        prefix = {"info": "✓", "warning": "⚠", "error": "✗"}.get(level, "·")
        self._log_text.configure(state="normal")
        self._log_text.insert("end", f"{ts} ", "ts")
        self._log_text.insert("end", f"{prefix}  {msg}\n", level)
        self._log_text.configure(state="disabled")
        self._log_text.see("end")

    def _clear_log(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def _update_status(self, msg: str):
        """进度回调（线程安全），写入日志面板。"""
        from hub_logger import logger
        self.root.after(0, lambda m=msg: logger.info(m))

    # ── 工具启动 ──────────────────────────────────────────────────────────────

    def open_tool(self, key: str, initial_file: str = None):
        cfg = TOOL_MAP.get(key)
        if cfg is None:
            messagebox.showerror("错误", f"未知工具：{key}")
            return

        file_path = os.path.join(_SRC, cfg["file"])
        if not os.path.exists(file_path):
            messagebox.showerror("错误", f"工具文件不存在：\n{file_path}")
            return

        if cfg["class"] is None:
            self._open_subprocess(file_path, initial_file=initial_file)
        else:
            self._open_in_tab(file_path, cfg["class"], key,
                              initial_file=initial_file)

    def _open_toplevel(self, file_path: str, class_name: str, initial_file: str = None):
        try:
            mod_name = os.path.splitext(os.path.basename(file_path))[0]
            spec = importlib.util.spec_from_file_location(mod_name, file_path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls  = getattr(mod, class_name)
            win  = tk.Toplevel(self.root)
            win.transient(self.root)
            app  = cls(win, initial_file=initial_file) if initial_file else cls(win)
            self._tool_instances.append(app)
            win.bind("<Destroy>", lambda e, a=app: self._tool_instances.remove(a)
                     if a in self._tool_instances else None)
        except Exception as e:
            messagebox.showerror("启动失败", str(e))

    def _open_in_tab(self, file_path: str, class_name: str, tool_key: str,
                     initial_file: str = None):
        # 去重：已打开则直接切换
        if tool_key in self._tab_registry:
            self._select_tab(tool_key)
            self._show_tabs()
            return
        try:
            mod_name = os.path.splitext(os.path.basename(file_path))[0]
            spec = importlib.util.spec_from_file_location(mod_name, file_path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls  = getattr(mod, class_name)

            tf = ToolFrame(self._content_area)
            tf._set_status_cb = lambda s, k=tool_key: self._tab_bar.set_status(k, s)

            app = cls(tf, initial_file=initial_file) if initial_file else cls(tf)

            label = tf._tool_title or class_name
            self._tab_bar.add_tab(tool_key, label, status="idle")
            self._tab_frames[tool_key]   = tf
            self._tab_registry[tool_key] = tool_key
            self._tool_instances.append(app)

            self._show_tabs()
            self._select_tab(tool_key)
        except Exception as e:
            messagebox.showerror("启动失败", str(e))

    def _open_subprocess(self, file_path: str, initial_file: str = None):
        venv_python = os.path.join(_SRC, "..", "myenv", "Scripts", "python.exe")
        python = venv_python if os.path.exists(venv_python) else sys.executable
        try:
            cmd = [python, file_path]
            if initial_file:
                cmd.append(initial_file)
            subprocess.Popen(cmd)
        except Exception as e:
            messagebox.showerror("启动失败", str(e))

    # ── 关于 ──────────────────────────────────────────────────────────────────

    def _show_about(self):
        messagebox.showinfo(
            "关于 VideoCraft",
            "VideoCraft\n视频生产工具集\n\n"
            "核心流程：下载 → 语音转字幕 → 翻译 → 字幕烧录"
        )


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoCraftHub(root)
    root.mainloop()
