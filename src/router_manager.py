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

# ── 显示文本常量 ──────────────────────────────────────────────────────────────

TIER_DISPLAY = {
    TIER_PREMIUM:  "高档 (Premium)",
    TIER_STANDARD: "中档 (Standard)",
    TIER_ECONOMY:  "低档 (Economy)",
}
TIER_HINT = {
    TIER_PREMIUM:  "最强模型，适合高精度推理、长文翻译等复杂任务",
    TIER_STANDARD: "平衡速度与质量，适合常规翻译、字幕处理",
    TIER_ECONOMY:  "快速轻量，适合高频批量或简单任务",
}


def open_router_manager(parent):
    """在 parent 窗口上弹出 Router 管理窗口。"""
    RouterManagerWindow(parent)


# ── 主窗口 ────────────────────────────────────────────────────────────────────

class RouterManagerWindow:
    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title("AI Router 管理")
        self.win.geometry("660x540")
        self.win.resizable(True, True)
        self.win.grab_set()     # 模态行为

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        self.tab_keys  = tk.Frame(nb, padx=12, pady=10)
        self.tab_tiers = tk.Frame(nb, padx=12, pady=10)
        self.tab_stats = tk.Frame(nb, padx=12, pady=10)

        nb.add(self.tab_keys,  text="  Provider & Key  ")
        nb.add(self.tab_tiers, text="  档位配置  ")
        nb.add(self.tab_stats, text="  调用统计  ")

        nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

        self._build_keys_tab()
        self._build_tiers_tab()
        self._build_stats_tab()

        tk.Button(self.win, text="关闭", command=self.win.destroy,
                  width=10).pack(side="right", padx=15, pady=(0, 10))

    def _on_tab_change(self, event):
        nb = event.widget
        if nb.index(nb.select()) == 2:      # 统计 tab
            self._refresh_stats()

    # ── Tab 1: Provider & Key ─────────────────────────────────────────────────

    def _build_keys_tab(self):
        tab = self.tab_keys

        # 列标题
        hdr = tk.Frame(tab)
        hdr.pack(fill="x", pady=(0, 2))
        tk.Label(hdr, text="Provider",  width=10, anchor="w", font=("", 9, "bold")).pack(side="left")
        tk.Label(hdr, text="Key 状态",  width=24, anchor="w", font=("", 9, "bold")).pack(side="left")
        tk.Label(hdr, text="启用",      width=5,  anchor="w", font=("", 9, "bold")).pack(side="left")
        ttk.Separator(tab, orient="horizontal").pack(fill="x", pady=3)

        self._enabled_vars = {}
        for name, cfg in router._providers.items():
            self._build_provider_row(tab, name, cfg)

        ttk.Separator(tab, orient="horizontal").pack(fill="x", pady=8)
        tk.Label(tab,
                 text="Key 保存在本地 keys/ 目录，不会上传至网络。"
                      "点击「编辑」可查看或修改。",
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
        tk.Button(row, text="编辑", width=6,
                  command=lambda n=name, c=cfg: self._open_edit_dialog(n, c)
                  ).pack(side="left", padx=8)

    def _key_status(self, cfg):
        """返回 (显示文本, 颜色)。"""
        key_file = cfg.get("key_file", "")
        if not key_file:
            return "无需 Key", "#555555"
        key_path = os.path.join(_keys_dir(), key_file)
        if not os.path.exists(key_path):
            return "❌ 未配置", "#CC0000"
        with open(key_path, "r", encoding="utf-8") as f:
            key = f.read().strip()
        if not key:
            return "❌ Key 为空", "#CC0000"
        masked = key[:4] + "****" + key[-4:] if len(key) >= 8 else "****"
        return f"✅ {masked}", "#228B22"

    def _open_edit_dialog(self, name, cfg):
        dlg = tk.Toplevel(self.win)
        dlg.title(f"编辑 {name}")
        dlg.geometry("500x340")
        dlg.resizable(False, False)
        dlg.grab_set()

        r = 0

        # API Key
        tk.Label(dlg, text="API Key:", anchor="e", width=12).grid(
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
        ttk.Checkbutton(dlg, text="显示", variable=show_var,
                        command=toggle_show).grid(row=r, column=3, padx=6)
        r += 1

        # Base URL（仅 openai_compatible）
        url_var = None
        if cfg.get("type") == "openai_compatible":
            tk.Label(dlg, text="Base URL:", anchor="e", width=12).grid(
                row=r, column=0, padx=10, pady=8, sticky="e")
            url_var = tk.StringVar(value=cfg.get("base_url", ""))
            tk.Entry(dlg, textvariable=url_var, width=44).grid(
                row=r, column=1, columnspan=3, pady=8, sticky="w")
            r += 1

        # 模型列表（仅 openai_compatible）
        models_text = None
        if cfg.get("type") == "openai_compatible":
            tk.Label(dlg, text="模型列表\n(逗号分隔):", anchor="ne", width=12).grid(
                row=r, column=0, padx=10, pady=8, sticky="ne")
            models_text = tk.Text(dlg, height=4, width=44, wrap="word")
            models_text.grid(row=r, column=1, columnspan=3, pady=8, sticky="w")
            models_text.insert("1.0", ", ".join(cfg.get("models", [])))
            r += 1

        def save():
            key = key_var.get().strip()
            if not key:
                messagebox.showerror("错误", "API Key 不能为空", parent=dlg)
                return

            # 写入 .key 文件
            kp = os.path.join(_keys_dir(), cfg.get("key_file", ""))
            if kp:
                os.makedirs(os.path.dirname(kp), exist_ok=True)
                with open(kp, "w", encoding="utf-8") as f:
                    f.write(key)

            # 更新 router 配置（base_url / models）
            kwargs = {}
            if url_var is not None:
                kwargs["base_url"] = url_var.get().strip()
            if models_text is not None:
                raw = models_text.get("1.0", "end").strip()
                kwargs["models"] = [m.strip() for m in raw.split(",") if m.strip()]
            if kwargs:
                router.update_provider(name, **kwargs)

            messagebox.showinfo("已保存", f"{name} 配置已保存", parent=dlg)
            self._rebuild_keys_tab()    # 刷新状态显示
            dlg.destroy()

        btn_row = tk.Frame(dlg)
        btn_row.grid(row=r, column=0, columnspan=4, pady=14)
        tk.Button(btn_row, text="保存", command=save, width=10).pack(side="left", padx=10)
        tk.Button(btn_row, text="取消", command=dlg.destroy, width=10).pack(side="left")

    def _rebuild_keys_tab(self):
        for w in self.tab_keys.winfo_children():
            w.destroy()
        self._build_keys_tab()

    # ── Tab 2: 档位配置 ───────────────────────────────────────────────────────

    def _build_tiers_tab(self):
        tab = self.tab_tiers

        tk.Label(tab, text="为每个档位指定使用的 AI Provider 和模型：",
                 font=("", 9), fg="#555").pack(anchor="w", pady=(0, 8))

        current   = router.get_tier_routing()
        providers = router.get_provider_names()
        self._tier_widgets: dict = {}

        for tier in TIERS:
            self._build_tier_row(tab, tier, current.get(tier, {}), providers)

        tk.Frame(tab, height=8).pack()

        save_btn = tk.Button(tab, text="保存档位配置", command=self._save_tiers,
                             bg="#4CAF50", fg="white", width=16, pady=4)
        save_btn.pack()

        self._tier_status_var = tk.StringVar()
        tk.Label(tab, textvariable=self._tier_status_var,
                 fg="#228B22", font=("", 9)).pack(pady=4)

    def _build_tier_row(self, parent, tier, current, provider_names):
        frame = tk.LabelFrame(parent, text=TIER_DISPLAY[tier], padx=10, pady=6)
        frame.pack(fill="x", pady=4)

        tk.Label(frame, text=TIER_HINT[tier],
                 font=("", 8), fg="gray").pack(anchor="w")

        ctrl = tk.Frame(frame)
        ctrl.pack(fill="x", pady=(4, 0))

        tk.Label(ctrl, text="Provider:", width=9, anchor="w").pack(side="left")

        prov_var = tk.StringVar(value=current.get("provider",
                                provider_names[0] if provider_names else ""))
        prov_combo = ttk.Combobox(ctrl, textvariable=prov_var,
                                  values=provider_names, state="readonly", width=14)
        prov_combo.pack(side="left", padx=(0, 12))

        tk.Label(ctrl, text="Model:", width=7, anchor="w").pack(side="left")

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
                saved.append(TIER_DISPLAY[tier])

        if saved:
            self._tier_status_var.set(f"✅ 已保存：{', '.join(saved)}")
        else:
            self._tier_status_var.set("⚠️ 没有有效配置可保存")
        self.win.after(4000, lambda: self._tier_status_var.set(""))

    # ── Tab 3: 调用统计 ───────────────────────────────────────────────────────

    def _build_stats_tab(self):
        tab = self.tab_stats

        cols   = ("provider", "calls", "errors", "error_rate", "last_used")
        labels = ("Provider", "调用次数", "错误次数",  "错误率",  "最后使用时间")
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
        tk.Button(btn_col, text="刷新", command=self._refresh_stats,
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
            last   = s["last_used"] or "从未使用"
            self.stats_tree.insert("", "end", values=(name, calls, errors, rate, last))


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()          # 隐藏空白根窗口
    open_router_manager(root)
    root.mainloop()
