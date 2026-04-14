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

_PRIVACY_OPTIONS = [
    ("公开", "PUBLIC_TO_EVERYONE"),
    ("好友可见", "MUTUAL_FOLLOW_FRIENDS"),
    ("仅自己", "SELF_ONLY"),
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
            body = b"<html><body><h2>\u6388\u6743\u5b8c\u6210\uff0c\u8bf7\u5173\u95ed\u6b64\u9875\u9762\u8fd4\u56de\u5e94\u7528\u3002</h2></body></html>"
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
        master.title("TikTok 发布")
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

        # ── 账号区 ─────────────────────────────────────────────────────
        acct_frame = ttk.LabelFrame(root, text="账号")
        acct_frame.pack(fill="x", **pad)

        self._lbl_status = ttk.Label(acct_frame, text=self._status_text(), foreground=self._status_color())
        self._lbl_status.grid(row=0, column=0, sticky="w", padx=8, pady=6)

        ttk.Button(acct_frame, text="授权登录", command=self._on_login).grid(row=0, column=1, padx=4)
        ttk.Button(acct_frame, text="配置凭证", command=self._on_config_creds).grid(row=0, column=2, padx=4)
        ttk.Button(acct_frame, text="注销", command=self._on_logout).grid(row=0, column=3, padx=4)

        # ── 视频信息区 ─────────────────────────────────────────────────
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

        ttk.Label(info_frame, text="话题标签").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        self._var_tags = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self._var_tags).grid(row=2, column=1, columnspan=2, sticky="ew", padx=4)
        ttk.Label(info_frame, text="空格分隔，如: #travel #vlog", foreground="#888").grid(row=3, column=1, sticky="w", padx=4)

        ttk.Label(info_frame, text="隐私设置").grid(row=4, column=0, sticky="w", padx=8, pady=4)
        self._var_privacy = tk.StringVar(value="PUBLIC_TO_EVERYONE")
        priv_frame = ttk.Frame(info_frame)
        priv_frame.grid(row=4, column=1, columnspan=2, sticky="w", padx=4)
        for label, value in _PRIVACY_OPTIONS:
            ttk.Radiobutton(priv_frame, text=label, variable=self._var_privacy, value=value).pack(side="left", padx=6)

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
        self._btn_cancel_sched = ttk.Button(btn_frame, text="取消排队", command=self._on_cancel_sched, state="disabled")
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

    # ── 状态辅助 ───────────────────────────────────────────────────────────
    def _status_text(self) -> str:
        at = self._creds.get("access_token")
        oid = self._creds.get("open_id", "")
        if at:
            return f"已登录  open_id: {oid[:12]}..." if oid else "已登录"
        return "未登录"

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

    # ── 事件处理 ───────────────────────────────────────────────────────────
    def _browse_video(self):
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.mov *.webm"), ("所有文件", "*.*")]
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
        """弹出对话框填写 client_key / client_secret。"""
        dlg = tk.Toplevel(self.master)
        dlg.title("配置 TikTok 开发者凭证")
        dlg.grab_set()
        dlg.resizable(False, False)

        ttk.Label(dlg, text="client_key:").grid(row=0, column=0, sticky="w", padx=10, pady=6)
        var_ck = tk.StringVar(value=self._creds.get("client_key", ""))
        ttk.Entry(dlg, textvariable=var_ck, width=44).grid(row=0, column=1, padx=6)

        ttk.Label(dlg, text="client_secret:").grid(row=1, column=0, sticky="w", padx=10, pady=6)
        var_cs = tk.StringVar(value=self._creds.get("client_secret", ""))
        ttk.Entry(dlg, textvariable=var_cs, show="*", width=44).grid(row=1, column=1, padx=6)

        ttk.Label(dlg, text="申请地址: developers.tiktok.com", foreground="#555").grid(
            row=2, column=0, columnspan=2, padx=10, pady=2, sticky="w")

        def _save():
            ck = var_ck.get().strip()
            cs = var_cs.get().strip()
            if not ck or not cs:
                messagebox.showwarning("提示", "client_key 和 client_secret 均不能为空", parent=dlg)
                return
            self._creds["client_key"] = ck
            self._creds["client_secret"] = cs
            self._save_credentials()
            self._log_ui("开发者凭证已保存。")
            dlg.destroy()

        ttk.Button(dlg, text="保存", command=_save).grid(row=3, column=0, columnspan=2, pady=10)

    def _on_login(self):
        if not self._creds.get("client_key"):
            messagebox.showinfo("提示", "请先点击「配置凭证」填写 client_key / client_secret。")
            return
        threading.Thread(target=self._do_login, daemon=True).start()

    def _on_logout(self):
        for key in ("access_token", "refresh_token", "open_id", "expires_at"):
            self._creds.pop(key, None)
        self._save_credentials()
        self._refresh_status_label()
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

    # ── OAuth PKCE 流 ──────────────────────────────────────────────────────
    def _do_login(self):
        self._log_ui("开始 OAuth 授权流程...")
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

            self._log_ui(f"正在打开浏览器授权页...")
            webbrowser.open(auth_url)

            # 等待回调（最多 3 分钟）
            deadline = time.time() + 180
            while time.time() < deadline:
                server.handle_request()
                if server._auth_code or server._auth_error:
                    break

            server.server_close()

            if server._auth_error:
                self._log_ui(f"授权失败: {server._auth_error}")
                return
            if not server._auth_code:
                self._log_ui("授权超时，请重试。")
                return

            # 换取 token
            self._log_ui("正在换取 Access Token...")
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
            self._log_ui("授权成功！Access Token 已保存。")
            self.master.after(0, self._refresh_status_label)

        except Exception as e:
            self._log_ui(f"登录出错: {e}")
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
            self._log_ui("Access Token 已自动刷新。")
            return True
        except Exception as e:
            self._log_ui(f"Token 刷新失败: {e}")
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
            self._log_ui(f"初始化上传... 文件大小: {file_size / 1024 / 1024:.1f} MB, 共 {total_chunks} 块")
            self._set_progress(0, "初始化上传...")

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
                msg = init_data.get("error", {}).get("message", "未知错误")
                self._log_ui(f"初始化失败: {msg}")
                self.set_error(f"TikTok 上传初始化失败: {msg}")
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

                    pct = int((i + 1) / total_chunks * 80)  # 上传占 80%
                    self._set_progress(pct, f"上传第 {i+1}/{total_chunks} 块...")
                    self._log_ui(f"已上传块 {i+1}/{total_chunks} ({content_range})")

            # Step 3: 轮询发布状态
            self._log_ui("上传完成，等待 TikTok 处理...")
            self._set_progress(85, "等待发布处理...")
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
                self._log_ui(f"发布状态: {status}")

                if status == "PUBLISH_COMPLETE":
                    self._set_progress(100, "发布成功！")
                    self._log_ui("视频已成功发布到 TikTok！")
                    self.set_done()
                    return
                elif status in ("FAILED", "PUBLISH_FAILED"):
                    fail_code = st_data.get("data", {}).get("fail_reason", "")
                    self._log_ui(f"发布失败: {fail_code}")
                    self.set_error(f"TikTok 发布失败: {fail_code}")
                    return

            # Polling timed out without definitive success/failure — warn, not error.
            self._log_ui("发布状态查询超时，请到 TikTok 后台确认。")
            self.set_warning("TikTok 发布状态查询超时，请到后台确认结果")

        except requests.HTTPError as e:
            self._log_ui(f"HTTP 错误: {e.response.status_code} - {e.response.text[:200]}")
            self.set_error(f"TikTok 上传 HTTP 错误: {e}")
        except Exception as e:
            self._log_ui(f"上传出错: {e}")
            self.set_error(f"TikTok 上传失败: {e}")

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
        """每秒更新倒计时 label（在主线程）。"""
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
