from __future__ import annotations

import traceback

import typer

from .cli import app


def main(argv: list[str] | None = None) -> int:
    try:
        app(standalone_mode=False, args=argv)
        return 0
    except typer.Exit as exc:
        return int(exc.exit_code)
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
