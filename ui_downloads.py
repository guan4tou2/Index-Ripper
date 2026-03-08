import threading


class DownloadsPanel:
    def __init__(self, parent_frame, ctk, tk, threading_module=None):
        self.parent_frame = parent_frame
        self.ctk = ctk
        self.tk = tk
        self.threading = threading_module or threading
        self._items = {}

    def ensure(self, file_path: str, display_name: str):
        try:
            item = self._items.get(file_path)
            if item:
                return item["cancel_event"]

            row = self.ctk.CTkFrame(self.parent_frame)
            row.pack(fill="x", padx=5, pady=4)

            name_label = self.ctk.CTkLabel(row, text=display_name)
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
                    status.configure(text="Canceling...")
                except self.tk.TclError:
                    pass

            cancel_btn = self.ctk.CTkButton(
                row, text="Cancel", width=80, command=do_cancel
            )
            cancel_btn.pack(side="right", padx=5)

            self._items[file_path] = {
                "frame": row,
                "bar": progress_bar_widget,
                "label": name_label,
                "status": status,
                "cancel_event": cancel_event,
            }
            return cancel_event
        except self.tk.TclError:
            return self.threading.Event()

    def set_progress(self, file_path: str, progress: float) -> None:
        try:
            item = self._items.get(file_path)
            if not item:
                return
            item["bar"].set(progress / 100)
            item["status"].configure(text=f"Downloading {progress:.1f}%")
        except self.tk.TclError:
            pass

    def set_status(self, file_path: str, text: str) -> None:
        try:
            item = self._items.get(file_path)
            if not item:
                return
            item["status"].configure(text=text)
        except self.tk.TclError:
            pass
