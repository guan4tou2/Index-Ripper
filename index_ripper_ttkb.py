from __future__ import annotations

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
