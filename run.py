#!/usr/bin/env python3
import sys
import traceback
from pathlib import Path

from app.cli import main


def _log_error(exc):
    try:
        from app import config

        config.STATE_DIR.mkdir(parents=True, exist_ok=True)
        (config.STATE_DIR / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        _log_error(exc)
        raise
