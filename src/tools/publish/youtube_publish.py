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

from hub_logger import logger
from i18n import tr
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

def _privacy_options():
    """Build the visibility option list with current-locale labels."""
    return [
        (tr("tool.youtube.vis_public"),   "public"),
        (tr("tool.youtube.vis_unlisted"), "unlisted"),
        (tr("tool.youtube.vis_private"),  "private"),
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
            body = tr("tool.publish.common.oauth_done_page").encode("utf-8")
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
        master.title(tr("tool.youtube.title"))
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
            except Exception as e:
                logger.error(f"加载 YouTube 凭据失败 ({_TOKEN_FILE}): {e}")
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

        # ── Account ──
        acct_frame = ttk.LabelFrame(root, text=tr("tool.publish.common.account"))
        acct_frame.pack(fill="x", **pad)

        self._lbl_status = ttk.Label(
            acct_frame, text=self._status_text(), foreground=self._status_color()
        )
        self._lbl_status.grid(row=0, column=0, sticky="w", padx=8, pady=6)

        ttk.Button(acct_frame, text=tr("tool.publish.common.btn_login"),
                   command=self._on_login).grid(row=0, column=1, padx=4)
        ttk.Button(acct_frame, text=tr("tool.publish.common.btn_logout"),
                   command=self._on_logout).grid(row=0, column=2, padx=4)

        # Client secret row
        ttk.Label(acct_frame, text=tr("tool.youtube.secret_file_label")).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 6))
        self._lbl_secret = ttk.Label(acct_frame, text=self._secret_file_text(), foreground="#555")
        self._lbl_secret.grid(row=1, column=1, sticky="w", padx=4)
        ttk.Button(acct_frame, text=tr("tool.youtube.btn_choose_secret"),
                   command=self._on_choose_secret).grid(row=1, column=2, padx=4)

        # ── Publish info ──
        info_frame = ttk.LabelFrame(root, text=tr("tool.publish.common.info"))
        info_frame.pack(fill="x", **pad)
        info_frame.columnconfigure(1, weight=1)

        ttk.Label(info_frame, text=tr("tool.publish.common.video_file")).grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self._var_video = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self._var_video).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(info_frame, text=tr("tool.publish.common.browse"),
                   command=self._browse_video).grid(row=0, column=2, padx=4)

        ttk.Label(info_frame, text=tr("tool.publish.common.title_label")).grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self._var_title = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self._var_title).grid(row=1, column=1, columnspan=2, sticky="ew", padx=4)
        ttk.Label(info_frame, text=tr("tool.youtube.title_hint"), foreground="#888").grid(row=2, column=1, sticky="w", padx=4)

        ttk.Label(info_frame, text=tr("tool.youtube.desc_label")).grid(row=3, column=0, sticky="nw", padx=8, pady=4)
        self._txt_desc = tk.Text(info_frame, height=4, wrap="word", font=("Segoe UI", 9))
        self._txt_desc.grid(row=3, column=1, columnspan=2, sticky="ew", padx=4, pady=2)

        ttk.Label(info_frame, text=tr("tool.youtube.tags_label")).grid(row=4, column=0, sticky="w", padx=8, pady=4)
        self._var_tags = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self._var_tags).grid(row=4, column=1, columnspan=2, sticky="ew", padx=4)
        ttk.Label(info_frame, text=tr("tool.youtube.tags_hint"), foreground="#888").grid(row=5, column=1, sticky="w", padx=4)

        # ── Visibility ──
        vis_frame = ttk.LabelFrame(root, text=tr("tool.youtube.visibility_frame"))
        vis_frame.pack(fill="x", **pad)
        self._var_privacy = tk.StringVar(value="private")
        for label, value in _privacy_options():
            ttk.Radiobutton(vis_frame, text=label, variable=self._var_privacy, value=value).pack(
                side="left", padx=12, pady=6
            )

        # ── Playlists ──
        pl_frame = ttk.LabelFrame(root, text=tr("tool.youtube.playlist_frame"))
        pl_frame.pack(fill="x", **pad)

        pl_top = tk.Frame(pl_frame)
        pl_top.pack(fill="x", padx=8, pady=4)

        self._pl_inner = _WrapFrame(pl_top)
        self._pl_inner.pack(side="left", fill="x", expand=True)

        ttk.Button(pl_top, text=tr("tool.youtube.btn_refresh"),
                   command=self._on_refresh_playlists).pack(side="right", padx=4)

        self._pl_vars: dict[str, tk.BooleanVar] = {}   # playlist_id → BooleanVar

        # ── Schedule ──
        sched_frame = ttk.LabelFrame(root, text=tr("tool.publish.common.schedule"))
        sched_frame.pack(fill="x", **pad)
        sched_frame.columnconfigure(3, weight=1)

        self._var_sched_enable = tk.BooleanVar(value=False)
        ttk.Checkbutton(sched_frame, text=tr("tool.publish.common.enable"), variable=self._var_sched_enable,
                        command=self._on_sched_toggle).grid(row=0, column=0, padx=8, pady=6)

        ttk.Label(sched_frame, text=tr("tool.publish.common.date_label")).grid(row=0, column=1, padx=4)
        self._var_sched_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self._entry_date = ttk.Entry(sched_frame, textvariable=self._var_sched_date, width=12, state="disabled")
        self._entry_date.grid(row=0, column=2, padx=4)

        ttk.Label(sched_frame, text=tr("tool.publish.common.time_label")).grid(row=0, column=3, padx=4)
        self._var_sched_time = tk.StringVar(value="09:00")
        self._entry_time = ttk.Entry(sched_frame, textvariable=self._var_sched_time, width=8, state="disabled")
        self._entry_time.grid(row=0, column=4, padx=4)

        self._lbl_countdown = ttk.Label(sched_frame, text="", foreground="#555")
        self._lbl_countdown.grid(row=1, column=0, columnspan=5, sticky="w", padx=8, pady=2)

        # ── Action buttons ──
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", padx=10, pady=6)
        self._btn_publish = ttk.Button(btn_frame, text=tr("tool.publish.common.btn_publish_now"),
                                       command=self._on_publish)
        self._btn_publish.pack(side="left", padx=4)
        self._btn_cancel_sched = ttk.Button(btn_frame, text=tr("tool.publish.common.btn_cancel_sched"),
                                            command=self._on_cancel_sched, state="disabled")
        self._btn_cancel_sched.pack(side="left", padx=4)

        # ── Progress ──
        prog_frame = ttk.Frame(root)
        prog_frame.pack(fill="x", padx=10, pady=2)
        self._progress = ttk.Progressbar(prog_frame, mode="determinate", maximum=100)
        self._progress.pack(fill="x")
        self._lbl_prog = ttk.Label(prog_frame, text="")
        self._lbl_prog.pack(anchor="w")

        # ── Log ──
        log_frame = ttk.LabelFrame(root, text=tr("tool.publish.common.log_frame"))
        log_frame.pack(fill="both", expand=True, **pad)
        self._log_text = tk.Text(log_frame, height=8, state="disabled", wrap="word",
                                 font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
                                 insertbackground="white")
        scroll = ttk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True)

    # ── Client secret selection ──
    def _secret_file_text(self) -> str:
        path = self._creds.get("client_secret_path", "")
        if path and os.path.isfile(path):
            return os.path.basename(path)
        # Check if auto-detected
        if self._client.get("client_id"):
            matches = glob.glob(os.path.join(_KEYS_DIR, "client_secret_*.json"))
            return (tr("tool.youtube.secret_auto", name=os.path.basename(matches[0]))
                    if matches else tr("tool.youtube.secret_none"))
        return tr("tool.youtube.secret_none")

    def _on_choose_secret(self):
        path = filedialog.askopenfilename(
            title=tr("tool.youtube.dialog_secret_title"),
            initialdir=_KEYS_DIR,
            filetypes=[(tr("tool.youtube.filter_json"), "*.json"),
                       (tr("tool.publish.common.filter_all"), "*.*")],
        )
        if not path:
            return
        client = _load_client_secret(path)
        if not client.get("client_id"):
            messagebox.showwarning(tr("dialog.common.info"),
                                   tr("tool.youtube.warn_invalid_secret"))
            return
        self._client = client
        self._creds["client_secret_path"] = path
        self._save_credentials()
        self._lbl_secret.config(text=os.path.basename(path))
        self._log_ui(tr("tool.youtube.log_secret_switched", filename=os.path.basename(path)))

    # ── Status helpers ──
    def _status_text(self) -> str:
        at = self._creds.get("access_token")
        email = self._creds.get("email", "")
        if at:
            return (tr("tool.youtube.status_logged_in_email", email=email) if email
                    else tr("tool.publish.common.status_logged_in"))
        return tr("tool.publish.common.status_not_logged_in")

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
            title=tr("tool.publish.common.dialog_select_video"),
            filetypes=[(tr("tool.publish.common.filter_video"), "*.mp4 *.mov *.mkv *.webm *.avi"),
                       (tr("tool.publish.common.filter_all"), "*.*")]
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
            messagebox.showinfo(tr("dialog.common.info"),
                                tr("tool.youtube.warn_no_client_secret"))
            return
        if not self._login_lock.acquire(blocking=False):
            self._log_ui(tr("tool.youtube.log_auth_in_progress"))
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
        self.master.after(0, lambda: self._cmb_playlist.configure(values=[tr("tool.youtube.playlist_none")]))
        self.master.after(0, lambda: self._cmb_playlist.set(tr("tool.youtube.playlist_none")))
        self._log_ui(tr("tool.youtube.log_logout"))

    def _on_publish(self):
        video = self._var_video.get().strip()
        if not video or not os.path.isfile(video):
            messagebox.showwarning(tr("dialog.common.info"),
                                   tr("tool.publish.common.warn_no_video"))
            return
        if not self._ensure_token():
            messagebox.showwarning(tr("dialog.common.info"),
                                   tr("tool.publish.common.warn_no_login"))
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
        self._lbl_countdown.config(text=tr("tool.publish.common.sched_cancelled"))
        self._btn_cancel_sched.config(state="disabled")
        self._btn_publish.config(state="normal")
        self.set_idle()
        self._log_ui(tr("tool.publish.common.sched_cancelled_log"))

    def _on_refresh_playlists(self):
        if not self._ensure_token():
            messagebox.showwarning(tr("dialog.common.info"),
                                   tr("tool.youtube.warn_need_login"))
            return
        threading.Thread(target=self._fetch_playlists, daemon=True).start()

    # ── OAuth flow ──
    def _do_login(self):
        self._log_ui(tr("tool.youtube.log_auth_start"))
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

            self._log_ui(tr("tool.youtube.log_opening_browser"))
            webbrowser.open(auth_url)

            # Wait for callback (max 3 minutes)
            deadline = time.time() + 180
            while time.time() < deadline:
                if server._auth_code or server._auth_error:
                    break
                time.sleep(0.5)
            server.shutdown()
            server.server_close()

            if server._auth_error:
                self._log_ui(tr("tool.publish.common.auth_failed", e=server._auth_error))
                return
            if not server._auth_code:
                self._log_ui(tr("tool.publish.common.auth_timeout"))
                return

            # Exchange code for token
            self._log_ui(tr("tool.youtube.log_exchange_token"))
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
            self._log_ui(tr("tool.youtube.log_auth_success",
                            email=self._creds.get('email') or tr("tool.youtube.email_unknown")))
            self.master.after(0, self._refresh_status_label)

            # Fetch playlists after login
            self._fetch_playlists()

        except Exception as e:
            self._log_ui(tr("tool.youtube.log_login_error", e=e))
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
            self._log_ui(tr("tool.youtube.log_token_refreshed"))
            return True
        except Exception as e:
            self._log_ui(tr("tool.youtube.log_token_refresh_failed", e=e))
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
                msg = resp.json().get('error', {}).get('message', resp.text[:100])
                self._log_ui(tr("tool.youtube.log_playlists_failed_http", code=resp.status_code, msg=msg))
                return
            items = resp.json().get("items", [])
            self._playlists = [
                (it["snippet"]["title"], it["id"]) for it in items
            ]
            self.master.after(0, self._rebuild_playlist_checkboxes)
            self._log_ui(tr("tool.youtube.log_playlists_loaded", count=len(self._playlists)))
        except Exception as e:
            self._log_ui(tr("tool.youtube.log_playlists_failed", e=e))

    def _rebuild_playlist_checkboxes(self):
        for widget in self._pl_inner.winfo_children():
            widget.destroy()
        self._pl_vars.clear()
        if not self._playlists:
            tk.Label(self._pl_inner, text=tr("tool.youtube.playlist_empty"), foreground="#888").place(x=0, y=4)
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
            self._log_ui(tr("tool.youtube.log_init_upload", size_mb=file_size / 1024 / 1024))
            self._set_progress(0, tr("tool.youtube.progress_init"))

            # Step 1: init resumable upload, get upload URI
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
                self._log_ui(tr("tool.youtube.log_no_upload_uri"))
                self.set_idle()
                return
            self._log_ui(tr("tool.youtube.log_upload_uri_ok"))

            # Step 2: chunked upload
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
                        # Upload complete
                        resp_json = put_resp.json()
                        video_id = resp_json.get("id")
                        self._set_progress(95, tr("tool.youtube.progress_complete"))
                        self._log_ui(tr("tool.youtube.log_upload_complete", video_id=video_id))
                        break
                    elif put_resp.status_code == 308:
                        # Continue uploading
                        chunk_num += 1
                        pct = int(min(offset + len(chunk), file_size) / file_size * 90)
                        self._set_progress(pct, tr("tool.youtube.progress_chunk",
                                                   chunk=chunk_num, total=total_chunks))
                        self._log_ui(tr("tool.youtube.log_chunk_done", end=end + 1, total=file_size))
                        offset += len(chunk)
                    else:
                        self._log_ui(tr("tool.youtube.log_upload_error_http",
                                        code=put_resp.status_code, text=put_resp.text[:200]))
                        self.set_idle()
                        return

            if not video_id:
                self._log_ui(tr("tool.youtube.log_no_video_id"))
                self.set_idle()
                return

            # Step 3: add to playlists (optional, multi-select)
            for playlist_id in self._get_selected_playlist_ids():
                self._add_to_playlist(video_id, playlist_id)

            self._set_progress(100, tr("tool.youtube.progress_success"))
            self._log_ui(tr("tool.youtube.log_publish_success", video_id=video_id))
            self.set_done()

        except requests.HTTPError as e:
            self._log_ui(tr("tool.youtube.log_http_error",
                            code=e.response.status_code, text=e.response.text[:300]))
            self.set_error(tr("tool.youtube.error_http", e=e))
        except Exception as e:
            self._log_ui(tr("tool.youtube.log_upload_error", e=e))
            self.set_error(tr("tool.youtube.error_upload", e=e))

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
                self._log_ui(tr("tool.youtube.log_pl_added"))
            else:
                self._log_ui(tr("tool.youtube.log_pl_add_failed_http", code=resp.status_code))
        except Exception as e:
            self._log_ui(tr("tool.youtube.log_pl_add_failed", e=e))

    # ── 定时发布 ───────────────────────────────────────────────────────────
    def _schedule_publish(self):
        date_str = self._var_sched_date.get().strip()
        time_str = self._var_sched_time.get().strip()
        try:
            target = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showwarning(tr("dialog.common.info"), tr("tool.publish.common.warn_bad_date"))
            return

        delay = (target - datetime.now()).total_seconds()
        if delay <= 0:
            messagebox.showwarning(tr("dialog.common.info"), tr("tool.publish.common.warn_past_time"))
            return

        self._log_ui(tr("tool.publish.common.sched_queued",
                        target=target.strftime('%Y-%m-%d %H:%M'), minutes=delay / 60))
        self._btn_publish.config(state="disabled")
        self._btn_cancel_sched.config(state="normal")
        self.set_busy()

        self._sched_timer = threading.Timer(delay, self._on_sched_fire)
        self._sched_timer.daemon = True
        self._sched_timer.start()
        self._start_countdown(target)

    def _on_sched_fire(self):
        self._sched_timer = None
        self._log_ui(tr("tool.publish.common.sched_triggered"))
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
                self._lbl_countdown.config(text=tr("tool.publish.common.countdown_imminent"))
                return
            h = int(remaining // 3600)
            m = int((remaining % 3600) // 60)
            s = int(remaining % 60)
            self._lbl_countdown.config(text=tr("tool.publish.common.countdown_fmt", h=h, m=m, s=s))
            self.master.after(1000, _tick)
        self.master.after(1000, _tick)
