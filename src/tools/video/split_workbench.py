"""
Split Workbench — review, edit, and export AI-generated segments.

Loads a video + subs.txt (produced by `Subtitle → Generate Segments`), shows
each segment in an editable list, previews via an embedded VLC player, and
exports either as multiple files (split) or a single stitched file (merge).
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tools.base import ToolBase
from i18n import tr
from hub_logger import logger

from core import segment_model as sm
from core.segment_model import Segment
from core.video_concat import split_segments, merge_segments
from core.video_split import SplitMode
from ui.vlc_player import VlcPlayerFrame, is_vlc_available


# Display-label i18n key per mode. Enum values stay as stable internal ids.
_MODE_LABEL_KEYS: dict[SplitMode, str] = {
    SplitMode.FAST: "tool.split_workbench.mode.fast",
    SplitMode.KEYFRAME_SNAP: "tool.split_workbench.mode.keyframe_snap",
    SplitMode.ACCURATE: "tool.split_workbench.mode.accurate",
}
_MODE_TOOLTIP_KEYS: dict[SplitMode, str] = {
    SplitMode.FAST: "tool.split_workbench.mode.tooltip.fast",
    SplitMode.KEYFRAME_SNAP: "tool.split_workbench.mode.tooltip.keyframe_snap",
    SplitMode.ACCURATE: "tool.split_workbench.mode.tooltip.accurate",
}


def _get_video_duration(path: str) -> float:
    import subprocess
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
        return float(result.stdout.strip())
    except (ValueError, OSError):
        return 0.0


def _fmt_hms(sec: float) -> str:
    return sm.format_timestamp(sec)


def _fmt_duration(sec: float) -> str:
    s = max(0, int(round(sec)))
    h, rem = divmod(s, 3600)
    m, sec_r = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec_r:02d}"
    return f"{m}:{sec_r:02d}"


class SplitWorkbenchApp(ToolBase):
    def __init__(self, master, initial_file: str | None = None):
        self.master = master
        master.title(tr("tool.split_workbench.title"))
        master.geometry("1100x680")

        self.video_path_var = tk.StringVar()
        self.desc_path_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.status_var = tk.StringVar(value=tr("tool.split_workbench.status_idle"))

        self._segments: list[Segment] = []
        self._video_duration: float = 0.0
        self._selected_iid: str | None = None
        self._busy: bool = False

        # Split-mode state: store enum value (stable id) in the Var, map to
        # localized label via _MODE_LABEL_KEYS. Default to KEYFRAME_SNAP so
        # the workbench's out-of-the-box behavior aligns cuts to I-frames.
        self._split_mode_var = tk.StringVar(value=SplitMode.KEYFRAME_SNAP.value)
        self._mode_label_to_value: dict[str, str] = {}

        self._build_ui()

        if initial_file:
            self.video_path_var.set(initial_file)
            self._auto_output_dir(initial_file)
            self._try_load_video()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        m = self.master
        m.columnconfigure(0, weight=1)
        m.rowconfigure(1, weight=1)

        # Row 0: file pickers
        top = tk.Frame(m)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(4, weight=1)

        tk.Label(top, text=tr("tool.split_workbench.label_video")).grid(row=0, column=0, sticky="e")
        tk.Entry(top, textvariable=self.video_path_var).grid(row=0, column=1, sticky="ew", padx=4)
        tk.Button(top, text=tr("tool.split_workbench.browse"), command=self._browse_video).grid(row=0, column=2, padx=2)

        tk.Label(top, text=tr("tool.split_workbench.label_desc")).grid(row=0, column=3, sticky="e", padx=(8, 0))
        tk.Entry(top, textvariable=self.desc_path_var).grid(row=0, column=4, sticky="ew", padx=4)
        tk.Button(top, text=tr("tool.split_workbench.browse"), command=self._browse_desc).grid(row=0, column=5, padx=2)
        tk.Button(top, text=tr("tool.split_workbench.btn_load"), command=self._load_all).grid(row=0, column=6, padx=2)

        tk.Label(top, text=tr("tool.split_workbench.label_output_dir")).grid(row=1, column=0, sticky="e", pady=(4, 0))
        tk.Entry(top, textvariable=self.output_dir_var).grid(row=1, column=1, columnspan=4, sticky="ew", padx=4, pady=(4, 0))
        tk.Button(top, text=tr("tool.split_workbench.browse"), command=self._browse_output).grid(row=1, column=5, padx=2, pady=(4, 0))

        # Row 1: main split pane
        main = tk.PanedWindow(m, orient="horizontal", sashrelief="raised")
        main.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)

        # ── Left: segment list + detail editor ───────────────────────────
        left = tk.Frame(main)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        main.add(left, minsize=520)

        tree_wrap = tk.Frame(left)
        tree_wrap.grid(row=0, column=0, sticky="nsew")
        tree_wrap.columnconfigure(0, weight=1)
        tree_wrap.rowconfigure(0, weight=1)

        cols = ("sel", "idx", "start", "duration", "title")
        self._tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", selectmode="browse")
        headings = {
            "sel": tr("tool.split_workbench.col_sel"),
            "idx": tr("tool.split_workbench.col_idx"),
            "start": tr("tool.split_workbench.col_start"),
            "duration": tr("tool.split_workbench.col_duration"),
            "title": tr("tool.split_workbench.col_title"),
        }
        widths = {"sel": 40, "idx": 40, "start": 90, "duration": 80, "title": 280}
        anchors = {"sel": "center", "idx": "center", "start": "center", "duration": "center", "title": "w"}
        for c in cols:
            self._tree.heading(c, text=headings[c])
            self._tree.column(c, width=widths[c], anchor=anchors[c], stretch=(c == "title"))
        self._tree.grid(row=0, column=0, sticky="nsew")

        tree_scroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.grid(row=0, column=1, sticky="ns")

        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self._tree.bind("<Button-1>", self._on_row_click)
        self._tree.bind("<Double-1>", self._on_row_double_click)

        # Row operations
        ops = tk.Frame(left)
        ops.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        tk.Button(ops, text=tr("tool.split_workbench.btn_add"), command=self._add_row).pack(side="left", padx=2)
        tk.Button(ops, text=tr("tool.split_workbench.btn_delete"), command=self._delete_row).pack(side="left", padx=2)
        tk.Button(ops, text=tr("tool.split_workbench.btn_sort"), command=self._sort_rows).pack(side="left", padx=2)
        tk.Button(ops, text=tr("tool.split_workbench.btn_select_all"), command=lambda: self._toggle_all(True)).pack(side="left", padx=2)
        tk.Button(ops, text=tr("tool.split_workbench.btn_select_none"), command=lambda: self._toggle_all(False)).pack(side="left", padx=2)

        # Detail editor
        detail = tk.LabelFrame(left, text=tr("tool.split_workbench.detail_title"))
        detail.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        detail.columnconfigure(1, weight=1)

        tk.Label(detail, text=tr("tool.split_workbench.detail_start")).grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self._detail_start = tk.StringVar()
        tk.Entry(detail, textvariable=self._detail_start, width=14).grid(row=0, column=1, sticky="w", pady=4)

        tk.Label(detail, text=tr("tool.split_workbench.detail_title_label")).grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self._detail_title = tk.StringVar()
        tk.Entry(detail, textvariable=self._detail_title).grid(row=1, column=1, sticky="ew", padx=(0, 4), pady=4)

        tk.Button(detail, text=tr("tool.split_workbench.btn_apply"), command=self._apply_detail).grid(row=0, column=2, rowspan=2, padx=6)

        # ── Right: VLC player ────────────────────────────────────────────
        right = tk.Frame(main)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        main.add(right, minsize=400)

        self._player = VlcPlayerFrame(right)
        self._player.grid(row=0, column=0, sticky="nsew")

        if not self._player.is_available():
            logger.warning(tr("tool.split_workbench.log_vlc_missing"))

        # Row 2: export bar
        bar = tk.Frame(m)
        bar.grid(row=2, column=0, sticky="ew", padx=8, pady=6)
        bar.columnconfigure(5, weight=1)

        self._btn_save = tk.Button(bar, text=tr("tool.split_workbench.btn_save"), command=self._save_segments)
        self._btn_save.grid(row=0, column=0, padx=2)

        self._btn_split = tk.Button(bar, text=tr("tool.split_workbench.btn_export_split"), command=self._export_split)
        self._btn_split.grid(row=0, column=1, padx=2)

        # Split-mode selector sits between split and merge so it visually
        # belongs to the split flow (merge always re-encodes — no mode choice).
        tk.Label(bar, text=tr("tool.split_workbench.label_mode")).grid(row=0, column=2, padx=(8, 2))
        labels = [tr(_MODE_LABEL_KEYS[m]) for m in SplitMode]
        self._mode_label_to_value = {tr(_MODE_LABEL_KEYS[m]): m.value for m in SplitMode}
        current_label = tr(_MODE_LABEL_KEYS[SplitMode(self._split_mode_var.get())])
        self._cmb_mode = ttk.Combobox(
            bar, state="readonly", width=16, values=labels,
        )
        self._cmb_mode.set(current_label)
        self._cmb_mode.bind("<<ComboboxSelected>>", self._on_mode_selected)
        self._cmb_mode.grid(row=0, column=3, padx=2)
        self._install_mode_tooltip(self._cmb_mode)

        self._btn_merge = tk.Button(bar, text=tr("tool.split_workbench.btn_export_merge"), command=self._export_merge)
        self._btn_merge.grid(row=0, column=4, padx=(8, 2))

        self._progress = ttk.Progressbar(bar, mode="determinate", maximum=100)
        self._progress.grid(row=0, column=5, sticky="ew", padx=8)

        tk.Label(bar, textvariable=self.status_var, fg="#2196F3", anchor="w").grid(
            row=1, column=0, columnspan=6, sticky="ew", pady=(4, 0)
        )

        # Clean up VLC on window close
        try:
            self.master.bind("<Destroy>", self._on_destroy, add="+")
        except Exception:
            pass

    # ── Mode selector ─────────────────────────────────────────────────────

    def _on_mode_selected(self, _event: object = None) -> None:
        label = self._cmb_mode.get()
        value = self._mode_label_to_value.get(label)
        if value:
            self._split_mode_var.set(value)

    def _install_mode_tooltip(self, widget: tk.Widget) -> None:
        """Show the current mode's tooltip on hover. Lightweight Toplevel tip."""
        tip: dict[str, tk.Toplevel | None] = {"win": None}

        def show(_e: object = None) -> None:
            if tip["win"] is not None:
                return
            try:
                mode = SplitMode(self._split_mode_var.get())
            except ValueError:
                return
            text = tr(_MODE_TOOLTIP_KEYS[mode])
            w = tk.Toplevel(widget)
            w.wm_overrideredirect(True)
            x = widget.winfo_rootx() + 10
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            w.wm_geometry(f"+{x}+{y}")
            tk.Label(
                w, text=text, bg="#ffffe0", fg="#333",
                relief="solid", borderwidth=1, padx=6, pady=3,
                justify="left", wraplength=320,
            ).pack()
            tip["win"] = w

        def hide(_e: object = None) -> None:
            if tip["win"] is not None:
                tip["win"].destroy()
                tip["win"] = None

        widget.bind("<Enter>", show, add="+")
        widget.bind("<Leave>", hide, add="+")
        widget.bind("<<ComboboxSelected>>", lambda e: (hide(), show()), add="+")

    # ── File pickers ──────────────────────────────────────────────────────

    def _browse_video(self) -> None:
        path = filedialog.askopenfilename(
            title=tr("tool.split_workbench.dialog_video"),
            filetypes=[("Video files", "*.mp4 *.mkv *.avi *.mov"), ("All files", "*.*")],
        )
        if path:
            self.video_path_var.set(path)
            self._auto_output_dir(path)
            self._guess_desc_path(path)

    def _browse_desc(self) -> None:
        path = filedialog.askopenfilename(
            title=tr("tool.split_workbench.dialog_desc"),
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.desc_path_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title=tr("tool.split_workbench.dialog_output_dir"))
        if path:
            self.output_dir_var.set(path)

    def _auto_output_dir(self, video_path: str) -> None:
        if self.output_dir_var.get():
            return
        base = os.path.join(os.path.dirname(os.path.abspath(video_path)), "splits")
        self.output_dir_var.set(base)

    def _guess_desc_path(self, video_path: str) -> None:
        if self.desc_path_var.get():
            return
        video_dir = os.path.dirname(os.path.abspath(video_path))
        for candidate in ("subs.txt", "segments.txt"):
            p = os.path.join(video_dir, candidate)
            if os.path.exists(p):
                self.desc_path_var.set(p)
                return

    # ── Loading ───────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        self._try_load_video()
        self._try_load_desc()

    def _try_load_video(self) -> None:
        path = self.video_path_var.get()
        if not path or not os.path.exists(path):
            return
        self._video_duration = _get_video_duration(path)
        if self._video_duration <= 0:
            self._set_status(tr("tool.split_workbench.error_duration"), color="#f44747")
            return
        if self._player.is_available():
            try:
                self._player.load(path)
            except Exception as e:
                logger.warning(tr("tool.split_workbench.log_player_load_failed", e=e))
        self._refresh_tree()
        self._set_status(tr("tool.split_workbench.status_video_loaded",
                            duration=_fmt_hms(self._video_duration)))

    def _try_load_desc(self) -> None:
        path = self.desc_path_var.get()
        if not path or not os.path.exists(path):
            return
        try:
            segs = sm.load_from_file(path)
        except OSError as e:
            self._set_status(tr("tool.split_workbench.error_load_desc", e=e), color="#f44747")
            return
        if not segs:
            self._set_status(tr("tool.split_workbench.error_empty_desc"), color="#f0a500")
            return
        self._segments = segs
        self._refresh_tree()
        self._set_status(tr("tool.split_workbench.status_desc_loaded", n=len(segs)))

    # ── Tree rendering ────────────────────────────────────────────────────

    def _refresh_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        checked_before: set[int] = set()
        # Keep prior selection flags if re-rendering after an edit
        for iid in self._tree.get_children():
            pass  # cleared above
        for i, seg in enumerate(self._segments):
            dur = sm.duration_of(self._segments, i, self._video_duration)
            self._tree.insert(
                "", "end", iid=str(i),
                values=("✓", i + 1, _fmt_hms(seg.start_sec), _fmt_duration(dur), seg.title),
            )

    def _iter_rows(self):
        for iid in self._tree.get_children():
            yield iid, self._tree.item(iid, "values")

    def _selected_indices(self) -> list[int]:
        selected: list[int] = []
        for iid, values in self._iter_rows():
            if values and str(values[0]).strip() == "✓":
                selected.append(int(iid))
        return selected

    def _toggle_all(self, state: bool) -> None:
        mark = "✓" if state else ""
        for iid, values in list(self._iter_rows()):
            new_values = (mark,) + tuple(values[1:])
            self._tree.item(iid, values=new_values)

    # ── Row interaction ───────────────────────────────────────────────────

    def _on_row_click(self, event) -> None:
        region = self._tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self._tree.identify_column(event.x)
        if column == "#1":  # sel checkbox
            iid = self._tree.identify_row(event.y)
            if iid:
                values = list(self._tree.item(iid, "values"))
                values[0] = "" if values[0] == "✓" else "✓"
                self._tree.item(iid, values=values)
                return "break"

    def _on_row_select(self, _event) -> None:
        sel = self._tree.selection()
        if not sel:
            self._selected_iid = None
            return
        self._selected_iid = sel[0]
        idx = int(self._selected_iid)
        if 0 <= idx < len(self._segments):
            seg = self._segments[idx]
            self._detail_start.set(_fmt_hms(seg.start_sec))
            self._detail_title.set(seg.title)
            if self._player.is_available():
                self._player.seek(seg.start_sec)
                self._player.pause()

    def _on_row_double_click(self, _event) -> None:
        if self._selected_iid is None:
            return
        idx = int(self._selected_iid)
        if 0 <= idx < len(self._segments) and self._player.is_available():
            self._player.seek(self._segments[idx].start_sec)
            self._player.play()

    def _apply_detail(self) -> None:
        if self._selected_iid is None:
            return
        idx = int(self._selected_iid)
        if not (0 <= idx < len(self._segments)):
            return
        start_text = self._detail_start.get().strip()
        ts = sm.parse_timestamp(start_text)
        if ts is None:
            self._set_status(tr("tool.split_workbench.error_bad_timestamp", ts=start_text), color="#f0a500")
            return
        self._segments[idx] = Segment(start_sec=ts, title=self._detail_title.get().strip())
        self._refresh_tree()
        self._tree.selection_set(str(idx))
        self._set_status(tr("tool.split_workbench.status_row_applied", idx=idx + 1))

    def _add_row(self) -> None:
        if self._video_duration <= 0:
            self._set_status(tr("tool.split_workbench.error_no_video_loaded"), color="#f0a500")
            return
        if self._selected_iid is not None:
            idx = int(self._selected_iid)
            base = self._segments[idx]
            end = sm.end_of(self._segments, idx, self._video_duration)
            new_start = (base.start_sec + end) / 2.0
            new_seg = Segment(start_sec=new_start, title=tr("tool.split_workbench.new_segment_title"))
            self._segments.insert(idx + 1, new_seg)
        else:
            self._segments.append(Segment(start_sec=0.0, title=tr("tool.split_workbench.new_segment_title")))
        self._segments.sort(key=lambda s: s.start_sec)
        self._refresh_tree()

    def _delete_row(self) -> None:
        if self._selected_iid is None:
            return
        idx = int(self._selected_iid)
        if 0 <= idx < len(self._segments):
            self._segments.pop(idx)
            self._selected_iid = None
            self._refresh_tree()

    def _sort_rows(self) -> None:
        self._segments.sort(key=lambda s: s.start_sec)
        self._refresh_tree()

    # ── Save / export ─────────────────────────────────────────────────────

    def _save_segments(self) -> None:
        path = self.desc_path_var.get()
        if not path:
            path = filedialog.asksaveasfilename(
                title=tr("tool.split_workbench.dialog_save_desc"),
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt")],
            )
            if not path:
                return
            self.desc_path_var.set(path)
        try:
            sm.save_to_file(path, self._segments)
        except OSError as e:
            self._set_status(tr("tool.split_workbench.error_save", e=e), color="#f44747")
            return
        self._set_status(tr("tool.split_workbench.status_saved", path=path), color="#4caf50")

    def _export_split(self) -> None:
        self._run_export(mode="split")

    def _export_merge(self) -> None:
        self._run_export(mode="merge")

    def _run_export(self, mode: str) -> None:
        if self._busy:
            return
        video_path = self.video_path_var.get()
        if not video_path or not os.path.exists(video_path):
            self._set_status(tr("tool.split_workbench.error_no_video"), color="#f44747")
            return
        if not self._segments:
            self._set_status(tr("tool.split_workbench.error_no_segments"), color="#f44747")
            return
        if self._video_duration <= 0:
            self._video_duration = _get_video_duration(video_path)
            if self._video_duration <= 0:
                self._set_status(tr("tool.split_workbench.error_duration"), color="#f44747")
                return

        selected = self._selected_indices()
        if not selected:
            selected = list(range(len(self._segments)))

        issues = sm.validate(self._segments, self._video_duration)
        if issues:
            proceed = messagebox.askokcancel(
                tr("tool.split_workbench.confirm_title"),
                tr("tool.split_workbench.confirm_issues", issues="\n".join(issues[:10])),
            )
            if not proceed:
                return

        output_dir = self.output_dir_var.get()
        if not output_dir:
            self._set_status(tr("tool.split_workbench.error_no_output_dir"), color="#f44747")
            return

        total_sec = sum(
            sm.duration_of(self._segments, i, self._video_duration) for i in selected
        )

        if mode == "split":
            summary = tr(
                "tool.split_workbench.confirm_split",
                video=os.path.basename(video_path),
                output_dir=output_dir,
                count=len(selected),
                total=_fmt_duration(total_sec),
            )
        else:
            summary = tr(
                "tool.split_workbench.confirm_merge",
                video=os.path.basename(video_path),
                output_dir=output_dir,
                count=len(selected),
                total=_fmt_duration(total_sec),
            )

        if not messagebox.askokcancel(tr("tool.split_workbench.confirm_title"), summary):
            return

        # Stop player to release file handles on Windows before ffmpeg runs.
        if self._player.is_available():
            self._player.stop()

        self._busy = True
        self._set_buttons_state("disabled")
        self._progress["value"] = 0
        self.set_busy()

        def _progress_cb(done: int, total: int) -> None:
            pct = int(done / total * 100) if total > 0 else 0
            self.master.after(0, lambda: self._progress.configure(value=pct))
            self.master.after(
                0,
                lambda: self._set_status(
                    tr("tool.split_workbench.status_progress", done=done, total=total)
                ),
            )

        def _on_probe_start() -> None:
            self.master.after(
                0,
                lambda: self._set_status(tr("tool.split_workbench.status_probing")),
            )

        def _run() -> None:
            try:
                if mode == "split":
                    split_mode = SplitMode(self._split_mode_var.get())
                    outputs = split_segments(
                        video_path, self._segments, selected,
                        self._video_duration, output_dir,
                        progress_cb=_progress_cb,
                        mode=split_mode,
                        on_probe_start=_on_probe_start,
                    )
                    self.master.after(
                        0,
                        lambda: self._set_status(
                            tr("tool.split_workbench.status_split_done",
                               count=len(outputs), output_dir=output_dir),
                            color="#4caf50",
                        ),
                    )
                    logger.info(
                        f"Workbench split: {len(outputs)} segments "
                        f"({os.path.basename(video_path)}) → {output_dir}"
                    )
                else:
                    base = os.path.splitext(os.path.basename(video_path))[0]
                    out_path = os.path.join(output_dir, f"{base}_merged.mp4")
                    merge_segments(
                        video_path, self._segments, selected,
                        self._video_duration, out_path, progress_cb=_progress_cb,
                    )
                    self.master.after(
                        0,
                        lambda: self._set_status(
                            tr("tool.split_workbench.status_merge_done", path=out_path),
                            color="#4caf50",
                        ),
                    )
                    logger.info(
                        f"Workbench merge: {len(selected)} segments "
                        f"({os.path.basename(video_path)}) → {out_path}"
                    )
                self.set_done()
            except Exception as e:
                self.master.after(
                    0,
                    lambda exc=e: self._set_status(
                        tr("tool.split_workbench.status_failed", e=exc), color="#f44747"
                    ),
                )
                self.set_error(tr("tool.split_workbench.log_export_failed", e=e))
            finally:
                self.master.after(0, lambda: self._set_buttons_state("normal"))
                self.master.after(0, lambda: setattr(self, "_busy", False))

        threading.Thread(target=_run, daemon=True).start()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str = "#2196F3") -> None:
        self.status_var.set(text)

    def _set_buttons_state(self, state: str) -> None:
        for btn in (self._btn_save, self._btn_split, self._btn_merge):
            btn.configure(state=state)

    def _on_destroy(self, event) -> None:
        if event.widget is not self.master:
            return
        try:
            self._player.release()
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    SplitWorkbenchApp(root)
    root.mainloop()
