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


from app_utils import configure_tk_libraries
configure_tk_libraries()


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
