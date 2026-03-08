#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import os
import sys
import time


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pyside_poc.py",
        description="Minimal PySide6 POC UI (Tree / Logs / Downloads / Status).",
    )
    parser.add_argument(
        "--qt-platform",
        default=None,
        help=(
            "Optional QT_QPA_PLATFORM override (e.g. offscreen, minimal). "
            "Applied before importing PySide6."
        ),
    )
    parser.add_argument(
        "--quit-after",
        type=float,
        default=None,
        help="Auto-quit after N seconds (useful for manual measurements).",
    )
    parser.add_argument(
        "--print-pid",
        action="store_true",
        help="Print process PID on startup.",
    )
    parser.add_argument(
        "--measure-startup",
        action="store_true",
        help="Print rough startup timing checkpoints to stdout.",
    )
    return parser.parse_args(argv)


def _print_missing_pyside6_instructions() -> None:
    msg = """PySide6 is not installed.

Install:
  python3 -m pip install PySide6
  # or: python -m pip install PySide6

Run:
  python3 pyside_poc.py
  # or: python pyside_poc.py

Notes:
  - This is a discardable POC and exits with code 0 when PySide6 is missing.
  - For headless experiments you may try: python3 pyside_poc.py --qt-platform offscreen
"""
    sys.stdout.write(msg)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _parse_args(argv)

    if args.qt_platform:
        os.environ.setdefault("QT_QPA_PLATFORM", str(args.qt_platform))

    t0 = time.perf_counter()
    try:
        QtCore = importlib.import_module("PySide6.QtCore")
        QtWidgets = importlib.import_module("PySide6.QtWidgets")

        Qt = QtCore.Qt
        QTimer = QtCore.QTimer

        QApplication = QtWidgets.QApplication
        QFrame = QtWidgets.QFrame
        QGroupBox = QtWidgets.QGroupBox
        QHBoxLayout = QtWidgets.QHBoxLayout
        QLabel = QtWidgets.QLabel
        QListWidget = QtWidgets.QListWidget
        QMainWindow = QtWidgets.QMainWindow
        QPlainTextEdit = QtWidgets.QPlainTextEdit
        QProgressBar = QtWidgets.QProgressBar
        QSplitter = QtWidgets.QSplitter
        QTreeWidget = QtWidgets.QTreeWidget
        QTreeWidgetItem = QtWidgets.QTreeWidgetItem
        QVBoxLayout = QtWidgets.QVBoxLayout
        QWidget = QtWidgets.QWidget
    except Exception:
        _print_missing_pyside6_instructions()
        return 0

    t_import = time.perf_counter()

    app = QApplication(["pyside_poc"])
    app.setApplicationName("Index-Ripper PySide6 POC")

    if args.print_pid:
        sys.stdout.write(f"PID: {os.getpid()}\n")
        sys.stdout.flush()

    window = QMainWindow()
    window.setWindowTitle("Index-Ripper - PySide6 POC")
    window.resize(1080, 720)

    central = QWidget()
    root_layout = QVBoxLayout(central)
    root_layout.setContentsMargins(12, 12, 12, 12)
    root_layout.setSpacing(10)

    def boxed(title: str, child):
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(child)
        return box

    tree = QTreeWidget()
    tree.setHeaderHidden(True)
    root_item = QTreeWidgetItem(["index-ripper"])
    sources_item = QTreeWidgetItem(["sources"])
    sources_item.addChild(QTreeWidgetItem(["example.torrent"]))
    root_item.addChild(sources_item)
    root_item.addChild(QTreeWidgetItem(["outputs"]))
    tree.addTopLevelItem(root_item)
    tree.expandAll()
    tree_box = boxed("Tree", tree)

    logs = QPlainTextEdit()
    logs.setReadOnly(True)
    logs.setPlaceholderText("Logs will appear here.")
    logs.appendPlainText("[info] PySide6 POC started")
    logs.appendPlainText("[info] This UI is intentionally minimal")
    logs_box = boxed("Logs", logs)

    downloads = QListWidget()
    downloads.addItem("example_01.zip (queued)")
    downloads.addItem("example_02.zip (waiting)")
    downloads_box = boxed("Downloads", downloads)

    right_split = QSplitter()
    right_split.setOrientation(Qt.Orientation.Vertical)
    right_split.addWidget(logs_box)
    right_split.addWidget(downloads_box)
    right_split.setStretchFactor(0, 3)
    right_split.setStretchFactor(1, 2)

    main_split = QSplitter()
    main_split.addWidget(tree_box)
    main_split.addWidget(right_split)
    main_split.setStretchFactor(0, 2)
    main_split.setStretchFactor(1, 5)

    status_frame = QFrame()
    status_frame.setFrameShape(QFrame.StyledPanel)
    status_layout = QHBoxLayout(status_frame)
    status_layout.setContentsMargins(10, 8, 10, 8)
    status_layout.setSpacing(10)
    status_label = QLabel("Status: idle")
    status_progress = QProgressBar()
    status_progress.setRange(0, 100)
    status_progress.setValue(0)
    status_progress.setTextVisible(False)
    status_layout.addWidget(status_label, 1)
    status_layout.addWidget(status_progress, 2)
    status_box = boxed("Status", status_frame)

    root_layout.addWidget(main_split, 1)
    root_layout.addWidget(status_box, 0)
    window.setCentralWidget(central)

    t_ui = time.perf_counter()

    if args.quit_after is not None and args.quit_after >= 0:
        QTimer.singleShot(int(args.quit_after * 1000), app.quit)

    window.show()
    t_show = time.perf_counter()

    if args.measure_startup:
        sys.stdout.write(
            "startup_seconds "
            f"import={t_import - t0:.4f} "
            f"ui={t_ui - t_import:.4f} "
            f"show={t_show - t0:.4f}\n"
        )
        sys.stdout.flush()

    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
