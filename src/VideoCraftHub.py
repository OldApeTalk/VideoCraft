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

from project import Project, add_recent_project, get_recent_projects
from router_manager import open_router_manager
from operations import get_operations

# ── 工具注册表 ────────────────────────────────────────────────────────────────
# class: None → 用 subprocess 启动；有 class 名 → Toplevel 内嵌

_SRC = os.path.dirname(os.path.abspath(__file__))

TOOL_MAP = {
    "yt-dlp":      {"file": "yt-dlp-with simuheader ipv4.py", "class": "YouTubeDownloader"},
    "speech2text": {"file": "Speech2Text-lemonfoxAPI-Online.py", "class": None},
    "translate":   {"file": "Translate-srt-gemini.py",          "class": "TranslateApp"},
    "subtitle":    {"file": "SubtitleTool.py",                   "class": None},
    "srttools":    {"file": "SrtTools.py",                       "class": "YouTubeSegmentsApp"},
    "splitvideo":  {"file": "SplitVideo0.2.py",                  "class": "SplitVideoApp"},
    "videotools":  {"file": "VideoTools.py",                     "class": "VideoToolsGUI"},
    "text2video":  {"file": "text2Video.py",                     "class": "Text2VideoApp"},
}

# ── Hub 主类 ──────────────────────────────────────────────────────────────────

class VideoCraftHub:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("VideoCraft")
        self.root.geometry("900x600")
        self.root.minsize(600, 400)

        self.project: Project | None = None
        self._recent_menu: tk.Menu | None = None
        self._tool_instances: list = []   # 防止工具实例被 GC 回收
        self._last_snapshot: set = set()  # 上次文件夹快照，用于自动刷新检测

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
                            command=lambda: self.open_tool("yt-dlp"))

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

        # 字幕
        sub_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="字幕", menu=sub_menu)
        sub_menu.add_command(label="字幕烧录",
                             command=lambda: self.open_tool("subtitle"))
        sub_menu.add_command(label="SRT 工具",
                             command=lambda: self.open_tool("srttools"))
        sub_menu.add_command(label="视频分段",
                             command=lambda: self.open_tool("splitvideo"))

        # 视频
        vid_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="视频", menu=vid_menu)
        vid_menu.add_command(label="视频工具",
                             command=lambda: self.open_tool("videotools"))
        vid_menu.add_command(label="文字转视频",
                             command=lambda: self.open_tool("text2video"))

        # AI
        ai_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="AI", menu=ai_menu)
        ai_menu.add_command(label="Router 管理",
                            command=lambda: open_router_manager(self.root))

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
        sidebar_frame = tk.Frame(self._pane, width=200, bg="#f5f5f5")
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

        # ── 右：内容区 ──
        self._content = tk.Frame(self._pane, bg="white")
        self._pane.add(self._content, weight=1)

        # ── 底部状态栏 ──
        statusbar = tk.Frame(self.root, bd=1, relief="sunken", bg="#f0f0f0")
        statusbar.pack(fill="x", side="bottom")
        self._status_var = tk.StringVar(value="未打开工程")
        tk.Label(statusbar, textvariable=self._status_var,
                 anchor="w", bg="#f0f0f0", font=("", 9),
                 padx=8, pady=2).pack(fill="x")

    # ── 欢迎页 ────────────────────────────────────────────────────────────────

    def _show_welcome(self):
        for w in self._content.winfo_children():
            w.destroy()
        frame = tk.Frame(self._content, bg="white")
        frame.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(frame, text="VideoCraft", font=("", 22, "bold"),
                 bg="white", fg="#333").pack(pady=(0, 6))
        tk.Label(frame, text="打开一个文件夹以开始工作",
                 font=("", 11), bg="white", fg="#888").pack(pady=(0, 20))
        tk.Button(frame, text="  打开文件夹  ", font=("", 11),
                  command=self.open_folder,
                  bg="#0078d4", fg="white", relief="flat",
                  padx=10, pady=6).pack()

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

        # 清空欢迎页
        for w in self._content.winfo_children():
            w.destroy()

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
            self._tree.insert(root_node, "end", text=label,
                              values=(entry["path"],),
                              tags=("dir" if entry["is_dir"] else "file",))

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
                self.open_folder(path)

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

        menu.tk_popup(event.x_root, event.y_root)

    def _run_operation(self, op, file_path: str):
        if op.handler in ("quick", "common"):
            self._run_quick(op, file_path)
        else:
            self.open_tool(op.tool_key)

    def _run_quick(self, op, file_path: str):
        def task():
            try:
                result = op.func(file_path,
                                 progress_callback=self._update_status)
                if result:
                    self.root.after(0, lambda r=result: self._status_var.set(
                        f"完成: {os.path.basename(r)}"))
            except Exception as e:
                self.root.after(0, lambda err=str(e): messagebox.showerror(
                    "操作失败", err))
        threading.Thread(target=task, daemon=True).start()

    def _update_status(self, msg: str):
        """进度回调，线程安全。"""
        self.root.after(0, lambda m=msg: self._status_var.set(m))

    # ── 工具启动 ──────────────────────────────────────────────────────────────

    def open_tool(self, key: str):
        cfg = TOOL_MAP.get(key)
        if cfg is None:
            messagebox.showerror("错误", f"未知工具：{key}")
            return

        file_path = os.path.join(_SRC, cfg["file"])
        if not os.path.exists(file_path):
            messagebox.showerror("错误", f"工具文件不存在：\n{file_path}")
            return

        if cfg["class"] is None:
            self._open_subprocess(file_path)
        else:
            self._open_toplevel(file_path, cfg["class"])

    def _open_toplevel(self, file_path: str, class_name: str):
        try:
            mod_name = os.path.splitext(os.path.basename(file_path))[0]
            spec = importlib.util.spec_from_file_location(mod_name, file_path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls  = getattr(mod, class_name)
            win  = tk.Toplevel(self.root)
            win.transient(self.root)           # 保持在 Hub 之上，对话框关闭后不被遮挡
            app  = cls(win)
            self._tool_instances.append(app)   # 持有引用，防止 GC
            win.bind("<Destroy>", lambda e, a=app: self._tool_instances.remove(a)
                     if a in self._tool_instances else None)
        except Exception as e:
            messagebox.showerror("启动失败", str(e))

    def _open_subprocess(self, file_path: str):
        venv_python = os.path.join(_SRC, "..", "myenv", "Scripts", "python.exe")
        python = venv_python if os.path.exists(venv_python) else sys.executable
        try:
            subprocess.Popen([python, file_path])
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
