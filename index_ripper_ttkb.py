from __future__ import annotations

import os
import sys


if "--smoke" in sys.argv:
    print("SMOKE_OK")
    raise SystemExit(0)

if "--self-test" in sys.argv:
    from self_test import run_self_test

    result = run_self_test()
    print(
        f"SELF_TEST_OK total={result.total} files={result.files} dirs={result.directories}"
    )
    raise SystemExit(0)


def _configure_tk_libraries() -> None:
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    for prefix in (sys.base_prefix, sys.prefix):
        lib_root = os.path.join(prefix, "lib")
        if not os.path.isdir(lib_root):
            continue
        tcl_dir = tk_dir = None
        try:
            for entry in os.listdir(lib_root):
                if entry.startswith("tcl") and os.path.isfile(os.path.join(lib_root, entry, "init.tcl")):
                    tcl_dir = os.path.join(lib_root, entry)
                if entry.startswith("tk") and os.path.isfile(os.path.join(lib_root, entry, "tk.tcl")):
                    tk_dir = os.path.join(lib_root, entry)
        except OSError:
            continue
        if tcl_dir and tk_dir:
            os.environ.setdefault("TCL_LIBRARY", tcl_dir)
            os.environ.setdefault("TK_LIBRARY", tk_dir)
            return


_configure_tk_libraries()


def main() -> int:
    if "--ui-smoke" in sys.argv:
        from ui_ttkb import WebsiteCopierTtkb

        app = WebsiteCopierTtkb(ui_smoke=True)
        app.run()
        print("UI_SMOKE_OK")
        return 0

    from ui_ttkb import WebsiteCopierTtkb

    app = WebsiteCopierTtkb()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
