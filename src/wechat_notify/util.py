"""Small helpers: timestamps, masking, humanised ages, logging, truncation."""

from __future__ import annotations

import contextlib
import sys
from datetime import datetime
from typing import TYPE_CHECKING

from .config import TZ

if TYPE_CHECKING:  # pragma: no cover - import cycle only for typing
    from .state import State


def now() -> datetime:
    """Current time in China Standard Time."""
    return datetime.now(TZ)


def now_str() -> str:
    """Current time formatted like ``2026-10-22 23:16:22``."""
    return now().strftime("%Y-%m-%d %H:%M:%S")


def mask(value: str | None) -> str:
    """Mask a secret-ish identifier so it can be printed and pasted safely.

    >>> mask("demo-bot-1234567890.bot")
    'demo****.bot'
    >>> mask(None)
    '(空)'
    """
    if not value:
        return "(空)"
    if len(value) <= 8:
        return value[:2] + "***"
    return value[:4] + "****" + value[-4:]


def age_text(ts: float | None) -> str:
    """Render ``time.time()`` deltas as a short Chinese age string."""
    import time

    if not ts:
        return "未知"
    seconds = max(0, int(time.time() - ts))
    if seconds < 60:
        return f"{seconds} 秒前"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前"
    if seconds < 86_400:
        return f"{seconds // 3600} 小时前"
    return f"{seconds // 86400} 天前"


def truncate(text: str, limit: int) -> str:
    """Collapse whitespace and cut ``text`` to ``limit`` characters."""
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


def log(state: State, message: str) -> None:
    """Print a timestamped line and append it to ``<state>/notify.log``.

    Logging must never be the reason a send fails, so file errors are swallowed.
    """
    line = f"[{now_str()}] {message}"
    print(line, flush=True)
    try:
        state.dir.mkdir(parents=True, exist_ok=True)
        with state.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def configure_stdio() -> None:
    """Force UTF-8 on stdout/stderr so Chinese output survives Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError, ValueError):
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]


__all__ = [
    "age_text",
    "configure_stdio",
    "log",
    "mask",
    "now",
    "now_str",
    "truncate",
]
