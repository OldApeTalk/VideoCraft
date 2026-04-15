"""
tools/publish/tiktok_publish.py - TikTok 视频发布工具

通过 TikTok Content Posting API v2 将本地视频发布到 TikTok。
功能：OAuth 2.0 PKCE 登录、分块上传、隐私设置、应用内定时发布。
"""

import hashlib
import http.server
import json
import math
import os
import secrets
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
import webbrowser
from base64 import urlsafe_b64encode
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog, ttk

import requests

from i18n import tr
from tools.base import ToolBase

# ── API 端点 ──────────────────────────────────────────────────────────────────
_AUTH_URL     = "https://www.tiktok.com/v2/auth/authorize/"
_TOKEN_URL    = "https://open.tiktokapis.com/v2/oauth/token/"
_INIT_URL     = "https://open.tiktokapis.com/v2/post/publish/video/init/"
_STATUS_URL   = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
_CALLBACK_PORT = 18765
_CALLBACK_PATH = "/callback"
_CHUNK_SIZE    = 10 * 1024 * 1024   # 10 MB

# ── Token 文件路径（相对于项目根，运行时拼绝对路径）─────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_KEYS_DIR = os.path.normpath(os.path.join(_HERE, "../../../keys"))
_TOKEN_FILE = os.path.join(_KEYS_DIR, "tiktok_token.json")

def _privacy_options():
    """Build the privacy option list with current-locale labels."""
    return [
        (tr("tool.tiktok.privacy_public"),  "PUBLIC_TO_EVERYONE"),
        (tr("tool.tiktok.privacy_friends"), "MUTUAL_FOLLOW_FRIENDS"),
        (tr("tool.tiktok.privacy_self"),    "SELF_ONLY"),
    ]


# ── OAuth 回调服务器 ───────────────────────────────────────────────────────────
class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """接收 TikTok OAuth 重定向，提取 code 参数。"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == _CALLBACK_PATH:
            params = urllib.parse.parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            error = params.get("error", [None])[0]
            self.server._auth_code = code
            self.server._auth_error = error
            body = f"<html><body><h2>{tr('tool.publish.common.oauth_done_page')}</h2></body></html>".encode("utf-8")
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


# ── 主工具类 ──────────────────────────────────────────────────────────────────
class TikTokPublishApp(ToolBase):
    """TikTok 视频发布工具，嵌入 Hub Tab。"""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title(tr("tool.tiktok.title"))
        master.geometry("640x700")

        self._creds = {}          # 运行时凭证缓存
        self._sched_timer = None  # threading.Timer 用于定时发布

        self._load_credentials()
        self._build_ui()

        if initial_file and os.path.isfile(initial_file):
            self._var_video.set(initial_file)

    # ── 凭证 I/O ───────────────────────────────────────────────────────────
    def _load_credentials(self):
        if os.path.isfile(_TOKEN_FILE):
            try:
                with open(_TOKEN_FILE, "r", encoding="utf-8") as f:
                    self._creds = json.load(f)
            except Exception:
                self._creds = {}

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

        self._lbl_status = ttk.Label(acct_frame, text=self._status_text(), foreground=self._status_color())
        self._lbl_status.grid(row=0, column=0, sticky="w", padx=8, pady=6)

        ttk.Button(acct_frame, text=tr("tool.publish.common.btn_login"),
                   command=self._on_login).grid(row=0, column=1, padx=4)
        ttk.Button(acct_frame, text=tr("tool.tiktok.btn_config_creds"),
                   command=self._on_config_creds).grid(row=0, column=2, padx=4)
        ttk.Button(acct_frame, text=tr("tool.publish.common.btn_logout"),
                   command=self._on_logout).grid(row=0, column=3, padx=4)

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

        ttk.Label(info_frame, text=tr("tool.tiktok.hashtags_label")).grid(row=2, column=0, sticky="w", padx=8, pady=4)
        self._var_tags = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self._var_tags).grid(row=2, column=1, columnspan=2, sticky="ew", padx=4)
        ttk.Label(info_frame, text=tr("tool.tiktok.hashtags_hint"), foreground="#888").grid(row=3, column=1, sticky="w", padx=4)

        ttk.Label(info_frame, text=tr("tool.tiktok.privacy_label")).grid(row=4, column=0, sticky="w", padx=8, pady=4)
        self._var_privacy = tk.StringVar(value="PUBLIC_TO_EVERYONE")
        priv_frame = ttk.Frame(info_frame)
        priv_frame.grid(row=4, column=1, columnspan=2, sticky="w", padx=4)
        for label, value in _privacy_options():
            ttk.Radiobutton(priv_frame, text=label, variable=self._var_privacy, value=value).pack(side="left", padx=6)

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
        self._btn_publish = ttk.Button(btn_frame, text=tr("tool.publish.common.btn_publish_now"), command=self._on_publish)
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

    # ── Status helpers ──
    def _status_text(self) -> str:
        at = self._creds.get("access_token")
        oid = self._creds.get("open_id", "")
        if at:
            return (tr("tool.tiktok.status_logged_in_openid", open_id=oid[:12]) if oid
                    else tr("tool.publish.common.status_logged_in"))
        return tr("tool.publish.common.status_not_logged_in")

    def _status_color(self) -> str:
        return "#228B22" if self._creds.get("access_token") else "#CC3333"

    def _refresh_status_label(self):
        self._lbl_status.config(text=self._status_text(), foreground=self._status_color())

    def _log_ui(self, msg: str):
        """写入工具内日志区（主线程安全用 after）。"""
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

    # ── Event handlers ──
    def _browse_video(self):
        path = filedialog.askopenfilename(
            title=tr("tool.publish.common.dialog_select_video"),
            filetypes=[(tr("tool.publish.common.filter_video"), "*.mp4 *.mov *.webm"),
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

    def _on_config_creds(self):
        """Dialog to fill in client_key / client_secret."""
        dlg = tk.Toplevel(self.master)
        dlg.title(tr("tool.tiktok.dialog_config_title"))
        dlg.grab_set()
        dlg.resizable(False, False)

        ttk.Label(dlg, text="client_key:").grid(row=0, column=0, sticky="w", padx=10, pady=6)
        var_ck = tk.StringVar(value=self._creds.get("client_key", ""))
        ttk.Entry(dlg, textvariable=var_ck, width=44).grid(row=0, column=1, padx=6)

        ttk.Label(dlg, text="client_secret:").grid(row=1, column=0, sticky="w", padx=10, pady=6)
        var_cs = tk.StringVar(value=self._creds.get("client_secret", ""))
        ttk.Entry(dlg, textvariable=var_cs, show="*", width=44).grid(row=1, column=1, padx=6)

        ttk.Label(dlg, text=tr("tool.tiktok.apply_hint"), foreground="#555").grid(
            row=2, column=0, columnspan=2, padx=10, pady=2, sticky="w")

        def _save():
            ck = var_ck.get().strip()
            cs = var_cs.get().strip()
            if not ck or not cs:
                messagebox.showwarning(tr("dialog.common.info"),
                                       tr("tool.tiktok.warn_creds_empty"), parent=dlg)
                return
            self._creds["client_key"] = ck
            self._creds["client_secret"] = cs
            self._save_credentials()
            self._log_ui(tr("tool.tiktok.log_creds_saved"))
            dlg.destroy()

        ttk.Button(dlg, text=tr("tool.tiktok.btn_save"), command=_save).grid(row=3, column=0, columnspan=2, pady=10)

    def _on_login(self):
        if not self._creds.get("client_key"):
            messagebox.showinfo(tr("dialog.common.info"), tr("tool.tiktok.warn_need_creds"))
            return
        threading.Thread(target=self._do_login, daemon=True).start()

    def _on_logout(self):
        for key in ("access_token", "refresh_token", "open_id", "expires_at"):
            self._creds.pop(key, None)
        self._save_credentials()
        self._refresh_status_label()
        self._log_ui(tr("tool.tiktok.log_logout"))

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

    # ── OAuth PKCE flow ──
    def _do_login(self):
        self._log_ui(tr("tool.tiktok.log_auth_start"))
        try:
            # 生成 PKCE
            verifier = urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
            challenge = urlsafe_b64encode(
                hashlib.sha256(verifier.encode()).digest()
            ).rstrip(b"=").decode()

            state = secrets.token_hex(16)
            redirect_uri = f"http://localhost:{_CALLBACK_PORT}{_CALLBACK_PATH}"

            params = urllib.parse.urlencode({
                "client_key": self._creds["client_key"],
                "response_type": "code",
                "scope": "video.publish,video.upload",
                "redirect_uri": redirect_uri,
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            })
            auth_url = f"{_AUTH_URL}?{params}"

            # 启动本地回调服务器
            server = http.server.HTTPServer(("localhost", _CALLBACK_PORT), _CallbackHandler)
            server._auth_code = None
            server._auth_error = None
            server.timeout = 1

            self._log_ui(tr("tool.tiktok.log_opening_browser"))
            webbrowser.open(auth_url)

            # Wait for callback (max 3 minutes)
            deadline = time.time() + 180
            while time.time() < deadline:
                server.handle_request()
                if server._auth_code or server._auth_error:
                    break

            server.server_close()

            if server._auth_error:
                self._log_ui(tr("tool.publish.common.auth_failed", e=server._auth_error))
                return
            if not server._auth_code:
                self._log_ui(tr("tool.publish.common.auth_timeout"))
                return

            # Exchange code for token
            self._log_ui(tr("tool.tiktok.log_exchange_token"))
            resp = requests.post(_TOKEN_URL, json={
                "client_key": self._creds["client_key"],
                "client_secret": self._creds["client_secret"],
                "code": server._auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            }, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            self._creds.update({
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", ""),
                "open_id": data.get("open_id", ""),
                "expires_at": time.time() + data.get("expires_in", 86400) - 60,
            })
            self._save_credentials()
            self._log_ui(tr("tool.tiktok.log_auth_success"))
            self.master.after(0, self._refresh_status_label)

        except Exception as e:
            self._log_ui(tr("tool.tiktok.log_login_error", e=e))
            self.log_error(f"TikTok login error: {e}")

    # ── Token 刷新 ─────────────────────────────────────────────────────────
    def _ensure_token(self) -> bool:
        """确保 access_token 有效；如过期则自动刷新。返回 True 表示 token 可用。"""
        if not self._creds.get("access_token"):
            return False
        if time.time() < self._creds.get("expires_at", 0):
            return True  # 未过期

        # 尝试刷新
        rt = self._creds.get("refresh_token")
        if not rt:
            return False
        try:
            resp = requests.post(_TOKEN_URL, json={
                "client_key": self._creds["client_key"],
                "client_secret": self._creds["client_secret"],
                "grant_type": "refresh_token",
                "refresh_token": rt,
            }, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            self._creds.update({
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", rt),
                "expires_at": time.time() + data.get("expires_in", 86400) - 60,
            })
            self._save_credentials()
            self._log_ui(tr("tool.tiktok.log_token_refreshed"))
            return True
        except Exception as e:
            self._log_ui(tr("tool.tiktok.log_token_refresh_failed", e=e))
            return False

    # ── 分块上传 ───────────────────────────────────────────────────────────
    def _do_upload(self):
        video_path = self._var_video.get().strip()
        title = self._var_title.get().strip()
        tags = self._var_tags.get().strip()
        privacy = self._var_privacy.get()

        # 拼接 hashtag 到标题
        if tags:
            hashtags = " ".join(
                t if t.startswith("#") else f"#{t}"
                for t in tags.split()
                if t
            )
            full_title = f"{title} {hashtags}".strip() if title else hashtags
        else:
            full_title = title

        file_size = os.path.getsize(video_path)
        chunk_size = _CHUNK_SIZE
        total_chunks = max(1, math.ceil(file_size / chunk_size))

        headers = {
            "Authorization": f"Bearer {self._creds['access_token']}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        try:
            self._log_ui(tr("tool.tiktok.log_init_upload",
                            size_mb=file_size / 1024 / 1024, total_chunks=total_chunks))
            self._set_progress(0, tr("tool.tiktok.progress_init"))

            # Step 1: init
            init_payload = {
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": min(chunk_size, file_size),
                    "total_chunk_count": total_chunks,
                },
                "post_info": {
                    "title": full_title[:2200],
                    "privacy_level": privacy,
                    "disable_duet": False,
                    "disable_stitch": False,
                    "disable_comment": False,
                },
            }
            resp = requests.post(_INIT_URL, headers=headers, json=init_payload, timeout=30)
            resp.raise_for_status()
            init_data = resp.json()

            if init_data.get("error", {}).get("code") != "ok":
                msg = init_data.get("error", {}).get("message", tr("tool.tiktok.err_unknown"))
                self._log_ui(tr("tool.tiktok.log_init_failed", msg=msg))
                self.set_error(tr("tool.tiktok.error_init_failed", msg=msg))
                return

            publish_id = init_data["data"]["publish_id"]
            upload_url = init_data["data"]["upload_url"]
            self._log_ui(f"publish_id: {publish_id}")

            # Step 2: 分块上传
            with open(video_path, "rb") as f:
                for i in range(total_chunks):
                    start = i * chunk_size
                    data = f.read(chunk_size)
                    end = start + len(data) - 1
                    content_range = f"bytes {start}-{end}/{file_size}"

                    put_headers = {
                        "Content-Type": "video/mp4",
                        "Content-Length": str(len(data)),
                        "Content-Range": content_range,
                    }
                    put_resp = requests.put(upload_url, headers=put_headers, data=data, timeout=120)
                    put_resp.raise_for_status()

                    pct = int((i + 1) / total_chunks * 80)  # upload accounts for 80%
                    self._set_progress(pct, tr("tool.tiktok.progress_chunk", i=i + 1, total=total_chunks))
                    self._log_ui(tr("tool.tiktok.log_chunk_done", i=i + 1, total=total_chunks, content_range=content_range))

            # Step 3: poll publish status
            self._log_ui(tr("tool.tiktok.log_upload_done_waiting"))
            self._set_progress(85, tr("tool.tiktok.progress_waiting"))
            for attempt in range(30):
                time.sleep(5)
                status_resp = requests.get(
                    _STATUS_URL,
                    params={"publish_id": publish_id},
                    headers={"Authorization": f"Bearer {self._creds['access_token']}"},
                    timeout=30,
                )
                status_resp.raise_for_status()
                st_data = status_resp.json()
                status = st_data.get("data", {}).get("status", "")
                self._log_ui(tr("tool.tiktok.log_status_fmt", status=status))

                if status == "PUBLISH_COMPLETE":
                    self._set_progress(100, tr("tool.tiktok.progress_success"))
                    self._log_ui(tr("tool.tiktok.log_publish_success"))
                    self.set_done()
                    return
                elif status in ("FAILED", "PUBLISH_FAILED"):
                    fail_code = st_data.get("data", {}).get("fail_reason", "")
                    self._log_ui(tr("tool.tiktok.log_publish_failed", fail_code=fail_code))
                    self.set_error(tr("tool.tiktok.error_publish_failed", fail_code=fail_code))
                    return

            # Polling timed out without definitive success/failure — warn, not error.
            self._log_ui(tr("tool.tiktok.log_poll_timeout"))
            self.set_warning(tr("tool.tiktok.warning_poll_timeout"))

        except requests.HTTPError as e:
            self._log_ui(tr("tool.tiktok.log_http_error",
                            code=e.response.status_code, text=e.response.text[:200]))
            self.set_error(tr("tool.tiktok.error_http", e=e))
        except Exception as e:
            self._log_ui(tr("tool.tiktok.log_upload_error", e=e))
            self.set_error(tr("tool.tiktok.error_upload", e=e))

    # ── Scheduled publish ──
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
        """Update the countdown label every second (on the main thread)."""
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
