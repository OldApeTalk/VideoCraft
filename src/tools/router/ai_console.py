"""AI Console — unified provider / key / routing management (Hub tab).

Replaces the legacy `router_manager.RouterManagerWindow` Toplevel dialog.
Runs as a regular Hub tab (ToolBase) so it follows the same conventions
as every other tool. Three sub-tabs:

  1. Provider & Key — LLM / ASR / TTS provider rows with inline key status
     and per-provider edit dialogs.
  2. Routing Matrix — task × tier grid where each cell picks
     (provider, model) for a given task at a given tier. The data model
     is core.ai.config's task_routing; see AIRouterAndCoreAPI draft.
  3. Call Stats — in-memory per-provider counters.

Per architecture principle 1, this tool is an "infrastructure console"
and is allowed to import core.ai directly.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox

from tools.base import ToolBase
from i18n import tr

from core.ai.router import router
from core.ai.tiers import TIERS, TIER_PREMIUM, TIER_STANDARD, TIER_ECONOMY
from core.ai import config as _ai_cfg
from core.ai.config import keys_dir as _keys_dir


# ── Display text helpers (locale-aware) ──────────────────────────────────────

def _tier_display(tier: str) -> str:
    return {
        TIER_PREMIUM:  tr("tool.router.tier_premium_label"),
        TIER_STANDARD: tr("tool.router.tier_standard_label"),
        TIER_ECONOMY:  tr("tool.router.tier_economy_label"),
    }.get(tier, tier)


def _tier_hint(tier: str) -> str:
    return {
        TIER_PREMIUM:  tr("tool.router.tier_premium_desc"),
        TIER_STANDARD: tr("tool.router.tier_standard_desc"),
        TIER_ECONOMY:  tr("tool.router.tier_economy_desc"),
    }.get(tier, "")


def _parse_int_range(value: str, *, minimum: int, maximum: int, field_label: str) -> int:
    try:
        parsed = int(value.strip())
    except Exception as e:
        raise ValueError(tr("tool.router.error_invalid_number", field=field_label)) from e
    if parsed < minimum or parsed > maximum:
        raise ValueError(tr("tool.router.error_out_of_range",
                            field=field_label, min=minimum, max=maximum))
    return parsed


# ── AI Console tab ──────────────────────────────────────────────────────────

class AIConsoleApp(ToolBase):
    def __init__(self, master, initial_file=None):
        self.master = master
        master.title(tr("tool.router.title"))
        master.geometry("780x620")

        nb = ttk.Notebook(master)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_keys   = tk.Frame(nb, padx=12, pady=10)
        self.tab_matrix = tk.Frame(nb, padx=12, pady=10)
        self.tab_stats  = tk.Frame(nb, padx=12, pady=10)

        nb.add(self.tab_keys,   text=tr("tool.router.tab_keys"))
        nb.add(self.tab_matrix, text=tr("tool.router.tab_matrix"))
        nb.add(self.tab_stats,  text=tr("tool.router.tab_stats"))

        nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

        self._build_keys_tab()
        self._build_matrix_tab()
        self._build_stats_tab()

    def _on_tab_change(self, event):
        nb = event.widget
        if nb.index(nb.select()) == 2:  # Stats tab
            self._refresh_stats()

    # ── Tab 1: Provider & Key ───────────────────────────────────────────────

    def _build_keys_tab(self):
        tab = self.tab_keys

        hdr = tk.Frame(tab)
        hdr.pack(fill="x", pady=(0, 2))
        tk.Label(hdr, text=tr("tool.router.col_provider"),   width=10, anchor="w", font=("", 9, "bold")).pack(side="left")
        tk.Label(hdr, text=tr("tool.router.col_key_status"), width=24, anchor="w", font=("", 9, "bold")).pack(side="left")
        tk.Label(hdr, text=tr("tool.router.col_enabled"),    width=5,  anchor="w", font=("", 9, "bold")).pack(side="left")
        ttk.Separator(tab, orient="horizontal").pack(fill="x", pady=3)

        self._enabled_vars = {}
        for name, cfg in router._providers.items():
            self._build_provider_row(tab, name, cfg)

        ttk.Separator(tab, orient="horizontal").pack(fill="x", pady=(8, 4))

        tk.Label(tab, text=tr("tool.router.asr_providers_header"),
                 font=("", 9, "bold"), fg="#444").pack(anchor="w", pady=(0, 4))
        for name, cfg in router._asr_providers.items():
            self._build_asr_provider_row(tab, name, cfg)

        ttk.Separator(tab, orient="horizontal").pack(fill="x", pady=(8, 4))

        tk.Label(tab, text=tr("tool.router.tts_providers_header"),
                 font=("", 9, "bold"), fg="#444").pack(anchor="w", pady=(0, 4))
        for name, cfg in router._tts_providers.items():
            self._build_asr_provider_row(tab, name, cfg)   # Reused row layout

        ttk.Separator(tab, orient="horizontal").pack(fill="x", pady=(4, 8))
        tk.Label(tab,
                 text=tr("tool.router.key_hint"),
                 font=("", 8), fg="gray",
                 wraplength=640, justify="left").pack(anchor="w")

    def _build_provider_row(self, parent, name, cfg):
        row = tk.Frame(parent)
        row.pack(fill="x", pady=5)

        tk.Label(row, text=name, width=10, anchor="w").pack(side="left")

        status_text, status_color = self._key_status(cfg)
        tk.Label(row, text=status_text, width=24, anchor="w",
                 fg=status_color, font=("", 9)).pack(side="left")

        var = tk.BooleanVar(value=cfg.get("enabled", True))
        self._enabled_vars[name] = var

        def on_toggle(n=name, v=var):
            router.set_provider_enabled(n, v.get())

        ttk.Checkbutton(row, variable=var, command=on_toggle).pack(side="left", padx=4)
        tk.Button(row, text=tr("tool.router.btn_edit"), width=6,
                  command=lambda n=name, c=cfg: self._open_edit_dialog(n, c)
                  ).pack(side="left", padx=8)

    def _build_asr_provider_row(self, parent, name, cfg):
        row = tk.Frame(parent)
        row.pack(fill="x", pady=5)

        display = cfg.get("name", name)
        tk.Label(row, text=display, width=10, anchor="w").pack(side="left")

        status_text, status_color = self._key_status(cfg)
        tk.Label(row, text=status_text, width=24, anchor="w",
                 fg=status_color, font=("", 9)).pack(side="left")

        tk.Label(row, width=9).pack(side="left")   # Spacer to align columns
        tk.Button(row, text=tr("tool.router.btn_edit"), width=6,
                  command=lambda n=name, c=cfg: self._open_asr_edit_dialog(n, c)
                  ).pack(side="left", padx=8)

    def _open_asr_edit_dialog(self, name, cfg):
        # TTS providers share this dialog but skip timeout fields — see
        # the router_manager fix commit (66cb634). This tab carries the
        # same behavior.
        is_tts = name in router._tts_providers

        display_name = cfg.get("name", name)
        dlg = tk.Toplevel(self.master)
        dlg.title(tr("tool.router.edit_dialog_title", name=display_name))
        dlg.geometry("560x180" if is_tts else "560x300")
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text=tr("tool.router.label_api_key"), anchor="e", width=12).grid(
            row=0, column=0, padx=10, pady=16, sticky="e")
        key_var = tk.StringVar()
        key_entry = tk.Entry(dlg, textvariable=key_var, width=38, show="*")
        key_entry.grid(row=0, column=1, columnspan=2, pady=16, sticky="w")

        key_path = os.path.join(_keys_dir(), cfg.get("key_file", ""))
        if key_path and os.path.exists(key_path):
            with open(key_path, "r", encoding="utf-8") as f:
                key_var.set(f.read().strip())

        show_var = tk.BooleanVar(value=False)
        def toggle_show():
            key_entry.config(show="" if show_var.get() else "*")
        ttk.Checkbutton(dlg, text=tr("tool.router.label_show"), variable=show_var,
                        command=toggle_show).grid(row=0, column=3, padx=6)

        connect_timeout_var = tk.StringVar(value=str(cfg.get("connect_timeout_sec", 60)))
        read_timeout_var    = tk.StringVar(value=str(cfg.get("read_timeout_sec", 120)))
        max_retries_var     = tk.StringVar(value=str(cfg.get("max_retries", 1)))

        if not is_tts:
            tk.Label(dlg, text=tr("tool.router.label_connect_timeout_sec"), anchor="e", width=12).grid(
                row=1, column=0, padx=10, pady=6, sticky="e")
            tk.Entry(dlg, textvariable=connect_timeout_var, width=14).grid(row=1, column=1, pady=6, sticky="w")

            tk.Label(dlg, text=tr("tool.router.label_read_timeout_sec"), anchor="e", width=12).grid(
                row=2, column=0, padx=10, pady=6, sticky="e")
            tk.Entry(dlg, textvariable=read_timeout_var, width=14).grid(row=2, column=1, pady=6, sticky="w")

            tk.Label(dlg, text=tr("tool.router.label_max_retries"), anchor="e", width=12).grid(
                row=3, column=0, padx=10, pady=6, sticky="e")
            tk.Entry(dlg, textvariable=max_retries_var, width=14).grid(row=3, column=1, pady=6, sticky="w")

            tk.Label(
                dlg, text=tr("tool.router.asr_retry_hint"),
                font=("", 8), fg="gray", justify="left", wraplength=430,
            ).grid(row=4, column=0, columnspan=4, padx=12, pady=(8, 4), sticky="w")

        def save():
            key = key_var.get().strip()
            if not key:
                messagebox.showerror(tr("dialog.common.error"),
                                     tr("tool.router.error_key_empty"), parent=dlg)
                return

            if not is_tts:
                try:
                    connect_timeout = _parse_int_range(
                        connect_timeout_var.get(), minimum=5, maximum=300,
                        field_label=tr("tool.router.label_connect_timeout_sec"),
                    )
                    read_timeout = _parse_int_range(
                        read_timeout_var.get(), minimum=30, maximum=600,
                        field_label=tr("tool.router.label_read_timeout_sec"),
                    )
                    max_retries = _parse_int_range(
                        max_retries_var.get(), minimum=1, maximum=10,
                        field_label=tr("tool.router.label_max_retries"),
                    )
                except ValueError as e:
                    messagebox.showerror(tr("dialog.common.error"), str(e), parent=dlg)
                    return

            kp = os.path.join(_keys_dir(), cfg.get("key_file", ""))
            if kp:
                os.makedirs(os.path.dirname(kp), exist_ok=True)
                with open(kp, "w", encoding="utf-8") as f:
                    f.write(key)

            if not is_tts:
                router.update_asr_provider(
                    name,
                    connect_timeout_sec=connect_timeout,
                    read_timeout_sec=read_timeout,
                    max_retries=max_retries,
                )
            # TTS: key file is the only persistent state; router reads it
            # lazily on each get_tts_key() call.

            messagebox.showinfo(tr("tool.router.saved_title"),
                                tr("tool.router.saved_config_msg", name=display_name), parent=dlg)
            self._rebuild_keys_tab()
            dlg.destroy()

        btn_row = tk.Frame(dlg)
        btn_row.grid(row=5, column=0, columnspan=4, pady=14)
        tk.Button(btn_row, text=tr("tool.router.btn_save"), command=save, width=10).pack(side="left", padx=10)
        tk.Button(btn_row, text=tr("tool.router.btn_cancel"), command=dlg.destroy, width=10).pack(side="left")

    def _key_status(self, cfg):
        """Return (display_text, color)."""
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

    def _open_edit_dialog(self, name, cfg):
        is_claude = cfg.get("type") == "claude_code"
        dlg = tk.Toplevel(self.master)
        dlg.title(tr("tool.router.edit_dialog_title", name=name))
        dlg.geometry("500x340")
        dlg.resizable(False, False)
        dlg.grab_set()

        if is_claude:
            self._build_claude_code_dialog(dlg, name, cfg)
        else:
            self._build_api_key_dialog(dlg, name, cfg)

    def _build_api_key_dialog(self, dlg, name, cfg):
        r = 0

        tk.Label(dlg, text=tr("tool.router.label_api_key"), anchor="e", width=12).grid(
            row=r, column=0, padx=10, pady=10, sticky="e")
        key_var = tk.StringVar()
        key_entry = tk.Entry(dlg, textvariable=key_var, width=38, show="*")
        key_entry.grid(row=r, column=1, columnspan=2, pady=10, sticky="w")

        key_path = os.path.join(_keys_dir(), cfg.get("key_file", ""))
        if key_path and os.path.exists(key_path):
            with open(key_path, "r", encoding="utf-8") as f:
                key_var.set(f.read().strip())

        show_var = tk.BooleanVar(value=False)
        def toggle_show():
            key_entry.config(show="" if show_var.get() else "*")
        ttk.Checkbutton(dlg, text=tr("tool.router.label_show"), variable=show_var,
                        command=toggle_show).grid(row=r, column=3, padx=6)
        r += 1

        url_var = None
        if cfg.get("type") == "openai_compatible":
            tk.Label(dlg, text="Base URL:", anchor="e", width=12).grid(
                row=r, column=0, padx=10, pady=8, sticky="e")
            url_var = tk.StringVar(value=cfg.get("base_url", ""))
            tk.Entry(dlg, textvariable=url_var, width=48).grid(
                row=r, column=1, columnspan=3, pady=8, sticky="w")
            r += 1

        models_text = None
        if "models" in cfg:
            tk.Label(dlg, text=tr("tool.router.label_models"), anchor="ne", width=12).grid(
                row=r, column=0, padx=10, pady=8, sticky="ne")
            models_text = tk.Text(dlg, height=4, width=42, wrap="word")
            models_text.grid(row=r, column=1, columnspan=3, pady=8, sticky="w")
            models_text.insert("1.0", ", ".join(cfg.get("models", [])))
            r += 1

        def save():
            key = key_var.get().strip()
            if not key:
                messagebox.showerror(tr("dialog.common.error"),
                                     tr("tool.router.error_key_empty"), parent=dlg)
                return

            kp = os.path.join(_keys_dir(), cfg.get("key_file", ""))
            if kp:
                os.makedirs(os.path.dirname(kp), exist_ok=True)
                with open(kp, "w", encoding="utf-8") as f:
                    f.write(key)

            kwargs = {}
            if url_var is not None:
                kwargs["base_url"] = url_var.get().strip()
            if models_text is not None:
                raw = models_text.get("1.0", "end").strip()
                kwargs["models"] = [m.strip() for m in raw.split(",") if m.strip()]
            if kwargs:
                router.update_provider(name, **kwargs)

            messagebox.showinfo(tr("tool.router.saved_title"),
                                tr("tool.router.saved_config_msg", name=name), parent=dlg)
            self._rebuild_keys_tab()
            dlg.destroy()

        btn_row = tk.Frame(dlg)
        btn_row.grid(row=r, column=0, columnspan=4, pady=14)
        tk.Button(btn_row, text=tr("tool.router.btn_save"), command=save, width=10).pack(side="left", padx=10)
        tk.Button(btn_row, text=tr("tool.router.btn_cancel"), command=dlg.destroy, width=10).pack(side="left")

    def _build_claude_code_dialog(self, dlg, name, cfg):
        """Edit dialog variant for claude_code providers: no API key row,
        no Base URL. Exposes executable path, timeout, and model list."""
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

            raw_models = models_text.get("1.0", "end")
            models = [m.strip() for m in raw_models.replace("\n", ",").split(",") if m.strip()]

            router.update_provider(
                name,
                executable=executable,
                timeout_sec=timeout_sec,
                models=models,
            )
            messagebox.showinfo(tr("tool.router.saved_title"),
                                tr("tool.router.saved_config_msg", name=name), parent=dlg)
            self._rebuild_keys_tab()
            dlg.destroy()

        btn_row = tk.Frame(dlg)
        btn_row.grid(row=r, column=0, columnspan=4, pady=14)
        tk.Button(btn_row, text=tr("tool.router.btn_save"), command=save, width=10).pack(side="left", padx=10)
        tk.Button(btn_row, text=tr("tool.router.btn_cancel"), command=dlg.destroy, width=10).pack(side="left")

    def _rebuild_keys_tab(self):
        for w in self.tab_keys.winfo_children():
            w.destroy()
        self._build_keys_tab()

    # ── Tab 2: Routing Matrix (task × tier) ─────────────────────────────────

    def _build_matrix_tab(self):
        tab = self.tab_matrix

        tk.Label(tab, text=tr("tool.router.matrix_prompt"),
                 font=("", 9), fg="#555", wraplength=700, justify="left",
                 ).pack(anchor="w", pady=(0, 10))

        grid = tk.Frame(tab)
        grid.pack(fill="both", expand=True)

        # Header row: blank corner + one cell per tier
        tk.Label(grid, text="", width=22).grid(row=0, column=0, sticky="w")
        for col_idx, tier in enumerate(TIERS, start=1):
            hdr = tk.Frame(grid)
            hdr.grid(row=0, column=col_idx, padx=4, pady=(0, 4), sticky="w")
            tk.Label(hdr, text=_tier_display(tier),
                     font=("", 9, "bold")).pack(anchor="w")
            tk.Label(hdr, text=_tier_hint(tier),
                     font=("", 8), fg="gray").pack(anchor="w")

        current      = router.get_task_routing()
        llm_names    = router.get_provider_names()
        asr_names    = [p["name"] for p in router.get_available_asr_providers()]
        tts_names    = [p["name"] for p in router.get_available_tts_providers()]
        pool_by_cat  = {"llm": llm_names, "asr": asr_names, "tts": tts_names}

        self._matrix_widgets: dict = {}

        for row_idx, (task_id, category, label) in enumerate(_ai_cfg.TASKS, start=1):
            tk.Label(grid, text=label, anchor="w", font=("", 9),
                     ).grid(row=row_idx, column=0, sticky="w", padx=4, pady=6)

            pool = pool_by_cat.get(category, [])
            for col_idx, tier in enumerate(TIERS, start=1):
                cell_data = current.get(task_id, {}).get(tier, {})
                cell_frame = self._build_matrix_cell(
                    grid, task_id, tier, cell_data, pool, category,
                )
                cell_frame.grid(row=row_idx, column=col_idx, padx=4, pady=6, sticky="w")

        tk.Frame(tab, height=10).pack()

        save_btn = tk.Button(tab, text=tr("tool.router.btn_save_matrix"),
                             command=self._save_matrix,
                             bg="#4CAF50", fg="white", width=16, pady=4)
        save_btn.pack()

        self._matrix_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self._matrix_status_var,
                 fg="#228B22", font=("", 9)).pack(pady=4)

    def _build_matrix_cell(self, parent, task_id, tier, current, provider_pool, category):
        frame = tk.Frame(parent)

        prov_var  = tk.StringVar(value=current.get("provider", ""))
        model_var = tk.StringVar(value=current.get("model", ""))

        prov_combo = ttk.Combobox(frame, textvariable=prov_var, values=provider_pool,
                                   state="readonly", width=10)
        prov_combo.pack(side="left", padx=(0, 2))

        model_combo = ttk.Combobox(frame, textvariable=model_var, state="normal", width=16)
        model_combo.pack(side="left")

        if category == "llm":
            self._populate_model_combo(prov_var.get(), model_combo, model_var)

            def on_change(event, pv=prov_var, mc=model_combo, mv=model_var):
                self._populate_model_combo(pv.get(), mc, mv)
            prov_combo.bind("<<ComboboxSelected>>", on_change)
        else:
            # ASR/TTS providers have no per-task model list — model stays blank.
            model_combo.configure(state="disabled")

        self._matrix_widgets[(task_id, tier)] = {
            "provider_var": prov_var,
            "model_var":    model_var,
            "category":     category,
        }
        return frame

    def _populate_model_combo(self, provider_name, combo, model_var):
        models = router.get_provider_models(provider_name) if provider_name else []
        combo["values"] = models
        if models and model_var.get() not in models:
            model_var.set(models[0])

    def _save_matrix(self):
        count = 0
        for (task_id, tier), widgets in self._matrix_widgets.items():
            provider = widgets["provider_var"].get().strip()
            model    = widgets["model_var"].get().strip()
            router.set_task_routing_cell(task_id, tier, provider, model)
            count += 1
        self._matrix_status_var.set(tr("tool.router.matrix_saved", count=count))
        self.master.after(4000, lambda: self._matrix_status_var.set(""))

    # ── Tab 3: Call stats ───────────────────────────────────────────────────

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
