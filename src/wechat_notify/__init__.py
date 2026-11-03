"""On-demand WeChat notifications for DSH agents (and your own scripts).

Public surface is intentionally tiny: the CLI in :mod:`wechat_notify.cli` is the
supported entry point; the helper modules are implementation details.
"""

from __future__ import annotations

from .config import __version__

__all__ = ["__version__"]
