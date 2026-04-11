"""
tools/publish/youtube_publish.py - YouTube 视频发布工具

通过 YouTube Data API v3 将本地视频发布到 YouTube。
功能：OAuth 2.0 授权登录（复用 Google client_secret）、Resumable Upload、
      标题/描述/标签/可见性/播放列表/定时发布。
"""

import glob
import http.server
import json
import os
import secrets
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone
from tkinter import filedialog, messagebox, ttk

import requests

from tools.base import ToolBase

# ── API 端点 ──────────────────────────────────────────────────────────────────
_AUTH_URL    = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL   = "https://oauth2.googleapis.com/token"
_REVOKE_URL  = "https://oauth2.googleapis.com/revoke"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
_YT_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
_YT_PLAYLIST_URL = "https://www.googleapis.com/youtube/v3/playlists"
_YT_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"

_CALLBACK_PORT = 18766
_CALLBACK_PATH = "/callback"
_CHUNK_SIZE    = 10 * 1024 * 1024   # 10 MB

_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]

# ── 路径 ──────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_KEYS_DIR = os.path.normpath(os.path.join(_HERE, "../../../keys"))
_TOKEN_FILE = os.path.join(_KEYS_DIR, "youtube_token.json")

_PRIVACY_OPTIONS = [
    ("公开", "public"),
    ("不公开列出", "unlisted"),
    ("私享", "private"),
]


# ── 读取 Google client_secret ──────────────────────────────────────────────────
def _load_client_secret(path: str = "") -> dict:
    """从指定路径或 keys/ 目录首个 client_secret_*.json 读取。"""
    if not path or not os.path.isfile(path):
        pattern = os.path.join(_KEYS_DIR, "client_secret_*.json")
        matches = glob.glob(pattern)
        if not matches:
            return {}
        path = matches[0]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("installed", data.get("web", {}))
    except Exception:
        return {}


# ── OAuth 回调服务器 ───────────────────────────────────────────────────────────
class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """接收 Google OAuth 重定向，提取 code 参数。"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == _CALLBACK_PATH:
            params = urllib.parse.parse_qs(parsed.query)
            self.server._auth_code  = params.get("code",  [None])[0]
            self.server._auth_error = params.get("error", [None])[0]
            body = "授权完成，请关闭此页面返回应用。".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # 静默


# ── 自动换行 Frame ────────────────────────────────────────────────────────────
class _WrapFrame(tk.Frame):
    """子控件自动换行的容器，类似 HTML flex-wrap。"""

    def __init__(self, master, h_gap=6, v_gap=4, **kwargs):
        super().__init__(master, **kwargs)
        self._h_gap = h_gap
        self._v_gap = v_gap
        self.bind("<Configure>", self._rewrap)

    def _rewrap(self, _event=None):
        self.update_idletasks()
        width = self.winfo_width()
        if width <= 1:
            return
        x = y = 0
        row_h = 0
        for child in self.winfo_children():
            cw = child.winfo_reqwidth()
            ch = child.winfo_reqheight()
            if x + cw > width and x > 0:
                x = 0
                y += row_h + self._v_gap
                row_h = 0
            child.place(x=x, y=y)
            x += cw + self._h_gap
            row_h = max(row_h, ch)
        total_h = y + row_h if self.winfo_children() else 0
        self.configure(height=max(total_h + self._v_gap, 24))


# ── 主工具类 ──────────────────────────────────────────────────────────────────
class YouTubePublishApp(ToolBase):
    """YouTube 视频发布工具，嵌入 Hub Tab。"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title("YouTube 发布")
        master.geometry("680x780")

        self._creds: dict = {}          # 运行时凭证缓存
        self._client: dict = {}         # client_id / client_secret
        self._playlists: list = []      # [(title, playlist_id), ...]
        self._sched_timer = None        # threading.Timer
        self._login_lock = threading.Lock()

        self._load_credentials()
        self._build_ui()

        if initial_file and os.path.isfile(initial_file):
            self._var_video.set(initial_file)

        # 如果已登录，异步拉取播放列表
        if self._creds.get("access_token"):
            threading.Thread(target=self._fetch_playlists, daemon=True).start()

    # ── 凭证 I/O ───────────────────────────────────────────────────────────
    def _load_credentials(self):
        self._creds = {}
        if os.path.isfile(_TOKEN_FILE):
            try:
                with open(_TOKEN_FILE, "r", encoding="utf-8") as f:
                    self._creds = json.load(f)
            except Exception:
                pass
        # 优先使用上次选择的密钥文件路径
        self._client = _load_client_secret(self._creds.get("client_secret_path", ""))

    def _save_credentials(self):
        os.makedirs(_KEYS_DIR, exist_ok=True)
        with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(self._creds, f, ensure_ascii=False, indent=2)

    # ── UI 构建 ────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = self.master
        pad = {"padx": 10, "pady": 4}

        # ── 账号区 ─────────────────────────────────────────────────────
        acct_frame = ttk.LabelFrame(root, text="账号")
        acct_frame.pack(fill="x", **pad)

        self._lbl_status = ttk.Label(
            acct_frame, text=self._status_text(), foreground=self._status_color()
        )
        self._lbl_status.grid(row=0, column=0, sticky="w", padx=8, pady=6)

        ttk.Button(acct_frame, text="授权登录", command=self._on_login).grid(row=0, column=1, padx=4)
        ttk.Button(acct_frame, text="注销", command=self._on_logout).grid(row=0, column=2, padx=4)

        # 密钥文件行
        ttk.Label(acct_frame, text="密钥文件").grid(row=1, column=0, sticky="w", padx=8, pady=(0, 6))
        self._lbl_secret = ttk.Label(acct_frame, text=self._secret_file_text(), foreground="#555")
        self._lbl_secret.grid(row=1, column=1, sticky="w", padx=4)
        ttk.Button(acct_frame, text="选择…", command=self._on_choose_secret).grid(row=1, column=2, padx=4)

        # ── 发布信息区 ─────────────────────────────────────────────────
        info_frame = ttk.LabelFrame(root, text="发布信息")
        info_frame.pack(fill="x", **pad)
        info_frame.columnconfigure(1, weight=1)

        ttk.Label(info_frame, text="视频文件").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self._var_video = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self._var_video).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(info_frame, text="浏览", command=self._browse_video).grid(row=0, column=2, padx=4)

        ttk.Label(info_frame, text="标题").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self._var_title = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self._var_title).grid(row=1, column=1, columnspan=2, sticky="ew", padx=4)
        ttk.Label(info_frame, text="最多 100 字符", foreground="#888").grid(row=2, column=1, sticky="w", padx=4)

        ttk.Label(info_frame, text="描述").grid(row=3, column=0, sticky="nw", padx=8, pady=4)
        self._txt_desc = tk.Text(info_frame, height=4, wrap="word", font=("Segoe UI", 9))
        self._txt_desc.grid(row=3, column=1, columnspan=2, sticky="ew", padx=4, pady=2)

        ttk.Label(info_frame, text="标签").grid(row=4, column=0, sticky="w", padx=8, pady=4)
        self._var_tags = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self._var_tags).grid(row=4, column=1, columnspan=2, sticky="ew", padx=4)
        ttk.Label(info_frame, text="逗号分隔，如: travel,vlog,youtube", foreground="#888").grid(row=5, column=1, sticky="w", padx=4)

        # ── 可见性区 ───────────────────────────────────────────────────
        vis_frame = ttk.LabelFrame(root, text="可见性")
        vis_frame.pack(fill="x", **pad)
        self._var_privacy = tk.StringVar(value="private")
        for label, value in _PRIVACY_OPTIONS:
            ttk.Radiobutton(vis_frame, text=label, variable=self._var_privacy, value=value).pack(
                side="left", padx=12, pady=6
            )

        # ── 播放列表区 ─────────────────────────────────────────────────
        pl_frame = ttk.LabelFrame(root, text="添加到播放列表（可选，可多选）")
        pl_frame.pack(fill="x", **pad)

        pl_top = tk.Frame(pl_frame)
        pl_top.pack(fill="x", padx=8, pady=4)

        self._pl_inner = _WrapFrame(pl_top)
        self._pl_inner.pack(side="left", fill="x", expand=True)

        ttk.Button(pl_top, text="刷新", command=self._on_refresh_playlists).pack(
            side="right", padx=4)

        self._pl_vars: dict[str, tk.BooleanVar] = {}   # playlist_id → BooleanVar

        # ── 定时发布区 ─────────────────────────────────────────────────
        sched_frame = ttk.LabelFrame(root, text="定时发布（需保持应用运行）")
        sched_frame.pack(fill="x", **pad)
        sched_frame.columnconfigure(3, weight=1)

        self._var_sched_enable = tk.BooleanVar(value=False)
        ttk.Checkbutton(sched_frame, text="启用", variable=self._var_sched_enable,
                        command=self._on_sched_toggle).grid(row=0, column=0, padx=8, pady=6)

        ttk.Label(sched_frame, text="日期 (YYYY-MM-DD)").grid(row=0, column=1, padx=4)
        self._var_sched_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self._entry_date = ttk.Entry(sched_frame, textvariable=self._var_sched_date, width=12, state="disabled")
        self._entry_date.grid(row=0, column=2, padx=4)

        ttk.Label(sched_frame, text="时间 (HH:MM)").grid(row=0, column=3, padx=4)
        self._var_sched_time = tk.StringVar(value="09:00")
        self._entry_time = ttk.Entry(sched_frame, textvariable=self._var_sched_time, width=8, state="disabled")
        self._entry_time.grid(row=0, column=4, padx=4)

        self._lbl_countdown = ttk.Label(sched_frame, text="", foreground="#555")
        self._lbl_countdown.grid(row=1, column=0, columnspan=5, sticky="w", padx=8, pady=2)

        # ── 操作按钮 ───────────────────────────────────────────────────
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", padx=10, pady=6)
        self._btn_publish = ttk.Button(btn_frame, text="立即发布", command=self._on_publish)
        self._btn_publish.pack(side="left", padx=4)
        self._btn_cancel_sched = ttk.Button(btn_frame, text="取消排队",
                                            command=self._on_cancel_sched, state="disabled")
        self._btn_cancel_sched.pack(side="left", padx=4)

        # ── 进度条 ─────────────────────────────────────────────────────
        prog_frame = ttk.Frame(root)
        prog_frame.pack(fill="x", padx=10, pady=2)
        self._progress = ttk.Progressbar(prog_frame, mode="determinate", maximum=100)
        self._progress.pack(fill="x")
        self._lbl_prog = ttk.Label(prog_frame, text="")
        self._lbl_prog.pack(anchor="w")

        # ── 日志区 ─────────────────────────────────────────────────────
        log_frame = ttk.LabelFrame(root, text="日志")
        log_frame.pack(fill="both", expand=True, **pad)
        self._log_text = tk.Text(log_frame, height=8, state="disabled", wrap="word",
                                 font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
                                 insertbackground="white")
        scroll = ttk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True)

    # ── 密钥文件选择 ───────────────────────────────────────────────────────
    def _secret_file_text(self) -> str:
        path = self._creds.get("client_secret_path", "")
        if path and os.path.isfile(path):
            return os.path.basename(path)
        # 检查是否自动找到了文件
        if self._client.get("client_id"):
            matches = glob.glob(os.path.join(_KEYS_DIR, "client_secret_*.json"))
            return os.path.basename(matches[0]) + "（自动）" if matches else "未选择"
        return "未选择"

    def _on_choose_secret(self):
        path = filedialog.askopenfilename(
            title="选择 Google OAuth 密钥文件",
            initialdir=_KEYS_DIR,
            filetypes=[("JSON 密钥文件", "*.json"), ("所有文件", "*.*")],
        )
        if not path:
            return
        client = _load_client_secret(path)
        if not client.get("client_id"):
            messagebox.showwarning("提示", "所选文件不是有效的 Google OAuth client_secret JSON。")
            return
        self._client = client
        self._creds["client_secret_path"] = path
        self._save_credentials()
        self._lbl_secret.config(text=os.path.basename(path))
        self._log_ui(f"已切换密钥文件: {os.path.basename(path)}")

    # ── 状态辅助 ───────────────────────────────────────────────────────────
    def _status_text(self) -> str:
        at = self._creds.get("access_token")
        email = self._creds.get("email", "")
        if at:
            return f"已登录  {email}" if email else "已登录"
        return "未登录"

    def _status_color(self) -> str:
        return "#228B22" if self._creds.get("access_token") else "#CC3333"

    def _refresh_status_label(self):
        self._lbl_status.config(text=self._status_text(), foreground=self._status_color())

    def _log_ui(self, msg: str):
        def _append():
            self._log_text.config(state="normal")
            self._log_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            self._log_text.see("end")
            self._log_text.config(state="disabled")
        self.master.after(0, _append)

    def _set_progress(self, pct: int, text: str = ""):
        def _update():
            self._progress["value"] = pct
            self._lbl_prog.config(text=text)
        self.master.after(0, _update)

    # ── 事件处理 ───────────────────────────────────────────────────────────
    def _browse_video(self):
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.mov *.mkv *.webm *.avi"), ("所有文件", "*.*")]
        )
        if path:
            self._var_video.set(path)

    def _on_sched_toggle(self):
        state = "normal" if self._var_sched_enable.get() else "disabled"
        self._entry_date.config(state=state)
        self._entry_time.config(state=state)
        if not self._var_sched_enable.get():
            self._lbl_countdown.config(text="")

    def _on_login(self):
        if not self._client.get("client_id"):
            messagebox.showinfo("提示", "未找到 Google OAuth client_secret 文件，\n"
                                "请将 client_secret_*.json 放入 keys/ 目录。")
            return
        if not self._login_lock.acquire(blocking=False):
            self._log_ui("授权流程正在进行中，请稍候...")
            return
        threading.Thread(target=self._do_login, daemon=True).start()

    def _on_logout(self):
        token = self._creds.get("access_token", "")
        if token:
            try:
                requests.post(_REVOKE_URL, params={"token": token}, timeout=10)
            except Exception:
                pass
        self._creds = {}
        self._save_credentials()
        self._playlists = []
        self.master.after(0, self._refresh_status_label)
        self.master.after(0, lambda: self._cmb_playlist.configure(values=["（不添加）"]))
        self.master.after(0, lambda: self._cmb_playlist.set("（不添加）"))
        self._log_ui("已注销。")

    def _on_publish(self):
        video = self._var_video.get().strip()
        if not video or not os.path.isfile(video):
            messagebox.showwarning("提示", "请先选择有效的视频文件。")
            return
        if not self._ensure_token():
            messagebox.showwarning("提示", "请先完成授权登录。")
            return

        if self._var_sched_enable.get():
            self._schedule_publish()
        else:
            self.set_busy()
            threading.Thread(target=self._do_upload, daemon=True).start()

    def _on_cancel_sched(self):
        if self._sched_timer:
            self._sched_timer.cancel()
            self._sched_timer = None
        self._lbl_countdown.config(text="已取消排队。")
        self._btn_cancel_sched.config(state="disabled")
        self._btn_publish.config(state="normal")
        self.set_idle()
        self._log_ui("定时发布已取消。")

    def _on_refresh_playlists(self):
        if not self._ensure_token():
            messagebox.showwarning("提示", "请先登录。")
            return
        threading.Thread(target=self._fetch_playlists, daemon=True).start()

    # ── OAuth 流 ───────────────────────────────────────────────────────────
    def _do_login(self):
        self._log_ui("开始 Google OAuth 授权流程...")
        try:
            state = secrets.token_hex(16)
            redirect_uri = f"http://127.0.0.1:{_CALLBACK_PORT}{_CALLBACK_PATH}"

            params = urllib.parse.urlencode({
                "client_id": self._client["client_id"],
                "response_type": "code",
                "scope": " ".join(_SCOPES),
                "redirect_uri": redirect_uri,
                "state": state,
                "access_type": "offline",
                "prompt": "consent",   # 强制返回 refresh_token
            })
            auth_url = f"{_AUTH_URL}?{params}"

            server = http.server.HTTPServer(("127.0.0.1", _CALLBACK_PORT), _CallbackHandler)
            server._auth_code  = None
            server._auth_error = None
            server.allow_reuse_address = True

            srv_thread = threading.Thread(target=server.serve_forever, daemon=True)
            srv_thread.start()

            self._log_ui("正在打开浏览器授权页...")
            webbrowser.open(auth_url)

            # 等待回调（最多 3 分钟）
            deadline = time.time() + 180
            while time.time() < deadline:
                if server._auth_code or server._auth_error:
                    break
                time.sleep(0.5)
            server.shutdown()
            server.server_close()

            if server._auth_error:
                self._log_ui(f"授权失败: {server._auth_error}")
                return
            if not server._auth_code:
                self._log_ui("授权超时，请重试。")
                return

            # 换取 token
            self._log_ui("正在换取 Access Token...")
            resp = requests.post(_TOKEN_URL, data={
                "code": server._auth_code,
                "client_id": self._client["client_id"],
                "client_secret": self._client["client_secret"],
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }, timeout=30)
            resp.raise_for_status()
            token_data = resp.json()

            self._creds.update({
                "access_token":  token_data["access_token"],
                "refresh_token": token_data.get("refresh_token", ""),
                "expires_at":    time.time() + token_data.get("expires_in", 3600) - 60,
            })

            # 获取用户信息
            info_resp = requests.get(_USERINFO_URL, headers=self._auth_headers(), timeout=10)
            if info_resp.ok:
                self._creds["email"] = info_resp.json().get("email", "")

            self._save_credentials()
            self._log_ui(f"授权成功！已登录为 {self._creds.get('email', '（未知）')}")
            self.master.after(0, self._refresh_status_label)

            # 登录完成后拉取播放列表
            self._fetch_playlists()

        except Exception as e:
            self._log_ui(f"登录出错: {e}")
            self.log_error(f"YouTube login error: {e}")
        finally:
            self._login_lock.release()

    # ── Token 刷新 ─────────────────────────────────────────────────────────
    def _ensure_token(self) -> bool:
        if not self._creds.get("access_token"):
            return False
        if time.time() < self._creds.get("expires_at", 0):
            return True

        rt = self._creds.get("refresh_token")
        if not rt:
            return False
        try:
            resp = requests.post(_TOKEN_URL, data={
                "client_id": self._client["client_id"],
                "client_secret": self._client["client_secret"],
                "refresh_token": rt,
                "grant_type": "refresh_token",
            }, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            self._creds.update({
                "access_token": data["access_token"],
                "expires_at": time.time() + data.get("expires_in", 3600) - 60,
            })
            self._save_credentials()
            self._log_ui("Access Token 已自动刷新。")
            return True
        except Exception as e:
            self._log_ui(f"Token 刷新失败: {e}")
            return False

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._creds['access_token']}"}

    # ── 播放列表 ───────────────────────────────────────────────────────────
    def _fetch_playlists(self):
        try:
            resp = requests.get(
                _YT_PLAYLIST_URL,
                params={"part": "snippet", "mine": "true", "maxResults": 50},
                headers=self._auth_headers(),
                timeout=30,
            )
            if not resp.ok:
                self._log_ui(f"拉取播放列表失败: HTTP {resp.status_code} - {resp.json().get('error', {}).get('message', resp.text[:100])}")
                return
            items = resp.json().get("items", [])
            self._playlists = [
                (it["snippet"]["title"], it["id"]) for it in items
            ]
            self.master.after(0, self._rebuild_playlist_checkboxes)
            self._log_ui(f"已加载 {len(self._playlists)} 个播放列表。")
        except Exception as e:
            self._log_ui(f"拉取播放列表失败: {e}")

    def _rebuild_playlist_checkboxes(self):
        for widget in self._pl_inner.winfo_children():
            widget.destroy()
        self._pl_vars.clear()
        if not self._playlists:
            tk.Label(self._pl_inner, text="（暂无播放列表）", foreground="#888").place(x=0, y=4)
            self._pl_inner.configure(height=28)
            return
        for title, pid in self._playlists:
            var = tk.BooleanVar(value=False)
            self._pl_vars[pid] = var
            ttk.Checkbutton(self._pl_inner, text=title, variable=var)
        self._pl_inner._rewrap()

    def _get_selected_playlist_ids(self) -> list[str]:
        return [pid for pid, var in self._pl_vars.items() if var.get()]

    # ── Resumable Upload ───────────────────────────────────────────────────
    def _do_upload(self):
        video_path = self._var_video.get().strip()
        title = self._var_title.get().strip()[:100] or os.path.basename(video_path)
        description = self._txt_desc.get("1.0", "end-1c").strip()
        tags_raw = self._var_tags.get().strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
        privacy = self._var_privacy.get()

        file_size = os.path.getsize(video_path)

        video_body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "22",   # People & Blogs（通用默认）
            },
            "status": {
                "privacyStatus": privacy,
            },
        }

        try:
            self._log_ui(f"初始化 Resumable Upload... 文件大小: {file_size / 1024 / 1024:.1f} MB")
            self._set_progress(0, "初始化上传...")

            # Step 1: 初始化 resumable upload，获取 upload URI
            init_resp = requests.post(
                _YT_UPLOAD_URL,
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={
                    **self._auth_headers(),
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": "video/*",
                    "X-Upload-Content-Length": str(file_size),
                },
                json=video_body,
                timeout=30,
            )
            init_resp.raise_for_status()
            upload_uri = init_resp.headers.get("Location")
            if not upload_uri:
                self._log_ui("未获取到上传 URI，初始化失败。")
                self.set_idle()
                return
            self._log_ui("上传 URI 已获取，开始分块上传...")

            # Step 2: 分块上传
            video_id = None
            with open(video_path, "rb") as f:
                offset = 0
                chunk_num = 0
                total_chunks = max(1, -(-file_size // _CHUNK_SIZE))  # ceil division

                while offset < file_size:
                    chunk = f.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    end = offset + len(chunk) - 1
                    content_range = f"bytes {offset}-{end}/{file_size}"

                    put_resp = requests.put(
                        upload_uri,
                        headers={
                            "Content-Length": str(len(chunk)),
                            "Content-Range": content_range,
                        },
                        data=chunk,
                        timeout=120,
                    )

                    if put_resp.status_code in (200, 201):
                        # 上传完成
                        resp_json = put_resp.json()
                        video_id = resp_json.get("id")
                        self._set_progress(95, "上传完成，处理中...")
                        self._log_ui(f"视频上传完成！video_id: {video_id}")
                        break
                    elif put_resp.status_code == 308:
                        # 继续上传
                        chunk_num += 1
                        pct = int(min(offset + len(chunk), file_size) / file_size * 90)
                        self._set_progress(pct, f"上传块 {chunk_num}/{total_chunks}...")
                        self._log_ui(f"已上传至 {end + 1}/{file_size} 字节")
                        offset += len(chunk)
                    else:
                        self._log_ui(f"上传出错: HTTP {put_resp.status_code} - {put_resp.text[:200]}")
                        self.set_idle()
                        return

            if not video_id:
                self._log_ui("未获取到 video_id，请检查上传状态。")
                self.set_idle()
                return

            # Step 3: 添加到播放列表（可选，多选）
            for playlist_id in self._get_selected_playlist_ids():
                self._add_to_playlist(video_id, playlist_id)

            self._set_progress(100, "发布成功！")
            self._log_ui(f"视频已成功发布！YouTube 链接: https://youtu.be/{video_id}")
            self.set_done()

        except requests.HTTPError as e:
            self._log_ui(f"HTTP 错误: {e.response.status_code} - {e.response.text[:300]}")
            self.log_error(f"YouTube upload HTTP error: {e}")
            self.set_idle()
        except Exception as e:
            self._log_ui(f"上传出错: {e}")
            self.log_error(f"YouTube upload error: {e}")
            self.set_idle()

    def _add_to_playlist(self, video_id: str, playlist_id: str):
        try:
            resp = requests.post(
                _YT_PLAYLIST_ITEMS_URL,
                params={"part": "snippet"},
                headers={**self._auth_headers(), "Content-Type": "application/json"},
                json={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
                timeout=30,
            )
            if resp.ok:
                self._log_ui("已添加到播放列表。")
            else:
                self._log_ui(f"添加到播放列表失败: {resp.status_code}")
        except Exception as e:
            self._log_ui(f"添加播放列表出错: {e}")

    # ── 定时发布 ───────────────────────────────────────────────────────────
    def _schedule_publish(self):
        date_str = self._var_sched_date.get().strip()
        time_str = self._var_sched_time.get().strip()
        try:
            target = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showwarning("提示", "日期格式应为 YYYY-MM-DD，时间格式应为 HH:MM。")
            return

        delay = (target - datetime.now()).total_seconds()
        if delay <= 0:
            messagebox.showwarning("提示", "定时时间必须晚于当前时间。")
            return

        self._log_ui(f"已排队定时发布，将于 {target.strftime('%Y-%m-%d %H:%M')} 发布（{delay/60:.1f} 分钟后）。")
        self._btn_publish.config(state="disabled")
        self._btn_cancel_sched.config(state="normal")
        self.set_busy()

        self._sched_timer = threading.Timer(delay, self._on_sched_fire)
        self._sched_timer.daemon = True
        self._sched_timer.start()
        self._start_countdown(target)

    def _on_sched_fire(self):
        self._sched_timer = None
        self._log_ui("定时发布触发！")
        self.master.after(0, lambda: self._btn_cancel_sched.config(state="disabled"))
        self.master.after(0, lambda: self._btn_publish.config(state="normal"))
        self.master.after(0, lambda: self._lbl_countdown.config(text=""))
        self._do_upload()

    def _start_countdown(self, target: datetime):
        def _tick():
            remaining = (target - datetime.now()).total_seconds()
            if self._sched_timer is None:
                return
            if remaining <= 0:
                self._lbl_countdown.config(text="即将发布...")
                return
            h = int(remaining // 3600)
            m = int((remaining % 3600) // 60)
            s = int(remaining % 60)
            self._lbl_countdown.config(text=f"距离发布: {h:02d}:{m:02d}:{s:02d}")
            self.master.after(1000, _tick)
        self.master.after(1000, _tick)
