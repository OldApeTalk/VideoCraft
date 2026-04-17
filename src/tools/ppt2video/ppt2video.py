"""PPT2Video — convert PowerPoint slides to narrated video.

Five-step pipeline:
  1. Submit PPT (.pptx with speaker notes)
  2. Export slide PNGs + extract notes text
  3. Generate per-page audio via TTS (or import user-supplied MP3s)
  4. Generate per-page subtitle SRT
  5. Compose final MP4 (image + audio + subtitle per page, then concat)
"""

from __future__ import annotations

import os
import glob
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tools.base import ToolBase
from i18n import tr
from hub_logger import logger


# Step status constants (reuse Hub STATUS_COLORS keys)
_IDLE = "idle"
_RUNNING = "running"
_DONE = "done"
_ERROR = "error"
_WARNING = "warning"

_STATUS_COLORS = {
    _IDLE:    "#9e9e9e",
    _RUNNING: "#2196F3",
    _DONE:    "#4caf50",
    _WARNING: "#f0a500",
    _ERROR:   "#f44747",
}

_STEPS = [
    ("step1", "tool.ppt2video.step1_title"),
    ("step2", "tool.ppt2video.step2_title"),
    ("step3", "tool.ppt2video.step3_title"),
    ("step4", "tool.ppt2video.step4_title"),
    ("step5", "tool.ppt2video.step5_title"),
]


class PPT2VideoApp(ToolBase):
    def __init__(self, master, initial_file: str | None = None):
        self.master = master
        master.title(tr("tool.ppt2video.title"))
        master.geometry("900x600")

        self._project_dir = initial_file
        self._workdir: str | None = None
        self._busy = False
        self._step_status: list[str] = [_IDLE] * 5
        self._step_dots: list[tk.Canvas] = []
        self._step_info_labels: list[tk.Label] = []
        self._step_buttons: list[tk.Button] = []

        # TTS config
        self._voice_id_var = tk.StringVar()
        self._use_existing_audio_var = tk.BooleanVar(value=False)
        self._enable_subs_var = tk.BooleanVar(value=False)

        self._status_var = tk.StringVar(value=tr("tool.ppt2video.status_idle"))

        if self._project_dir:
            self._workdir = os.path.join(self._project_dir, "ppt2video")
            self._build_ui()
            self._scan_existing_artifacts()
        else:
            self._build_empty_state()

    # ── Empty state (no project) ─────────────────────────────────────────

    def _build_empty_state(self):
        m = self.master
        frame = tk.Frame(m, bg="white")
        frame.pack(fill="both", expand=True)
        inner = tk.Frame(frame, bg="white")
        inner.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(inner, text=tr("tool.ppt2video.no_project_title"),
                 font=("", 18, "bold"), bg="white", fg="#333").pack(pady=(0, 6))
        tk.Label(inner, text=tr("tool.ppt2video.no_project_hint"),
                 font=("", 11), bg="white", fg="#888").pack(pady=(0, 20))

    # ── Main UI ──────────────────────────────────────────────────────────

    def _build_ui(self):
        m = self.master
        m.columnconfigure(0, weight=1)
        m.rowconfigure(1, weight=1)

        # --- Top: project info ---
        top = tk.Frame(m)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        top.columnconfigure(1, weight=1)

        tk.Label(top, text=tr("tool.ppt2video.label_workdir"),
                 font=("", 9)).grid(row=0, column=0, sticky="e")
        tk.Label(top, text=self._workdir or "", anchor="w",
                 font=("", 9), fg="#555").grid(row=0, column=1, sticky="ew", padx=6)

        # --- Middle: step checklist ---
        mid = tk.Frame(m)
        mid.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        mid.columnconfigure(2, weight=1)

        for i, (step_id, title_key) in enumerate(_STEPS):
            row_frame = tk.Frame(mid)
            row_frame.grid(row=i, column=0, columnspan=4, sticky="ew", pady=3)
            row_frame.columnconfigure(2, weight=1)

            # Status dot
            dot = tk.Canvas(row_frame, width=16, height=16,
                            highlightthickness=0)
            dot.grid(row=0, column=0, padx=(0, 6))
            self._draw_dot(dot, _IDLE)
            self._step_dots.append(dot)

            # Step label
            tk.Label(row_frame, text=f"{i+1}. {tr(title_key)}",
                     font=("", 10, "bold"), anchor="w").grid(
                         row=0, column=1, sticky="w")

            # Info label (artifact count etc.)
            info = tk.Label(row_frame, text="", font=("", 9), fg="#888",
                            anchor="w")
            info.grid(row=0, column=2, sticky="ew", padx=8)
            self._step_info_labels.append(info)

            # Run button
            btn = tk.Button(row_frame,
                            text=tr("tool.ppt2video.btn_run_step"),
                            state="disabled",
                            command=lambda idx=i: self._run_step(idx))
            btn.grid(row=0, column=3, padx=(4, 0))
            self._step_buttons.append(btn)

            # Step-specific inline widgets
            if step_id == "step1":
                detail = tk.Frame(mid)
                detail.grid(row=i, column=0, columnspan=4, sticky="ew",
                            padx=(28, 0), pady=(0, 2))
                # Actually place it below the row
                detail.grid(row=len(_STEPS) + i, column=0, columnspan=4,
                            sticky="ew", padx=(28, 0), pady=(0, 2))
                tk.Button(detail, text=tr("tool.ppt2video.btn_browse_pptx"),
                          command=self._browse_pptx).pack(side="left")
                self._pptx_label = tk.Label(detail, text="", fg="#555",
                                            font=("", 9))
                self._pptx_label.pack(side="left", padx=6)

            elif step_id == "step3":
                detail = tk.Frame(mid)
                detail.grid(row=len(_STEPS) + i, column=0, columnspan=4,
                            sticky="ew", padx=(28, 0), pady=(0, 2))
                tk.Label(detail, text=tr("tool.ppt2video.label_voice_id"),
                         font=("", 9)).pack(side="left")
                tk.Entry(detail, textvariable=self._voice_id_var,
                         width=36).pack(side="left", padx=4)
                tk.Checkbutton(
                    detail,
                    text=tr("tool.ppt2video.use_existing_audio"),
                    variable=self._use_existing_audio_var,
                ).pack(side="left", padx=8)

            elif step_id == "step4":
                detail = tk.Frame(mid)
                detail.grid(row=len(_STEPS) + i, column=0, columnspan=4,
                            sticky="ew", padx=(28, 0), pady=(0, 2))
                tk.Checkbutton(
                    detail,
                    text=tr("tool.ppt2video.enable_approx_subs"),
                    variable=self._enable_subs_var,
                ).pack(side="left")
                tk.Label(detail, text=tr("tool.ppt2video.subs_hint"),
                         font=("", 8), fg="#999").pack(side="left", padx=6)

        # --- Bottom: action bar ---
        bot = tk.Frame(m)
        bot.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 8))

        self._btn_run_all = tk.Button(
            bot, text=tr("tool.ppt2video.btn_run_all"),
            state="disabled", command=self._run_all)
        self._btn_run_all.pack(side="left", padx=(0, 6))

        self._btn_run_from = tk.Button(
            bot, text=tr("tool.ppt2video.btn_run_from_here"),
            state="disabled", command=self._run_from_current)
        self._btn_run_from.pack(side="left", padx=(0, 6))

        tk.Button(bot, text=tr("tool.ppt2video.btn_open_workdir"),
                  command=self._open_workdir).pack(side="left")

        tk.Label(bot, textvariable=self._status_var, font=("", 9),
                 fg="#555", anchor="w").pack(side="right", fill="x", expand=True)

        # Enable step 1 button immediately
        self._step_buttons[0].config(state="normal")
        self._btn_run_all.config(state="normal")

    # ── Drawing helpers ──────────────────────────────────────────────────

    def _draw_dot(self, canvas: tk.Canvas, status: str):
        canvas.delete("all")
        color = _STATUS_COLORS.get(status, _STATUS_COLORS[_IDLE])
        canvas.create_oval(2, 2, 14, 14, fill=color, outline="")

    def _set_step_status(self, idx: int, status: str, info: str = ""):
        self._step_status[idx] = status
        self.master.after(0, self._draw_dot, self._step_dots[idx], status)
        if info:
            self.master.after(0, self._step_info_labels[idx].config, {"text": info})

    # ── Artifact scanning ────────────────────────────────────────────────

    def _scan_existing_artifacts(self):
        if not self._workdir or not os.path.isdir(self._workdir):
            return

        pptx = os.path.join(self._workdir, "source.pptx")
        if os.path.isfile(pptx):
            self._set_step_status(0, _DONE)
            self._pptx_label.config(text=os.path.basename(pptx))
            self._step_buttons[1].config(state="normal")

        pages = self._count_files("pages", "*.png")
        notes = self._count_files("notes", "*.txt")
        if pages > 0:
            self._set_step_status(
                1, _DONE,
                tr("tool.ppt2video.info_pages_notes",
                   pages=pages, notes=notes))
            self._step_buttons[2].config(state="normal")

        audio = self._count_files("audio", "*.mp3")
        if audio > 0:
            self._set_step_status(
                2, _DONE,
                tr("tool.ppt2video.info_audio", count=audio))
            self._step_buttons[3].config(state="normal")

        subs = self._count_files("subs", "*.srt")
        if subs > 0:
            self._set_step_status(
                3, _DONE,
                tr("tool.ppt2video.info_subs", count=subs))
            self._step_buttons[4].config(state="normal")

        output = os.path.join(self._workdir, "output.mp4")
        if os.path.isfile(output):
            self._set_step_status(4, _DONE)

    def _count_files(self, subdir: str, pattern: str) -> int:
        d = os.path.join(self._workdir, subdir)
        if not os.path.isdir(d):
            return 0
        return len(glob.glob(os.path.join(d, pattern)))

    # ── Step execution stubs (wired in M2-M5) ───────────────────────────

    def _run_step(self, idx: int):
        if self._busy:
            return
        steps = [
            self._run_step1,
            self._run_step2,
            self._run_step3,
            self._run_step4,
            self._run_step5,
        ]
        steps[idx]()

    def _run_step1(self):
        self._browse_pptx()

    def _run_step2(self):
        pptx = os.path.join(self._workdir, "source.pptx")
        if not os.path.isfile(pptx):
            self.set_error(tr("tool.ppt2video.error_copy_pptx", e="source.pptx missing"))
            return
        self._set_busy(True)
        self._set_step_status(1, _RUNNING)
        self._status_var.set(tr("tool.ppt2video.status_exporting"))

        def work():
            try:
                from core.pptx_pipeline import run_step2
                pages, notes = run_step2(
                    pptx, self._workdir,
                    on_progress=lambda d, t, m: self.master.after(
                        0, self._status_var.set,
                        tr("tool.ppt2video.status_exporting") + f" {d}/{t}"),
                )
                self.master.after(0, self._on_step2_done, len(pages), len(notes))
            except Exception as e:
                self.master.after(0, self._on_step_error, 1, str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_step2_done(self, pages: int, notes: int):
        self._set_busy(False)
        self._set_step_status(
            1, _DONE,
            tr("tool.ppt2video.info_pages_notes", pages=pages, notes=notes))
        self._step_buttons[2].config(state="normal")
        self._status_var.set(tr("tool.ppt2video.status_step_done", step=2))
        self.set_done()

    def _run_step3(self):
        if self._use_existing_audio_var.get():
            audio_count = self._count_files("audio", "*.mp3")
            if audio_count > 0:
                self._set_step_status(
                    2, _DONE,
                    tr("tool.ppt2video.info_audio", count=audio_count))
                self._step_buttons[3].config(state="normal")
                self._status_var.set(tr("tool.ppt2video.status_step_done", step=3))
                return
            self.set_warning(tr("tool.ppt2video.error_no_audio"))
            return

        voice_id = self._voice_id_var.get().strip()
        if not voice_id:
            self.set_warning(tr("tool.ppt2video.error_no_voice_id"))
            self._status_var.set(tr("tool.ppt2video.error_no_voice_id"))
            return

        notes_dir = os.path.join(self._workdir, "notes")
        if not os.path.isdir(notes_dir) or self._count_files("notes", "*.txt") == 0:
            self.set_warning(tr("tool.ppt2video.error_no_notes"))
            self._status_var.set(tr("tool.ppt2video.error_no_notes"))
            return

        self._set_busy(True)
        self._set_step_status(2, _RUNNING)
        self._cancel_flag = False

        def work():
            try:
                from core.pptx_pipeline import synthesize_all_notes
                paths = synthesize_all_notes(
                    notes_dir,
                    os.path.join(self._workdir, "audio"),
                    voice_id,
                    should_cancel=lambda: self._cancel_flag,
                    on_progress=lambda d, t, m: self.master.after(
                        0, self._status_var.set,
                        tr("tool.ppt2video.status_tts_progress", done=d, total=t)),
                )
                count = sum(1 for p in paths if p)
                self.master.after(0, self._on_step3_done, count)
            except Exception as e:
                self.master.after(0, self._on_step_error, 2, str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_step3_done(self, count: int):
        self._set_busy(False)
        self._set_step_status(
            2, _DONE,
            tr("tool.ppt2video.info_audio", count=count))
        self._step_buttons[3].config(state="normal")
        self._status_var.set(tr("tool.ppt2video.status_step_done", step=3))
        self.set_done()

    def _run_step4(self):
        if not self._enable_subs_var.get():
            self._set_step_status(3, _DONE,
                                  tr("tool.ppt2video.subs_skipped"))
            self._step_buttons[4].config(state="normal")
            self._status_var.set(tr("tool.ppt2video.subs_skipped"))
            return

        notes_dir = os.path.join(self._workdir, "notes")
        audio_dir = os.path.join(self._workdir, "audio")
        if self._count_files("notes", "*.txt") == 0:
            self.set_warning(tr("tool.ppt2video.error_no_notes"))
            self._status_var.set(tr("tool.ppt2video.error_no_notes"))
            return
        if self._count_files("audio", "*.mp3") == 0:
            self.set_warning(tr("tool.ppt2video.error_no_audio"))
            self._status_var.set(tr("tool.ppt2video.error_no_audio"))
            return

        self._set_busy(True)
        self._set_step_status(3, _RUNNING)
        self._status_var.set(tr("tool.ppt2video.status_generating_subs"))

        def work():
            try:
                from core.pptx_pipeline import generate_all_subs
                paths = generate_all_subs(
                    notes_dir, audio_dir,
                    os.path.join(self._workdir, "subs"),
                    on_progress=lambda d, t, m: self.master.after(
                        0, self._status_var.set,
                        tr("tool.ppt2video.status_generating_subs") + f" {d}/{t}"),
                )
                count = sum(1 for p in paths if p)
                self.master.after(0, self._on_step4_done, count)
            except Exception as e:
                self.master.after(0, self._on_step_error, 3, str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_step4_done(self, count: int):
        self._set_busy(False)
        self._set_step_status(
            3, _DONE,
            tr("tool.ppt2video.info_subs", count=count))
        self._step_buttons[4].config(state="normal")
        self._status_var.set(tr("tool.ppt2video.status_step_done", step=4))
        self.set_done()

    def _run_step5(self):
        if self._count_files("pages", "*.png") == 0:
            self.set_warning(tr("tool.ppt2video.error_no_pages"))
            self._status_var.set(tr("tool.ppt2video.error_no_pages"))
            return
        if self._count_files("audio", "*.mp3") == 0:
            self.set_warning(tr("tool.ppt2video.error_no_audio"))
            self._status_var.set(tr("tool.ppt2video.error_no_audio"))
            return

        self._set_busy(True)
        self._set_step_status(4, _RUNNING)
        self._status_var.set(tr("tool.ppt2video.status_composing"))

        def work():
            try:
                from core.pptx_pipeline import compose_all
                output = os.path.join(self._workdir, "output.mp4")
                compose_all(
                    os.path.join(self._workdir, "pages"),
                    os.path.join(self._workdir, "audio"),
                    os.path.join(self._workdir, "subs"),
                    output,
                    on_progress=lambda d, t, m: self.master.after(
                        0, self._status_var.set,
                        tr("tool.ppt2video.status_composing") + f" {d}/{t}"),
                )
                self.master.after(0, self._on_step5_done)
            except Exception as e:
                self.master.after(0, self._on_step_error, 4, str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_step5_done(self):
        self._set_busy(False)
        self._set_step_status(4, _DONE)
        self._status_var.set(tr("tool.ppt2video.status_all_done"))
        self.set_done()

    def _on_step_error(self, step_idx: int, msg: str):
        self._set_busy(False)
        self._set_step_status(step_idx, _ERROR)
        self.set_error(msg)
        self._status_var.set(msg)

    def _run_all(self):
        self._run_sequential(0)

    def _run_from_current(self):
        start = 0
        for i, s in enumerate(self._step_status):
            if s != _DONE:
                start = i
                break
        self._run_sequential(start)

    def _run_sequential(self, start_idx: int):
        """Run steps start_idx..4 in sequence, each on completion triggers next."""
        if start_idx > 4:
            self._status_var.set(tr("tool.ppt2video.status_all_done"))
            return

        original_callbacks = {}

        def chain_step(idx: int):
            if idx > 4:
                return
            step_done_methods = [
                None,  # step1 has no async callback
                "_on_step2_done",
                "_on_step3_done",
                "_on_step4_done",
                "_on_step5_done",
            ]
            method_name = step_done_methods[idx]
            if method_name:
                original = getattr(self, method_name)
                original_callbacks[idx] = original

                def wrapper(*args, _orig=original, _idx=idx):
                    _orig(*args)
                    setattr(self, step_done_methods[_idx], _orig)
                    chain_step(_idx + 1)

                setattr(self, method_name, wrapper)

            steps = [
                self._run_step1,
                self._run_step2,
                self._run_step3,
                self._run_step4,
                self._run_step5,
            ]

            if idx == 0:
                if self._step_status[0] != _DONE:
                    self._status_var.set(tr("tool.ppt2video.status_not_implemented"))
                    return
                chain_step(1)
            else:
                steps[idx]()

        chain_step(start_idx)

    # ── File browsing ────────────────────────────────────────────────────

    def _browse_pptx(self):
        path = filedialog.askopenfilename(
            title=tr("tool.ppt2video.dialog_select_pptx"),
            filetypes=[("PowerPoint", "*.pptx"), ("All files", "*.*")],
        )
        if not path:
            return
        self._import_pptx(path)

    def _import_pptx(self, src: str):
        os.makedirs(self._workdir, exist_ok=True)
        dst = os.path.join(self._workdir, "source.pptx")
        try:
            shutil.copy2(src, dst)
        except OSError as e:
            self.set_error(tr("tool.ppt2video.error_copy_pptx", e=str(e)))
            self._set_step_status(0, _ERROR)
            return

        self._pptx_label.config(text=os.path.basename(src))
        self._set_step_status(0, _DONE)
        self._step_buttons[1].config(state="normal")
        self._status_var.set(tr("tool.ppt2video.status_pptx_imported"))
        self.log(f"PPT imported: {src}")

    def _open_workdir(self):
        if self._workdir:
            os.makedirs(self._workdir, exist_ok=True)
            os.startfile(self._workdir)

    # ── Button state helpers ─────────────────────────────────────────────

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        for btn in self._step_buttons:
            btn.config(state=state)
        self._btn_run_all.config(state=state)
        self._btn_run_from.config(state=state)
        if busy:
            self.set_busy()
        else:
            self.set_idle()
