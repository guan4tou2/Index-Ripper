from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from index_ripper.utils import normalize_extension


class FileTypeFilterMixin:
    """Mixin providing file-type filter checkbox management for the main app class."""

    def select_all_types(self) -> None:
        for var in self.file_types.values():
            var.set(True)

    def deselect_all_types(self) -> None:
        for var in self.file_types.values():
            var.set(False)

    def _bind_hscroll_wheel(self, widget) -> None:
        """讓 widget 的滾輪事件橫向捲動 filters_container（平滑版）。"""
        try:
            canvas = self.filters_container._parent_canvas
        except AttributeError:
            return

        # 每個 scroll unit = 20px，讓滾動距離合理
        canvas.configure(xscrollincrement=20)

        def _scroll(event):
            delta = getattr(event, "delta", 0)
            if not delta:
                return
            # macOS trackpad delta 很小 (1–5)；滑鼠滾輪約 120
            # 統一換算為 unit 數，最少 1
            units = max(1, abs(delta) // 3)
            canvas.xview_scroll(-units if delta > 0 else units, "units")

        widget.bind("<MouseWheel>", _scroll, add="+")
        widget.bind("<Shift-MouseWheel>", _scroll, add="+")

    def _add_file_type_filter(self, ext: str) -> None:
        if not hasattr(self, "filters_container"):
            return
        if ext in self.file_types:
            return
        var = tk.BooleanVar(value=True)
        self.file_types[ext] = var
        self.file_type_counts[ext] = 0
        cb = ctk.CTkCheckBox(
            self.filters_container,
            text=ext if ext else "(no ext)",
            variable=var,
            onvalue=True,
            offvalue=False,
        )
        cb.pack(side="left", padx=4, pady=4)
        self._bind_hscroll_wheel(cb)
        var.trace_add("write", lambda *_: self._on_type_filter_changed(ext))
        self.file_type_widgets[ext] = cb

    def _on_type_filter_changed(self, ext: str) -> None:
        """Show or hide existing tree rows when a file-type checkbox is toggled."""
        if self.full_tree_backup:
            return  # search filter active; handled by _filter_tree_by_term
        var = self.file_types.get(ext)
        if var is None:
            return
        visible = var.get()
        for node in self.tree_nodes.values():
            if node.kind == "file" and normalize_extension(node.name) == ext:
                node.hidden = not visible
        self._rebuild_visible()
        self._sync_rows()
