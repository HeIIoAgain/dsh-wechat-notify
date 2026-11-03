#!/usr/bin/env python
"""Compatibility entry point for DSH skill bundles.

``SKILL.md`` and the optional host plugin call this file by path, which keeps the
skill working whether the bundle is installed under ``$DSH_HOME/skills`` or run
straight from a git checkout. It simply puts ``src/`` on ``sys.path`` and defers to
:func:`wechat_notify.cli.main`.

Equivalent forms::

    python scripts/wechat_notify.py status
    python -m wechat_notify status          # after `pip install .`
    wechat-notify status                    # console script
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SRC_DIR = _SCRIPTS_DIR.parent / "src"
if _SRC_DIR.is_dir() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from wechat_notify.cli import main  # noqa: E402  (path setup must run first)

if __name__ == "__main__":
    raise SystemExit(main())
