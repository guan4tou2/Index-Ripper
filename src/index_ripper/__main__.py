"""Entry point for `python -m index_ripper`."""
import sys


def _main() -> None:
    if "--smoke" in sys.argv:
        print("SMOKE_OK")
        raise SystemExit(0)

    if "--self-test" in sys.argv:
        from index_ripper.self_test import run_self_test

        result = run_self_test()
        print(
            f"SELF_TEST_OK total={result.total} files={result.files} dirs={result.directories}"
        )
        raise SystemExit(0)

    from index_ripper.utils import configure_tk_libraries
    configure_tk_libraries()

    if "--ui-smoke" in sys.argv:
        from index_ripper.app import WebsiteCopierCtk

        app = WebsiteCopierCtk(ui_smoke=True)
        app.window.after(0, app.window.destroy)
        app.run()
        print("UI_SMOKE_OK")
        raise SystemExit(0)

    from index_ripper.app import main
    main()


if __name__ == "__main__":
    _main()
