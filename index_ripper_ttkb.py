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
        tcl_library = os.path.join(lib_root, "tcl8.6")
        tk_library = os.path.join(lib_root, "tk8.6")
        if os.path.isfile(os.path.join(tcl_library, "init.tcl")) and os.path.isfile(
            os.path.join(tk_library, "tk.tcl")
        ):
            os.environ.setdefault("TCL_LIBRARY", tcl_library)
            os.environ.setdefault("TK_LIBRARY", tk_library)
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
