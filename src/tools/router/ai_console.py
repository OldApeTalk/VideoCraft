"""AI Console — single-tab provider/key/routing matrix + call stats.

UI layout:
  Tab 1 (Routing): one big grid where every row is a (provider, model)
    pair. Each row shows the provider's key status / Edit / Test buttons
    on its first model row, and a column of radio buttons per task. The
    column-grouped radios make "task → exactly one provider+model" the
    natural interaction. ASR/TTS providers occupy a single row each.
    Providers without auth render with disabled radios (greyed out).
  Tab 2 (Stats): per-provider call counters; unchanged from M6.

Per architecture principle 1, this tool is an "infrastructure console"
and is allowed to import core.ai directly.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from tools.base import ToolBase
from i18n import tr

from core import ai
from core import prompts as _prompts
from core.ai.router import router
from core.ai import config as _ai_cfg
from core.ai.config import keys_dir as _keys_dir


# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_int_range(value: str, *, minimum: int, maximum: int, field_label: str) -> int:
    try:
        parsed = int(value.strip())
    except Exception as e:
        raise ValueError(tr("tool.router.error_invalid_number", field=field_label)) from e
    if parsed < minimum or parsed > maximum:
        raise ValueError(tr("tool.router.error_out_of_range",
                            field=field_label, min=minimum, max=maximum))
    return parsed


def _task_short_label(task_id: str) -> str:
    """Short i18n header label for a task (matrix column heading)."""
    return tr(f"tool.router.task_header.{task_id}")


def _row_value(provider: str, model: str) -> str:
    """Encode a (provider, model) pair as a single radio value string."""
    return f"{provider}::{model}"


def _decode_value(value: str) -> tuple[str, str]:
    """Inverse of _row_value."""
    if "::" in value:
        p, m = value.split("::", 1)
        return p, m
    return value, ""


# ── AI Console tool ─────────────────────────────────────────────────────────

class AIConsoleApp(ToolBase):
    def __init__(self, master, initial_file=None):
        self.master = master
        master.title(tr("tool.router.title"))
        master.geometry("1080x640")

        nb = ttk.Notebook(master)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_routing = tk.Frame(nb, padx=8, pady=8)
        self.tab_prompts = tk.Frame(nb, padx=8, pady=8)
        self.tab_stats   = tk.Frame(nb, padx=12, pady=10)

        nb.add(self.tab_routing, text=tr("tool.router.tab_routing"))
        nb.add(self.tab_prompts, text=tr("tool.router.tab_prompts"))
        nb.add(self.tab_stats,   text=tr("tool.router.tab_stats"))
        nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

        self._build_routing_tab()
        self._build_prompts_tab()
        self._build_stats_tab()

    def _on_tab_change(self, event):
        nb = event.widget
        if nb.index(nb.select()) == 2:  # Stats tab (now index 2 after Prompts)
            self._refresh_stats()

    # ── Routing tab (the merged matrix) ─────────────────────────────────────

    def _build_routing_tab(self):
        tab = self.tab_routing

        # Top help line
        tk.Label(tab,
                 text=tr("tool.router.routing_prompt"),
                 font=("", 9), fg="#555", wraplength=1000, justify="left",
                 ).pack(anchor="w", pady=(0, 8))

        # Scrollable grid container — provider list can grow as users add
        # custom OpenAI-compat endpoints / new providers. Embed in a Canvas
        # for vertical scrolling.
        outer = tk.Frame(tab)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        grid_holder = tk.Frame(canvas)
        canvas.create_window((0, 0), window=grid_holder, anchor="nw")
        grid_holder.bind("<Configure>",
                         lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Mouse-wheel scroll on Windows/macOS
        def _on_wheel(e):
            canvas.yview_scroll(int(-e.delta / 120), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        self._build_routing_grid(grid_holder)

    def _build_routing_grid(self, parent):
        # Per-task selected value StringVars (each holds "provider::model")
        current_routing = router.get_task_routing()
        self._task_vars: dict[str, tk.StringVar] = {}
        for tid, _cat, _label in _ai_cfg.TASKS:
            cell = current_routing.get(tid, {})
            self._task_vars[tid] = tk.StringVar(
                value=_row_value(cell.get("provider", ""), cell.get("model", ""))
            )

        # Provider button widgets keyed by provider name (so refresh / test
        # state changes can target them without rebuilding the whole grid).
        self._test_buttons: dict[str, tk.Button] = {}

        # Header row
        col = 0
        tk.Label(parent, text=tr("tool.router.col_provider_model"),
                 font=("", 9, "bold"), anchor="w", width=22,
                 ).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 4))
        col += 1
        tk.Label(parent, text=tr("tool.router.col_key_status"),
                 font=("", 9, "bold"), anchor="w", width=18,
                 ).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 4))
        col += 1
        tk.Label(parent, text="", width=6,
                 ).grid(row=0, column=col, padx=2)  # Edit
        col += 1
        tk.Label(parent, text="", width=6,
                 ).grid(row=0, column=col, padx=2)  # Test
        col += 1
        # Task header columns
        self._task_col_index: dict[str, int] = {}
        for tid, _cat, _label in _ai_cfg.TASKS:
            self._task_col_index[tid] = col
            tk.Label(parent, text=_task_short_label(tid),
                     font=("", 9, "bold"), anchor="center", width=11,
                     wraplength=80, justify="center",
                     ).grid(row=0, column=col, padx=2, pady=(0, 4))
            col += 1

        # Separator
        ttk.Separator(parent, orient="horizontal").grid(
            row=1, column=0, columnspan=col, sticky="ew", pady=2)

        # Provider rows. Iterate in a stable display order:
        #   LLM providers first (in router._providers order), then ASR, then TTS.
        row_idx = 2
        # LLM providers
        for name, cfg in router._providers.items():
            row_idx = self._build_provider_block(parent, row_idx, name, cfg, "llm")
        # ASR providers
        for name, cfg in router._asr_providers.items():
            row_idx = self._build_provider_block(parent, row_idx, name, cfg, "asr")
        # TTS providers
        for name, cfg in router._tts_providers.items():
            row_idx = self._build_provider_block(parent, row_idx, name, cfg, "tts")

    def _build_provider_block(self, parent, row_start: int, name: str,
                              cfg: dict, category: str) -> int:
        """Render the rows for one provider. LLM providers list every model
        as a separate row; ASR/TTS get one row each.

        Returns the next available row index after this block.
        """
        # Determine the model list to render rows for
        if category == "llm":
            models = list(cfg.get("models", []))
            if not models:
                models = [""]   # Render a single placeholder row even with no models
        else:
            # ASR / TTS — single row, model field unused (provider-only routing)
            models = [""]

        is_available = self._provider_available(cfg)
        key_status_text, key_status_color = self._key_status(cfg)
        display_name = cfg.get("name", name)

        for i, model in enumerate(models):
            row = row_start + i
            # First row of the provider block carries name + key + buttons
            if i == 0:
                # Provider/model label cell: bold provider name + model below
                label_frame = tk.Frame(parent)
                label_frame.grid(row=row, column=0, sticky="w", padx=4, pady=2)
                tk.Label(label_frame, text=display_name,
                         font=("", 9, "bold"), anchor="w",
                         ).pack(anchor="w")
                if model and category == "llm":
                    tk.Label(label_frame, text=f"  {model}",
                             font=("", 8), fg="#555",
                             ).pack(anchor="w")

                # Key status
                tk.Label(parent, text=key_status_text,
                         fg=key_status_color, anchor="w", font=("", 9),
                         ).grid(row=row, column=1, sticky="w", padx=4, pady=2)

                # Edit button
                tk.Button(parent, text=tr("tool.router.btn_edit"), width=5,
                          command=lambda n=name, c=cfg, cat=category:
                                  self._open_edit_dialog(n, c, cat)
                          ).grid(row=row, column=2, padx=2)

                # Test button
                test_btn = tk.Button(
                    parent, text=tr("tool.router.btn_test"), width=5,
                    command=lambda n=name, cat=category:
                            self._run_provider_test(n, cat),
                )
                # Phase 1: only LLM providers support quick test;
                # disable Test for non-LLM (with tooltip via state)
                # and for any provider without auth.
                if category != "llm" or not is_available:
                    test_btn.configure(state="disabled")
                test_btn.grid(row=row, column=3, padx=2)
                self._test_buttons[name] = test_btn
            else:
                # Subsequent rows: indented model label, no key/buttons
                tk.Label(parent, text=f"   {model}",
                         font=("", 9), anchor="w", fg="#333",
                         ).grid(row=row, column=0, sticky="w", padx=4, pady=2)

            # Task radio cells
            row_value = _row_value(name, model) if category == "llm" else _row_value(name, "")
            for tid, cat, _label in _ai_cfg.TASKS:
                col = self._task_col_index[tid]
                if cat != category:
                    # Wrong category for this task — show a dash, no widget
                    tk.Label(parent, text="—", fg="#bbb",
                             ).grid(row=row, column=col, padx=2, pady=2)
                    continue
                rb = ttk.Radiobutton(
                    parent, value=row_value, variable=self._task_vars[tid],
                    command=lambda t=tid, v=row_value: self._on_radio_change(t, v),
                )
                if not is_available:
                    rb.configure(state="disabled")
                rb.grid(row=row, column=col, padx=2, pady=2)

        # Trailing thin separator between providers for readability
        sep_row = row_start + len(models)
        ttk.Separator(parent, orient="horizontal").grid(
            row=sep_row, column=0, columnspan=4 + len(_ai_cfg.TASKS),
            sticky="ew", pady=1,
        )
        return sep_row + 1

    @staticmethod
    def _provider_available(cfg: dict) -> bool:
        """Return True if this provider can actually be used (auth present
        for non-claude_code, always-True for claude_code)."""
        return _ai_cfg.has_auth(cfg)

    def _on_radio_change(self, task_id: str, row_value: str):
        provider, model = _decode_value(row_value)
        router.set_task_routing(task_id, provider, model)

    def _rebuild_routing_tab(self):
        for w in self.tab_routing.winfo_children():
            w.destroy()
        self._build_routing_tab()

    # ── Edit dialog (provider key + base_url + models + refresh) ────────────

    def _open_edit_dialog(self, name: str, cfg: dict, category: str):
        if cfg.get("type") == "claude_code":
            self._open_claude_code_dialog(name, cfg)
            return
        if category == "llm":
            self._open_llm_edit_dialog(name, cfg)
            return
        # ASR / TTS dialog
        self._open_asr_tts_edit_dialog(name, cfg, category)

    def _open_llm_edit_dialog(self, name: str, cfg: dict):
        dlg = tk.Toplevel(self.master)
        dlg.title(tr("tool.router.edit_dialog_title", name=name))
        dlg.geometry("560x420")
        dlg.resizable(False, False)
        dlg.grab_set()

        r = 0
        tk.Label(dlg, text=tr("tool.router.label_api_key"),
                 anchor="e", width=12).grid(
            row=r, column=0, padx=10, pady=10, sticky="e")
        key_var = tk.StringVar()
        key_entry = tk.Entry(dlg, textvariable=key_var, width=42, show="*")
        key_entry.grid(row=r, column=1, columnspan=2, pady=10, sticky="w")
        kp = os.path.join(_keys_dir(), cfg.get("key_file", ""))
        if kp and os.path.exists(kp):
            with open(kp, "r", encoding="utf-8") as f:
                key_var.set(f.read().strip())
        show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dlg, text=tr("tool.router.label_show"), variable=show_var,
                        command=lambda: key_entry.config(show="" if show_var.get() else "*"),
                        ).grid(row=r, column=3, padx=6)
        r += 1

        url_var = None
        if cfg.get("type") == "openai_compatible":
            tk.Label(dlg, text="Base URL:", anchor="e", width=12).grid(
                row=r, column=0, padx=10, pady=8, sticky="e")
            url_var = tk.StringVar(value=cfg.get("base_url", ""))
            tk.Entry(dlg, textvariable=url_var, width=52).grid(
                row=r, column=1, columnspan=3, pady=8, sticky="w")
            r += 1

        # Models text area + Refresh-from-API button
        tk.Label(dlg, text=tr("tool.router.label_models"),
                 anchor="ne", width=12).grid(
            row=r, column=0, padx=10, pady=8, sticky="ne")
        models_text = tk.Text(dlg, height=6, width=46, wrap="word")
        models_text.grid(row=r, column=1, columnspan=2, pady=8, sticky="w")
        models_text.insert("1.0", ", ".join(cfg.get("models", [])))

        refresh_status_var = tk.StringVar(value="")

        def refresh_models():
            new_key = key_var.get().strip()
            new_url = url_var.get().strip() if url_var is not None else cfg.get("base_url", "")
            if not new_key:
                messagebox.showerror(tr("dialog.common.error"),
                                     tr("tool.router.error_key_empty"), parent=dlg)
                return
            refresh_status_var.set(tr("tool.router.refresh_models_busy"))
            refresh_btn.configure(state="disabled")
            dlg.update_idletasks()

            def _do():
                try:
                    # Inject the (possibly unsaved) key+url into a temp config
                    # call. Easiest: write the key file first, update base_url,
                    # then call list_models. But that has side effects. Cleaner:
                    # call the provider module directly.
                    if cfg.get("type") == "gemini":
                        from core.ai.providers import gemini as _g
                        models = _g.list_models(new_key)
                    elif cfg.get("type") == "openai_compatible":
                        if not new_url:
                            raise RuntimeError(tr("tool.router.error_no_base_url"))
                        from core.ai.providers import openai_compat as _oc
                        models = _oc.list_models(new_key, new_url)
                    else:
                        raise RuntimeError(tr("tool.router.refresh_unsupported"))
                    self.master.after(0, lambda m=models: _apply(m))
                except Exception as e:
                    err = str(e)
                    self.master.after(0,
                        lambda em=err: refresh_status_var.set(
                            tr("tool.router.refresh_models_fail", e=em[:120])))
                finally:
                    self.master.after(0, lambda: refresh_btn.configure(state="normal"))

            def _apply(models):
                models_text.delete("1.0", "end")
                models_text.insert("1.0", ", ".join(models))
                refresh_status_var.set(tr("tool.router.refresh_models_ok", count=len(models)))

            threading.Thread(target=_do, daemon=True).start()

        refresh_btn = tk.Button(dlg, text=tr("tool.router.btn_refresh_models"),
                                command=refresh_models, width=14)
        refresh_btn.grid(row=r, column=3, padx=6, pady=8, sticky="n")
        r += 1

        tk.Label(dlg, textvariable=refresh_status_var,
                 fg="#228B22", font=("", 8), anchor="w",
                 ).grid(row=r, column=1, columnspan=3, sticky="w", padx=8)
        r += 1

        def save():
            key = key_var.get().strip()
            if not key:
                messagebox.showerror(tr("dialog.common.error"),
                                     tr("tool.router.error_key_empty"), parent=dlg)
                return
            kp_save = os.path.join(_keys_dir(), cfg.get("key_file", ""))
            if kp_save:
                os.makedirs(os.path.dirname(kp_save), exist_ok=True)
                with open(kp_save, "w", encoding="utf-8") as f:
                    f.write(key)
            kwargs = {}
            if url_var is not None:
                kwargs["base_url"] = url_var.get().strip()
            raw = models_text.get("1.0", "end").strip()
            kwargs["models"] = [m.strip() for m in raw.split(",") if m.strip()]
            router.update_provider(name, **kwargs)
            messagebox.showinfo(tr("tool.router.saved_title"),
                                tr("tool.router.saved_config_msg", name=name), parent=dlg)
            self._rebuild_routing_tab()
            dlg.destroy()

        btn_row = tk.Frame(dlg)
        btn_row.grid(row=r, column=0, columnspan=4, pady=14)
        tk.Button(btn_row, text=tr("tool.router.btn_save"), command=save,
                  width=10).pack(side="left", padx=10)
        tk.Button(btn_row, text=tr("tool.router.btn_cancel"), command=dlg.destroy,
                  width=10).pack(side="left")

    def _open_claude_code_dialog(self, name: str, cfg: dict):
        dlg = tk.Toplevel(self.master)
        dlg.title(tr("tool.router.edit_dialog_title", name=name))
        dlg.geometry("500x340")
        dlg.resizable(False, False)
        dlg.grab_set()

        r = 0
        tk.Label(dlg, text=tr("tool.router.label_executable"), anchor="e", width=14).grid(
            row=r, column=0, padx=10, pady=(14, 6), sticky="e")
        exec_var = tk.StringVar(value=cfg.get("executable", "claude"))
        tk.Entry(dlg, textvariable=exec_var, width=42).grid(
            row=r, column=1, columnspan=3, pady=(14, 6), sticky="w")
        r += 1

        tk.Label(dlg, text=tr("tool.router.label_timeout_sec"), anchor="e", width=14).grid(
            row=r, column=0, padx=10, pady=6, sticky="e")
        timeout_var = tk.StringVar(value=str(cfg.get("timeout_sec", 600)))
        tk.Entry(dlg, textvariable=timeout_var, width=14).grid(
            row=r, column=1, pady=6, sticky="w")
        r += 1

        tk.Label(dlg, text=tr("tool.router.label_models"), anchor="ne", width=14).grid(
            row=r, column=0, padx=10, pady=6, sticky="ne")
        models_text = tk.Text(dlg, height=4, width=42, wrap="word")
        models_text.grid(row=r, column=1, columnspan=3, pady=6, sticky="w")
        models_text.insert("1.0", ", ".join(cfg.get("models", [])))
        r += 1

        tk.Label(
            dlg, text=tr("tool.router.claudecode_hint"),
            font=("", 8), fg="gray", justify="left", wraplength=440,
        ).grid(row=r, column=0, columnspan=4, padx=12, pady=(8, 4), sticky="w")
        r += 1

        def save():
            executable = exec_var.get().strip() or "claude"
            try:
                timeout_sec = _parse_int_range(
                    timeout_var.get(), minimum=10, maximum=3600,
                    field_label=tr("tool.router.label_timeout_sec"),
                )
            except ValueError as e:
                messagebox.showerror(tr("dialog.common.error"), str(e), parent=dlg)
                return
            raw = models_text.get("1.0", "end")
            models = [m.strip() for m in raw.replace("\n", ",").split(",") if m.strip()]
            router.update_provider(
                name,
                executable=executable,
                timeout_sec=timeout_sec,
                models=models,
            )
            messagebox.showinfo(tr("tool.router.saved_title"),
                                tr("tool.router.saved_config_msg", name=name), parent=dlg)
            self._rebuild_routing_tab()
            dlg.destroy()

        btn_row = tk.Frame(dlg)
        btn_row.grid(row=r, column=0, columnspan=4, pady=14)
        tk.Button(btn_row, text=tr("tool.router.btn_save"), command=save, width=10).pack(side="left", padx=10)
        tk.Button(btn_row, text=tr("tool.router.btn_cancel"), command=dlg.destroy, width=10).pack(side="left")

    def _open_asr_tts_edit_dialog(self, name: str, cfg: dict, category: str):
        # ASR has timeout fields; TTS has only the key.
        is_asr = (category == "asr")
        display_name = cfg.get("name", name)
        dlg = tk.Toplevel(self.master)
        dlg.title(tr("tool.router.edit_dialog_title", name=display_name))
        dlg.geometry("560x300" if is_asr else "560x180")
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text=tr("tool.router.label_api_key"),
                 anchor="e", width=12).grid(row=0, column=0, padx=10, pady=16, sticky="e")
        key_var = tk.StringVar()
        key_entry = tk.Entry(dlg, textvariable=key_var, width=38, show="*")
        key_entry.grid(row=0, column=1, columnspan=2, pady=16, sticky="w")
        kp = os.path.join(_keys_dir(), cfg.get("key_file", ""))
        if kp and os.path.exists(kp):
            with open(kp, "r", encoding="utf-8") as f:
                key_var.set(f.read().strip())
        show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dlg, text=tr("tool.router.label_show"), variable=show_var,
                        command=lambda: key_entry.config(show="" if show_var.get() else "*"),
                        ).grid(row=0, column=3, padx=6)

        connect_var = tk.StringVar(value=str(cfg.get("connect_timeout_sec", 60)))
        read_var    = tk.StringVar(value=str(cfg.get("read_timeout_sec", 120)))
        retries_var = tk.StringVar(value=str(cfg.get("max_retries", 1)))

        if is_asr:
            tk.Label(dlg, text=tr("tool.router.label_connect_timeout_sec"),
                     anchor="e", width=12).grid(row=1, column=0, padx=10, pady=6, sticky="e")
            tk.Entry(dlg, textvariable=connect_var, width=14).grid(row=1, column=1, pady=6, sticky="w")
            tk.Label(dlg, text=tr("tool.router.label_read_timeout_sec"),
                     anchor="e", width=12).grid(row=2, column=0, padx=10, pady=6, sticky="e")
            tk.Entry(dlg, textvariable=read_var, width=14).grid(row=2, column=1, pady=6, sticky="w")
            tk.Label(dlg, text=tr("tool.router.label_max_retries"),
                     anchor="e", width=12).grid(row=3, column=0, padx=10, pady=6, sticky="e")
            tk.Entry(dlg, textvariable=retries_var, width=14).grid(row=3, column=1, pady=6, sticky="w")
            tk.Label(dlg, text=tr("tool.router.asr_retry_hint"),
                     font=("", 8), fg="gray", justify="left", wraplength=430,
                     ).grid(row=4, column=0, columnspan=4, padx=12, pady=(8, 4), sticky="w")

        def save():
            key = key_var.get().strip()
            if not key:
                messagebox.showerror(tr("dialog.common.error"),
                                     tr("tool.router.error_key_empty"), parent=dlg)
                return
            if is_asr:
                try:
                    ct = _parse_int_range(connect_var.get(), minimum=5, maximum=300,
                                          field_label=tr("tool.router.label_connect_timeout_sec"))
                    rt = _parse_int_range(read_var.get(), minimum=30, maximum=600,
                                          field_label=tr("tool.router.label_read_timeout_sec"))
                    mr = _parse_int_range(retries_var.get(), minimum=1, maximum=10,
                                          field_label=tr("tool.router.label_max_retries"))
                except ValueError as e:
                    messagebox.showerror(tr("dialog.common.error"), str(e), parent=dlg)
                    return
            kp_save = os.path.join(_keys_dir(), cfg.get("key_file", ""))
            if kp_save:
                os.makedirs(os.path.dirname(kp_save), exist_ok=True)
                with open(kp_save, "w", encoding="utf-8") as f:
                    f.write(key)
            if is_asr:
                router.update_asr_provider(
                    name,
                    connect_timeout_sec=ct,
                    read_timeout_sec=rt,
                    max_retries=mr,
                )
            messagebox.showinfo(tr("tool.router.saved_title"),
                                tr("tool.router.saved_config_msg", name=display_name), parent=dlg)
            self._rebuild_routing_tab()
            dlg.destroy()

        btn_row = tk.Frame(dlg)
        btn_row.grid(row=5, column=0, columnspan=4, pady=14)
        tk.Button(btn_row, text=tr("tool.router.btn_save"), command=save,
                  width=10).pack(side="left", padx=10)
        tk.Button(btn_row, text=tr("tool.router.btn_cancel"), command=dlg.destroy,
                  width=10).pack(side="left")

    # ── Test button ─────────────────────────────────────────────────────────

    def _run_provider_test(self, name: str, category: str):
        if category != "llm":
            messagebox.showinfo(
                tr("tool.router.test_result_skipped_title", name=name),
                tr("tool.router.test_unsupported_for_category"),
                parent=self.master,
            )
            return

        btn = self._test_buttons.get(name)
        if btn is not None:
            btn.configure(state="disabled", text=tr("tool.router.btn_test_busy"))

        def _restore():
            if btn is not None:
                btn.configure(state="normal", text=tr("tool.router.btn_test"))

        def _run():
            try:
                txt = ai.complete(
                    "Please reply with the single word OK and nothing else.",
                    provider=name,
                )
                self.master.after(0,
                    lambda t=(txt or "").strip(): self._show_test_result(name, "ok", t))
            except Exception as e:
                err = str(e)
                self.master.after(0,
                    lambda em=err: self._show_test_result(name, "fail", em))
            finally:
                self.master.after(0, _restore)

        threading.Thread(target=_run, daemon=True).start()

    def _show_test_result(self, name: str, kind: str, message: str):
        title_key = {
            "ok":      "tool.router.test_result_ok_title",
            "fail":    "tool.router.test_result_fail_title",
            "skipped": "tool.router.test_result_skipped_title",
        }[kind]
        title = tr(title_key, name=name)
        snippet = message if len(message) <= 800 else message[:800] + "\n…"
        messagebox.showinfo(title, snippet, parent=self.master)

    # ── Key status ──────────────────────────────────────────────────────────

    def _key_status(self, cfg: dict):
        """Return (display_text, color)."""
        if cfg.get("type") == "claude_code":
            return tr("tool.router.status_claude_cli"), "#228B22"
        key_file = cfg.get("key_file", "")
        if not key_file:
            return tr("tool.router.status_no_key_needed"), "#555555"
        key_path = os.path.join(_keys_dir(), key_file)
        if not os.path.exists(key_path):
            return tr("tool.router.status_not_configured"), "#CC0000"
        with open(key_path, "r", encoding="utf-8") as f:
            key = f.read().strip()
        if not key:
            return tr("tool.router.status_key_empty"), "#CC0000"
        masked = key[:4] + "****" + key[-4:] if len(key) >= 8 else "****"
        return f"✅ {masked}", "#228B22"

    # ── Prompts tab (central prompt management) ─────────────────────────────

    def _build_prompts_tab(self):
        tab = self.tab_prompts

        tk.Label(
            tab,
            text=tr("tool.router.prompts_prompt"),
            font=("", 9), fg="#555", wraplength=1000, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        # Two-pane: task list on the left, editor on the right
        body = tk.Frame(tab)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, width=180)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        right = tk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        # Left: listbox of task ids with display labels
        tk.Label(left, text=tr("tool.router.col_task"), anchor="w",
                 font=("", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self._prompt_task_listbox = tk.Listbox(
            left, exportselection=False, font=("", 9))
        self._prompt_task_listbox.pack(fill="both", expand=True)
        self._prompt_tasks_in_order: list[str] = list(_prompts.list_tasks())
        for tid in self._prompt_tasks_in_order:
            label = self._task_label(tid)
            tag = " ●" if _prompts.is_overridden(tid) else ""
            self._prompt_task_listbox.insert("end", f"{label}{tag}")
        self._prompt_task_listbox.bind("<<ListboxSelect>>",
                                       lambda e: self._on_prompt_task_selected())

        # Right: prompt editor + placeholders + buttons
        meta_row = tk.Frame(right)
        meta_row.pack(fill="x", pady=(0, 4))
        self._prompt_title_var = tk.StringVar(value="")
        tk.Label(meta_row, textvariable=self._prompt_title_var,
                 font=("", 10, "bold"), anchor="w").pack(side="left")

        ph_row = tk.Frame(right)
        ph_row.pack(fill="x", pady=(0, 4))
        tk.Label(ph_row, text=tr("tool.router.placeholders_label"),
                 font=("", 8), fg="#555").pack(side="left")
        self._prompt_ph_var = tk.StringVar(value="")
        tk.Label(ph_row, textvariable=self._prompt_ph_var,
                 font=("", 8), fg="#888").pack(side="left", padx=(6, 0))

        editor_frame = tk.Frame(right)
        editor_frame.pack(fill="both", expand=True)
        self._prompt_editor = tk.Text(editor_frame, wrap="word",
                                      font=("Consolas", 10), undo=True)
        ed_vsb = ttk.Scrollbar(editor_frame, orient="vertical",
                               command=self._prompt_editor.yview)
        self._prompt_editor.configure(yscrollcommand=ed_vsb.set)
        self._prompt_editor.pack(side="left", fill="both", expand=True)
        ed_vsb.pack(side="right", fill="y")

        actions = tk.Frame(right)
        actions.pack(fill="x", pady=(6, 0))
        self._prompt_save_btn = tk.Button(
            actions, text=tr("tool.router.btn_save_prompt"),
            command=self._save_current_prompt, width=10)
        self._prompt_save_btn.pack(side="left", padx=(0, 6))
        self._prompt_reset_btn = tk.Button(
            actions, text=tr("tool.router.btn_reset_prompt"),
            command=self._reset_current_prompt, width=10)
        self._prompt_reset_btn.pack(side="left")

        self._prompt_status_var = tk.StringVar(value="")
        tk.Label(actions, textvariable=self._prompt_status_var,
                 fg="#228B22", font=("", 9)).pack(side="left", padx=10)

        self._current_prompt_task: str | None = None

        # Auto-select first task so the editor isn't blank on open
        if self._prompt_tasks_in_order:
            self._prompt_task_listbox.selection_set(0)
            self._on_prompt_task_selected()

    @staticmethod
    def _task_label(task_id: str) -> str:
        """Use the canonical TASKS catalog for display labels."""
        for tid, _cat, label in _ai_cfg.TASKS:
            if tid == task_id:
                return label
        return task_id

    def _on_prompt_task_selected(self):
        sel = self._prompt_task_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self._prompt_tasks_in_order):
            return
        task_id = self._prompt_tasks_in_order[idx]
        self._current_prompt_task = task_id
        self._prompt_title_var.set(self._task_label(task_id))
        ph = _prompts.placeholders(task_id)
        self._prompt_ph_var.set(", ".join(ph) if ph else tr("tool.router.no_placeholders"))
        self._prompt_editor.delete("1.0", "end")
        self._prompt_editor.insert("1.0", _prompts.get(task_id))
        self._prompt_status_var.set("")

    def _save_current_prompt(self):
        if not self._current_prompt_task:
            return
        content = self._prompt_editor.get("1.0", "end-1c")
        try:
            _prompts.set(self._current_prompt_task, content)
            self._prompt_status_var.set(tr("tool.router.prompt_saved"))
            self._refresh_prompt_listbox_marks()
        except Exception as e:
            messagebox.showerror(tr("dialog.common.error"), str(e), parent=self.master)
            return
        self.master.after(3000, lambda: self._prompt_status_var.set(""))

    def _reset_current_prompt(self):
        if not self._current_prompt_task:
            return
        if not messagebox.askyesno(
            tr("tool.router.reset_prompt_confirm_title"),
            tr("tool.router.reset_prompt_confirm_msg",
               name=self._task_label(self._current_prompt_task)),
            parent=self.master,
        ):
            return
        text = _prompts.reset(self._current_prompt_task)
        self._prompt_editor.delete("1.0", "end")
        self._prompt_editor.insert("1.0", text)
        self._prompt_status_var.set(tr("tool.router.prompt_reset_done"))
        self._refresh_prompt_listbox_marks()
        self.master.after(3000, lambda: self._prompt_status_var.set(""))

    def _refresh_prompt_listbox_marks(self):
        """Re-render listbox entries to show ● marker on overridden tasks."""
        sel = self._prompt_task_listbox.curselection()
        self._prompt_task_listbox.delete(0, "end")
        for tid in self._prompt_tasks_in_order:
            label = self._task_label(tid)
            tag = " ●" if _prompts.is_overridden(tid) else ""
            self._prompt_task_listbox.insert("end", f"{label}{tag}")
        if sel:
            self._prompt_task_listbox.selection_set(sel[0])

    # ── Stats tab (unchanged from M6) ───────────────────────────────────────

    def _build_stats_tab(self):
        tab = self.tab_stats

        cols   = ("provider", "calls", "errors", "error_rate", "last_used")
        labels = (tr("tool.router.col_provider"),
                  tr("tool.router.col_calls"),
                  tr("tool.router.col_errors"),
                  tr("tool.router.col_error_rate"),
                  tr("tool.router.col_last_used"))
        widths = (100, 80, 80, 70, 180)

        self.stats_tree = ttk.Treeview(tab, columns=cols,
                                       show="headings", height=10)
        for col, label, w in zip(cols, labels, widths):
            self.stats_tree.heading(col, text=label)
            self.stats_tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(tab, orient="vertical",
                            command=self.stats_tree.yview)
        self.stats_tree.configure(yscrollcommand=vsb.set)
        self.stats_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        btn_col = tk.Frame(tab)
        btn_col.pack(side="left", padx=10, anchor="n")
        tk.Button(btn_col, text=tr("tool.router.btn_refresh"),
                  command=self._refresh_stats, width=8).pack(pady=4)

        self._refresh_stats()

    def _refresh_stats(self):
        if not hasattr(self, "stats_tree"):
            return
        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)
        for name, s in router.get_stats().items():
            calls  = s["calls"]
            errors = s["errors"]
            rate   = f"{errors / calls * 100:.0f}%" if calls > 0 else "—"
            last   = s["last_used"] or tr("tool.router.never_used")
            self.stats_tree.insert("", "end", values=(name, calls, errors, rate, last))
