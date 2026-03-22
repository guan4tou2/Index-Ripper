import threading


def download_status_state(text: str) -> str:
    lower = (text or "").lower()
    if "fail" in lower:
        return "error"
    if "complete" in lower:
        return "success"
    if "cancel" in lower:
        return "warning"
    if "download" in lower:
        return "active"
    return "queued"


class DownloadsPanel:
    def __init__(self, parent_frame, ctk, tk, threading_module=None, tokens=None):
        self.parent_frame = parent_frame
        self.ctk = ctk
        self.tk = tk
        self.threading = threading_module or threading
        self._items = {}
        self.tokens = tokens or {}
        downloads_tokens = self.tokens.get("downloads", {})
        self.status_colors = downloads_tokens.get("status_colors", {})

    def _set_status_text(self, item, text: str) -> None:
        state = download_status_state(text)
        status_kwargs = {"text": text}
        color = self.status_colors.get(state)
        if color is not None:
            status_kwargs["text_color"] = color
        item["status"].configure(**status_kwargs)

    def ensure(self, file_path: str, display_name: str):
        try:
            item = self._items.get(file_path)
            if item:
                return item["cancel_event"]

            downloads_tokens = self.tokens.get("downloads", {})
            row = self.ctk.CTkFrame(
                self.parent_frame,
                fg_color=downloads_tokens.get("row_fg_color"),
                corner_radius=downloads_tokens.get("row_corner_radius", 8),
                border_width=downloads_tokens.get("row_border_width", 0),
            )
            row.pack(fill="x", padx=5, pady=4)

            name_label = self.ctk.CTkLabel(
                row,
                text=display_name,
                text_color=downloads_tokens.get("name_text_color"),
            )
            name_label.pack(side="left", padx=5)

            progress_bar_widget = self.ctk.CTkProgressBar(row)
            progress_bar_widget.set(0)
            progress_bar_widget.pack(side="left", expand=True, fill="x", padx=8)

            status = self.ctk.CTkLabel(row, text="Queued")
            status.pack(side="left", padx=5)

            cancel_event = self.threading.Event()

            def do_cancel():
                cancel_event.set()
                try:
                    self._set_status_text(self._items[file_path], "Canceling...")
                except self.tk.TclError:
                    pass

            cancel_btn_tokens = downloads_tokens.get("cancel_button", {})
            cancel_btn = self.ctk.CTkButton(
                row,
                text="Cancel",
                command=do_cancel,
                width=cancel_btn_tokens.get("width", 80),
                height=cancel_btn_tokens.get("height", 28),
                fg_color=cancel_btn_tokens.get("fg_color"),
                hover_color=cancel_btn_tokens.get("hover_color"),
            )
            cancel_btn.pack(side="right", padx=5)

            self._items[file_path] = {
                "frame": row,
                "bar": progress_bar_widget,
                "label": name_label,
                "status": status,
                "cancel_event": cancel_event,
            }
            self._set_status_text(self._items[file_path], "Queued")
            return cancel_event
        except self.tk.TclError:
            return self.threading.Event()

    def set_progress(self, file_path: str, progress: float) -> None:
        try:
            item = self._items.get(file_path)
            if not item:
                return
            item["bar"].set(progress / 100)
            self._set_status_text(item, f"Downloading {progress:.1f}%")
        except self.tk.TclError:
            pass

    def set_status(self, file_path: str, text: str) -> None:
        try:
            item = self._items.get(file_path)
            if not item:
                return
            self._set_status_text(item, text)
        except self.tk.TclError:
            pass
