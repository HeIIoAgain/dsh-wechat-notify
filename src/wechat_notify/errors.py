"""Domain errors that map onto documented CLI exit codes."""

from __future__ import annotations


class NoLoginError(RuntimeError):
    """No ``bot_token`` on disk (exit code 2)."""


class NoSessionError(RuntimeError):
    """No usable ``context_token``; the caller should queue the content (exit code 3)."""
