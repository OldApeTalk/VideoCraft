"""
Lightweight VLC player embedded in a Tk Frame.

Requires the `python-vlc` package AND a VLC 64-bit installation whose bitness
matches the Python interpreter. If VLC is unavailable, `is_vlc_available()`
returns False and the frame falls back to a plain-text notice so the host
tool stays usable.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk
from typing import Callable

try:
    import vlc  # type: ignore
    _VLC_IMPORT_ERROR: Exception | None = None
except Exception as _e:  # pragma: no cover - env-dependent
    vlc = None  # type: ignore
    _VLC_IMPORT_ERROR = _e


def is_vlc_available() -> bool:
    """True if python-vlc imported AND a VLC Instance can actually be built."""
    if vlc is None:
        return False
    try:
        inst = vlc.Instance()
        return inst is not None
    except Exception:
        return False


def _fmt_ms(ms: int) -> str:
    if ms < 0:
        ms = 0
    s = ms // 1000
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


class VlcPlayerFrame(tk.Frame):
    """Tk Frame with an embedded VLC surface and a minimal transport bar.

    Usage:
        player = VlcPlayerFrame(parent)
        player.pack(...)
        player.load("/path/to/video.mp4")
        player.seek(123.5)   # seconds
        player.play()
    """

    def __init__(self, master: tk.Misc, **kwargs):
        super().__init__(master, **kwargs)
        self._instance = None
        self._player = None
        self._duration_ms = 0
        self._loaded_path: str | None = None
        self._user_seeking = False
        self._poll_job: str | None = None
        self._on_position: Callable[[float, float], None] | None = None

        if is_vlc_available():
            self._instance = vlc.Instance()
            self._player = self._instance.media_player_new()
            self._build_ui()
        else:
            self._build_fallback_ui()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._surface = tk.Frame(self, bg="black", highlightthickness=0)
        self._surface.grid(row=0, column=0, sticky="nsew")

        controls = tk.Frame(self)
        controls.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        controls.columnconfigure(3, weight=1)

        self._btn_play = tk.Button(controls, text="▶", width=3, command=self.toggle_play)
        self._btn_play.grid(row=0, column=0, padx=2)
        tk.Button(controls, text="⏹", width=3, command=self.stop).grid(row=0, column=1, padx=2)

        self._time_label = tk.Label(controls, text="00:00 / 00:00", width=14)
        self._time_label.grid(row=0, column=2, padx=4)

        self._scale_var = tk.DoubleVar(value=0.0)
        self._scale = ttk.Scale(
            controls, from_=0.0, to=1000.0, orient="horizontal",
            variable=self._scale_var, command=self._on_scale_drag,
        )
        self._scale.grid(row=0, column=3, sticky="ew", padx=4)
        self._scale.bind("<ButtonPress-1>", lambda _e: self._begin_seek())
        self._scale.bind("<ButtonRelease-1>", self._end_seek)

    def _build_fallback_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        msg = "VLC not detected. Install VLC 64-bit + `pip install python-vlc`."
        if _VLC_IMPORT_ERROR is not None:
            msg += f"\n({_VLC_IMPORT_ERROR})"
        tk.Label(
            self, text=msg, justify="center", wraplength=320,
            fg="#888", bg="#222",
        ).grid(row=0, column=0, sticky="nsew")

    # ── Public API ────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        return self._player is not None

    def load(self, path: str) -> None:
        if self._player is None:
            return
        self.stop()
        media = self._instance.media_new(path)
        self._player.set_media(media)
        self._bind_surface()
        self._loaded_path = path
        # Kick a short play/pause so VLC reports duration and shows the first frame.
        self._player.play()
        self.after(200, self._show_first_frame)

    def _show_first_frame(self) -> None:
        if self._player is None:
            return
        self._duration_ms = max(0, self._player.get_length())
        self._player.set_pause(1)
        self._player.set_time(0)
        self._update_time_label()
        self._start_polling()

    def seek(self, seconds: float) -> None:
        if self._player is None:
            return
        target = max(0, int(seconds * 1000))
        if self._duration_ms > 0:
            target = min(target, self._duration_ms - 1)
        self._player.set_time(target)
        self._update_time_label()

    def play(self) -> None:
        if self._player is None:
            return
        self._player.play()
        self._btn_play.config(text="⏸")
        self._start_polling()

    def pause(self) -> None:
        if self._player is None:
            return
        self._player.set_pause(1)
        self._btn_play.config(text="▶")

    def toggle_play(self) -> None:
        if self._player is None:
            return
        if self._player.is_playing():
            self.pause()
        else:
            self.play()

    def stop(self) -> None:
        if self._player is None:
            return
        try:
            self._player.stop()
        except Exception:
            pass
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        if hasattr(self, "_btn_play"):
            self._btn_play.config(text="▶")

    def release(self) -> None:
        """Fully release VLC resources. Call on window close."""
        self.stop()
        if self._player is not None:
            try:
                self._player.release()
            except Exception:
                pass
            self._player = None
        if self._instance is not None:
            try:
                self._instance.release()
            except Exception:
                pass
            self._instance = None

    def set_on_position(self, cb: Callable[[float, float], None] | None) -> None:
        """Register a callback receiving (current_sec, duration_sec) on each tick."""
        self._on_position = cb

    # ── Internals ─────────────────────────────────────────────────────────

    def _bind_surface(self) -> None:
        """Attach VLC output to the surface frame (Windows/Linux/macOS)."""
        if self._player is None:
            return
        self.update_idletasks()
        handle = self._surface.winfo_id()
        if sys.platform.startswith("win"):
            self._player.set_hwnd(handle)
        elif sys.platform == "darwin":
            # On macOS VLC needs an NSView pointer; winfo_id() is close enough
            # for Tk+VLC 3.x. If this fails on a given build, fallback UI shows.
            try:
                self._player.set_nsobject(handle)
            except Exception:
                pass
        else:
            self._player.set_xwindow(handle)

    def _begin_seek(self) -> None:
        self._user_seeking = True

    def _on_scale_drag(self, _value: str) -> None:
        if not self._user_seeking:
            return
        self._update_time_label(drag_preview=True)

    def _end_seek(self, _event) -> None:
        if self._player is None:
            self._user_seeking = False
            return
        pct = self._scale_var.get() / 1000.0
        if self._duration_ms > 0:
            self._player.set_time(int(pct * self._duration_ms))
        self._user_seeking = False
        self._update_time_label()

    def _start_polling(self) -> None:
        if self._poll_job is not None:
            return
        self._poll_tick()

    def _poll_tick(self) -> None:
        if self._player is None:
            self._poll_job = None
            return
        if self._duration_ms <= 0:
            self._duration_ms = max(0, self._player.get_length())
        if not self._user_seeking and self._duration_ms > 0:
            cur = max(0, self._player.get_time())
            frac = cur / self._duration_ms
            self._scale_var.set(frac * 1000.0)
            self._update_time_label()
            if self._on_position is not None:
                try:
                    self._on_position(cur / 1000.0, self._duration_ms / 1000.0)
                except Exception:
                    pass
        self._poll_job = self.after(250, self._poll_tick)

    def _update_time_label(self, drag_preview: bool = False) -> None:
        if self._player is None or self._duration_ms <= 0:
            return
        if drag_preview:
            cur = int(self._scale_var.get() / 1000.0 * self._duration_ms)
        else:
            cur = max(0, self._player.get_time())
        self._time_label.config(text=f"{_fmt_ms(cur)} / {_fmt_ms(self._duration_ms)}")


__all__ = ["is_vlc_available", "VlcPlayerFrame"]
