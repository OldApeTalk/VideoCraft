"""
router_manager.py - AI Router 管理界面

提供三个标签页：
  1. Provider & Key  — 查看/编辑各 Provider 的 API Key，启用/禁用
  2. 档位配置        — 为高/中/低三档指定具体的 Provider + Model
  3. 调用统计        — 查看各 Provider 的调用次数、错误情况

使用方式：
    from router_manager import open_router_manager
    open_router_manager(parent_window)
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox

from ai_router import router, TIERS, TIER_PREMIUM, TIER_STANDARD, TIER_ECONOMY, _keys_dir
from i18n import tr

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


def open_router_manager(parent):
    """在 parent 窗口上弹出 Router 管理窗口。"""
    RouterManagerWindow(parent)


def _parse_int_range(value: str, *, minimum: int, maximum: int, field_label: str) -> int:
    try:
        parsed = int(value.strip())
    except Exception as e:
        raise ValueError(tr("tool.router.error_invalid_number", field=field_label)) from e
    if parsed < minimum or parsed > maximum:
        raise ValueError(tr("tool.router.error_out_of_range",
                            field=field_label, min=minimum, max=maximum))
    return parsed


# ── 主窗口 ────────────────────────────────────────────────────────────────────

class RouterManagerWindow:
    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title(tr("tool.router.title"))
        self.win.geometry("660x540")
        self.win.resizable(True, True)
        self.win.grab_set()     # 模态行为

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        self.tab_keys  = tk.Frame(nb, padx=12, pady=10)
        self.tab_tiers = tk.Frame(nb, padx=12, pady=10)
        self.tab_stats = tk.Frame(nb, padx=12, pady=10)

        nb.add(self.tab_keys,  text=tr("tool.router.tab_keys"))
        nb.add(self.tab_tiers, text=tr("tool.router.tab_tiers"))
        nb.add(self.tab_stats, text=tr("tool.router.tab_stats"))

        nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

        self._build_keys_tab()
        self._build_tiers_tab()
        self._build_stats_tab()

        tk.Button(self.win, text=tr("tool.router.btn_close"), command=self.win.destroy,
                  width=10).pack(side="right", padx=15, pady=(0, 10))

    def _on_tab_change(self, event):
        nb = event.widget
        if nb.index(nb.select()) == 2:      # 统计 tab
            self._refresh_stats()

    # ── Tab 1: Provider & Key ─────────────────────────────────────────────────

    def _build_keys_tab(self):
        tab = self.tab_keys

        # Column headers
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

        # ASR Providers section
        tk.Label(tab, text=tr("tool.router.asr_providers_header"), font=("", 9, "bold"), fg="#444").pack(anchor="w", pady=(0, 4))
        for name, cfg in router._asr_providers.items():
            self._build_asr_provider_row(tab, name, cfg)

        ttk.Separator(tab, orient="horizontal").pack(fill="x", pady=(8, 4))

        # TTS Providers section
        tk.Label(tab, text=tr("tool.router.tts_providers_header"), font=("", 9, "bold"), fg="#444").pack(anchor="w", pady=(0, 4))
        for name, cfg in router._tts_providers.items():
            self._build_asr_provider_row(tab, name, cfg)   # Same row structure as ASR, reused

        ttk.Separator(tab, orient="horizontal").pack(fill="x", pady=(4, 8))
        tk.Label(tab,
                 text=tr("tool.router.key_hint"),
                 font=("", 8), fg="gray",
                 wraplength=580, justify="left").pack(anchor="w")

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

        # No enabled/disabled checkbox for ASR (not yet supported)
        tk.Label(row, width=9).pack(side="left")   # Placeholder to align columns
        tk.Button(row, text=tr("tool.router.btn_edit"), width=6,
                  command=lambda n=name, c=cfg: self._open_asr_edit_dialog(n, c)
                  ).pack(side="left", padx=8)

    def _open_asr_edit_dialog(self, name, cfg):
        display_name = cfg.get("name", name)
        dlg = tk.Toplevel(self.win)
        dlg.title(tr("tool.router.edit_dialog_title", name=display_name))
        dlg.geometry("560x300")
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

        tk.Label(dlg, text=tr("tool.router.label_connect_timeout_sec"), anchor="e", width=12).grid(
            row=1, column=0, padx=10, pady=6, sticky="e")
        connect_timeout_var = tk.StringVar(value=str(cfg.get("connect_timeout_sec", 60)))
        tk.Entry(dlg, textvariable=connect_timeout_var, width=14).grid(row=1, column=1, pady=6, sticky="w")

        tk.Label(dlg, text=tr("tool.router.label_read_timeout_sec"), anchor="e", width=12).grid(
            row=2, column=0, padx=10, pady=6, sticky="e")
        read_timeout_var = tk.StringVar(value=str(cfg.get("read_timeout_sec", 120)))
        tk.Entry(dlg, textvariable=read_timeout_var, width=14).grid(row=2, column=1, pady=6, sticky="w")

        tk.Label(dlg, text=tr("tool.router.label_max_retries"), anchor="e", width=12).grid(
            row=3, column=0, padx=10, pady=6, sticky="e")
        max_retries_var = tk.StringVar(value=str(cfg.get("max_retries", 1)))
        tk.Entry(dlg, textvariable=max_retries_var, width=14).grid(row=3, column=1, pady=6, sticky="w")

        tk.Label(
            dlg,
            text=tr("tool.router.asr_retry_hint"),
            font=("", 8),
            fg="gray",
            justify="left",
            wraplength=430,
        ).grid(row=4, column=0, columnspan=4, padx=12, pady=(8, 4), sticky="w")

        def save():
            key = key_var.get().strip()
            if not key:
                messagebox.showerror(tr("dialog.common.error"),
                                     tr("tool.router.error_key_empty"), parent=dlg)
                return

            try:
                connect_timeout = _parse_int_range(
                    connect_timeout_var.get(),
                    minimum=5,
                    maximum=300,
                    field_label=tr("tool.router.label_connect_timeout_sec"),
                )
                read_timeout = _parse_int_range(
                    read_timeout_var.get(),
                    minimum=30,
                    maximum=600,
                    field_label=tr("tool.router.label_read_timeout_sec"),
                )
                max_retries = _parse_int_range(
                    max_retries_var.get(),
                    minimum=1,
                    maximum=10,
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
            router.update_asr_provider(
                name,
                connect_timeout_sec=connect_timeout,
                read_timeout_sec=read_timeout,
                max_retries=max_retries,
            )
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
        dlg = tk.Toplevel(self.win)
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

        # API Key
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

        # Base URL (openai_compatible only)
        url_var = None
        if cfg.get("type") == "openai_compatible":
            tk.Label(dlg, text=tr("tool.router.label_base_url"), anchor="e", width=12).grid(
                row=r, column=0, padx=10, pady=8, sticky="e")
            url_var = tk.StringVar(value=cfg.get("base_url", ""))
            tk.Entry(dlg, textvariable=url_var, width=44).grid(
                row=r, column=1, columnspan=3, pady=8, sticky="w")
            r += 1

        # Model list (openai_compatible only)
        models_text = None
        if cfg.get("type") == "openai_compatible":
            tk.Label(dlg, text=tr("tool.router.label_models"), anchor="ne", width=12).grid(
                row=r, column=0, padx=10, pady=8, sticky="ne")
            models_text = tk.Text(dlg, height=4, width=44, wrap="word")
            models_text.grid(row=r, column=1, columnspan=3, pady=8, sticky="w")
            models_text.insert("1.0", ", ".join(cfg.get("models", [])))
            r += 1

        def save():
            key = key_var.get().strip()
            if not key:
                messagebox.showerror(tr("dialog.common.error"),
                                     tr("tool.router.error_key_empty"), parent=dlg)
                return

            # Write .key file
            kp = os.path.join(_keys_dir(), cfg.get("key_file", ""))
            if kp:
                os.makedirs(os.path.dirname(kp), exist_ok=True)
                with open(kp, "w", encoding="utf-8") as f:
                    f.write(key)

            # Update router config (base_url / models)
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
            self._rebuild_keys_tab()    # Refresh status display
            dlg.destroy()

        btn_row = tk.Frame(dlg)
        btn_row.grid(row=r, column=0, columnspan=4, pady=14)
        tk.Button(btn_row, text=tr("tool.router.btn_save"), command=save, width=10).pack(side="left", padx=10)
        tk.Button(btn_row, text=tr("tool.router.btn_cancel"), command=dlg.destroy, width=10).pack(side="left")

    def _build_claude_code_dialog(self, dlg, name, cfg):
        """Edit dialog variant for claude_code providers: no API key row, no
        Base URL. Exposes executable path, timeout, and model list."""
        r = 0

        # Executable path
        tk.Label(dlg, text=tr("tool.router.label_executable"), anchor="e", width=14).grid(
            row=r, column=0, padx=10, pady=(14, 6), sticky="e")
        exec_var = tk.StringVar(value=cfg.get("executable", "claude"))
        tk.Entry(dlg, textvariable=exec_var, width=42).grid(
            row=r, column=1, columnspan=3, pady=(14, 6), sticky="w")
        r += 1

        # Timeout (seconds)
        tk.Label(dlg, text=tr("tool.router.label_timeout_sec"), anchor="e", width=14).grid(
            row=r, column=0, padx=10, pady=6, sticky="e")
        timeout_var = tk.StringVar(value=str(cfg.get("timeout_sec", 600)))
        tk.Entry(dlg, textvariable=timeout_var, width=14).grid(
            row=r, column=1, pady=6, sticky="w")
        r += 1

        # Model list (comma-separated)
        tk.Label(dlg, text=tr("tool.router.label_models"), anchor="ne", width=14).grid(
            row=r, column=0, padx=10, pady=6, sticky="ne")
        models_text = tk.Text(dlg, height=4, width=42, wrap="word")
        models_text.grid(row=r, column=1, columnspan=3, pady=6, sticky="w")
        models_text.insert("1.0", ", ".join(cfg.get("models", [])))
        r += 1

        # Hint
        tk.Label(
            dlg,
            text=tr("tool.router.claudecode_hint"),
            font=("", 8), fg="gray", justify="left", wraplength=440,
        ).grid(row=r, column=0, columnspan=4, padx=12, pady=(8, 4), sticky="w")
        r += 1

        def save():
            executable = exec_var.get().strip() or "claude"
            try:
                timeout_sec = _parse_int_range(
                    timeout_var.get(),
                    minimum=10,
                    maximum=3600,
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

    # ── Tab 2: 档位配置 ───────────────────────────────────────────────────────

    def _build_tiers_tab(self):
        tab = self.tab_tiers

        tk.Label(tab, text=tr("tool.router.tier_prompt"),
                 font=("", 9), fg="#555").pack(anchor="w", pady=(0, 8))

        current   = router.get_tier_routing()
        providers = router.get_provider_names()
        self._tier_widgets: dict = {}

        for tier in TIERS:
            self._build_tier_row(tab, tier, current.get(tier, {}), providers)

        tk.Frame(tab, height=8).pack()

        save_btn = tk.Button(tab, text=tr("tool.router.btn_save_tiers"), command=self._save_tiers,
                             bg="#4CAF50", fg="white", width=16, pady=4)
        save_btn.pack()

        self._tier_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self._tier_status_var,
                 fg="#228B22", font=("", 9)).pack(pady=4)

    def _build_tier_row(self, parent, tier, current, provider_names):
        frame = tk.LabelFrame(parent, text=_tier_display(tier), padx=10, pady=6)
        frame.pack(fill="x", pady=4)

        tk.Label(frame, text=_tier_hint(tier),
                 font=("", 8), fg="gray").pack(anchor="w")

        ctrl = tk.Frame(frame)
        ctrl.pack(fill="x", pady=(4, 0))

        tk.Label(ctrl, text=tr("tool.router.label_provider_combo"), width=9, anchor="w").pack(side="left")

        prov_var = tk.StringVar(value=current.get("provider",
                                provider_names[0] if provider_names else ""))
        prov_combo = ttk.Combobox(ctrl, textvariable=prov_var,
                                  values=provider_names, state="readonly", width=14)
        prov_combo.pack(side="left", padx=(0, 12))

        tk.Label(ctrl, text=tr("tool.router.label_model_combo"), width=7, anchor="w").pack(side="left")

        model_var = tk.StringVar(value=current.get("model", ""))
        model_combo = ttk.Combobox(ctrl, textvariable=model_var,
                                   state="normal", width=30)
        model_combo.pack(side="left")

        # 初始化模型列表
        self._populate_model_combo(prov_var.get(), model_combo, model_var)

        def on_provider_change(event, pv=prov_var, mc=model_combo, mv=model_var):
            self._populate_model_combo(pv.get(), mc, mv)

        prov_combo.bind("<<ComboboxSelected>>", on_provider_change)

        self._tier_widgets[tier] = {
            "provider_var": prov_var,
            "model_var":    model_var,
        }

    def _populate_model_combo(self, provider_name, combo, model_var):
        models = router.get_provider_models(provider_name)
        combo["values"] = models
        if models and model_var.get() not in models:
            model_var.set(models[0])

    def _save_tiers(self):
        saved = []
        for tier, widgets in self._tier_widgets.items():
            provider = widgets["provider_var"].get().strip()
            model    = widgets["model_var"].get().strip()
            if provider and model:
                router.set_tier_routing(tier, provider, model)
                saved.append(_tier_display(tier))

        if saved:
            self._tier_status_var.set(tr("tool.router.tiers_saved", items=", ".join(saved)))
        else:
            self._tier_status_var.set(tr("tool.router.tiers_none_valid"))
        self.win.after(4000, lambda: self._tier_status_var.set(""))

    # ── Tab 3: 调用统计 ───────────────────────────────────────────────────────

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
        tk.Button(btn_col, text=tr("tool.router.btn_refresh"), command=self._refresh_stats,
                  width=8).pack(pady=4)

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


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()          # 隐藏空白根窗口
    open_router_manager(root)
    root.mainloop()
