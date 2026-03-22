from __future__ import annotations

from dataclasses import dataclass, field

import customtkinter as ctk


@dataclass
class TreeNode:
    node_id: str
    parent_id: str        # "" for root-level nodes
    name: str
    kind: str             # "folder" | "file"
    full_path: str        # "" for folders
    size: str
    file_type: str
    icon_group: str       # "folder"|"image"|"document"|"archive"|"code"|"audio"|"video"|"text"|"binary"
    checked: bool = False
    expanded: bool = False
    hidden: bool = False  # True when filtered out by search
    children: list[str] = field(default_factory=list)  # ordered list of child node_ids


_EMOJI_ICONS = {
    "folder":   "📁",
    "image":    "🖼️",
    "document": "📄",
    "archive":  "🗜️",
    "code":     "💻",
    "audio":    "🎵",
    "video":    "🎬",
    "text":     "📝",
    "binary":   "⚙️",
}

_BG_NORMAL        = "transparent"
_BG_HOVER         = ("#F1F5F9", "#1E293B")
_BG_CHECKED       = ("#EFF6FF", "#172554")
_BG_CHECKED_HOVER = ("#DBEAFE", "#1E3A5F")


class RowWidget:
    """One visible row in the FileTree."""

    INDENT_PX = 20
    ROW_HEIGHT = 36

    def __init__(self, parent, app, node: TreeNode, depth: int):
        self.app = app
        self.node_id = node.node_id
        self._checked = node.checked
        self._hovered = False

        self.frame = ctk.CTkFrame(parent, height=self.ROW_HEIGHT, corner_radius=4)
        self.frame.pack(fill="x", padx=4, pady=0)
        self.frame.pack_propagate(False)

        # 3-px accent bar (left edge, blue when checked)
        self._accent = ctk.CTkFrame(
            self.frame, width=3, corner_radius=0,
            fg_color="#2563EB" if node.checked else "transparent",
        )
        self._accent.pack(side="left", fill="y")

        # Indent spacer
        if depth > 0:
            ctk.CTkFrame(
                self.frame, width=depth * self.INDENT_PX,
                fg_color="transparent", height=self.ROW_HEIGHT,
            ).pack(side="left")

        # Emoji icon
        ctk.CTkLabel(
            self.frame,
            text=_EMOJI_ICONS.get(node.icon_group, "📄"),
            font=ctk.CTkFont(size=18),
            width=28,
        ).pack(side="left", padx=(4, 4))

        # Name label
        self.name_label = ctk.CTkLabel(
            self.frame,
            text=node.name,
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold" if node.kind == "folder" else "normal"),
        )
        self.name_label.pack(side="left", fill="x", expand=True)

        # Chevron on RIGHT (folders only)
        if node.kind == "folder":
            self.chevron = ctk.CTkButton(
                self.frame, text="▼" if node.expanded else "▶",
                width=22, height=22, fg_color="transparent",
                hover_color=("gray85", "gray30"), text_color=("gray40", "gray60"),
                font=ctk.CTkFont(size=10),
                command=lambda: app._on_chevron_click(self.node_id),
            )
            self.chevron.pack(side="right", padx=(4, 4))
        elif node.kind == "file" and node.size:
            # Size label (right side, files only)
            ctk.CTkLabel(
                self.frame,
                text=node.size,
                font=ctk.CTkFont(size=12),
                text_color=("gray50", "gray60"),
                width=80,
                anchor="e",
            ).pack(side="right", padx=(0, 8))

        # Bind hover only on outer frame (avoids <Leave> flicker from child entry)
        self.frame.bind("<Enter>", self._on_enter)
        self.frame.bind("<Leave>", self._on_leave)
        # Bind click on frame and all non-chevron children
        self._bind_clicks(self.frame)

    def _bind_clicks(self, widget) -> None:
        """Bind click handler on widget and all children except the chevron."""
        if hasattr(self, "chevron") and widget is self.chevron:
            return  # chevron has its own command; don't intercept clicks
        widget.bind("<Button-1>", self._on_click)
        for child in widget.winfo_children():
            self._bind_clicks(child)

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._update_bg()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._update_bg()

    def _on_click(self, event) -> None:
        self.app._on_row_click(self.node_id, event)

    def set_checked(self, checked: bool) -> None:
        self._checked = checked
        self._accent.configure(
            fg_color="#2563EB" if checked else "transparent"
        )
        self._update_bg()

    def set_chevron(self, expanded: bool) -> None:
        if hasattr(self, "chevron"):
            self.chevron.configure(text="▼" if expanded else "▶")

    def _update_bg(self) -> None:
        if self._checked and self._hovered:
            color = _BG_CHECKED_HOVER
        elif self._checked:
            color = _BG_CHECKED
        elif self._hovered:
            color = _BG_HOVER
        else:
            color = _BG_NORMAL
        self.frame.configure(fg_color=color)

    def destroy(self) -> None:
        self.frame.destroy()


def should_skip_file_row(existing_entry) -> bool:
    """Return True when a file row is already fully registered."""
    return existing_entry is not None
