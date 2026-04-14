"""
tools/preferences/preferences.py - Preferences panel as a Hub tab.

Follows the standard Hub tool convention: subclass ToolBase, take a master
(ToolFrame) in __init__, lay out its UI with grid. Currently only exposes
language selection; will grow to include theme, default output directory,
etc. Changes that require a restart show an inline hint next to the action.
"""

import tkinter as tk
from tkinter import ttk

import i18n
from i18n import tr
from tools.base import ToolBase


class PreferencesApp(ToolBase):
    """Preferences tab — language picker (phase 1), more sections to follow."""

    def __init__(self, master, initial_file=None):
        self.master = master
        master.title(tr("tool.preferences.title"))
        master.geometry("640x360")

        # Root padding frame
        root = tk.Frame(master, padx=24, pady=24)
        root.pack(fill="both", expand=True)

        # ── Section: Language ────────────────────────────────────────────────
        section = tk.LabelFrame(
            root, text=tr("tool.preferences.section_language"),
            padx=16, pady=12,
        )
        section.pack(fill="x")

        tk.Label(section, text=tr("tool.preferences.language_label")).grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=6,
        )

        self._lang_labels = {
            "zh": tr("tool.preferences.language_zh"),
            "en": tr("tool.preferences.language_en"),
        }
        self._current_lang = i18n.get_current_lang()

        self._lang_var = tk.StringVar(
            value=self._lang_labels.get(self._current_lang, self._lang_labels["zh"])
        )
        combo = ttk.Combobox(
            section, textvariable=self._lang_var, state="readonly", width=16,
            values=[self._lang_labels["zh"], self._lang_labels["en"]],
        )
        combo.grid(row=0, column=1, sticky="w", pady=6)

        self._save_btn = tk.Button(
            section, text=tr("tool.preferences.save"),
            command=self._on_save, width=14,
            bg="#0078d4", fg="white", relief="flat",
            activebackground="#1a8ae5", cursor="hand2",
        )
        self._save_btn.grid(row=0, column=2, padx=(12, 0), pady=6)

        # Inline status label under the row (reserved space, initially empty)
        self._status_lbl = tk.Label(section, text="", fg="#2e8b57", anchor="w")
        self._status_lbl.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # Coverage disclaimer under the section
        tk.Label(
            root, text=tr("tool.preferences.coverage_note"),
            fg="#777", wraplength=560, justify="left",
        ).pack(fill="x", pady=(14, 0))

        # Future: more sections (theme, default output dir, shortcuts...) go here

    def _on_save(self):
        selected_label = self._lang_var.get()
        code = next(
            (k for k, v in self._lang_labels.items() if v == selected_label),
            i18n.DEFAULT_LANG,
        )
        try:
            i18n.set_current_lang(code)
        except Exception as e:
            self.set_error(f"保存首选项失败: {e}")
            self._status_lbl.config(text=f"✗ {e}", fg="#c0392b")
            return

        if code == self._current_lang:
            self._status_lbl.config(
                text=tr("tool.preferences.saved_no_change"), fg="#2e8b57",
            )
        else:
            self._status_lbl.config(
                text=tr("tool.preferences.saved_restart"), fg="#c06000",
            )
        self.set_done()
