"""Package metadata, constants and exit codes for the WeChat notifier."""

from __future__ import annotations

from datetime import timedelta, timezone

__version__ = "1.0.0"

PROJECT = "dsh-wechat-notify"
DISPLAY_NAME = "WeChat Notify"

#: iLink gateway used by the official WeChat bot channel.
DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"
#: ``bot_type=3`` is the WeChat bot channel used by iLink OpenClaw.
BOT_TYPE = "3"

#: All user-visible timestamps are rendered in China Standard Time.
TZ = timezone(timedelta(hours=8))

# Exit codes are part of the CLI contract: scripts and the DSH plugin branch on
# them, so they must never be renumbered.
EXIT_OK = 0
EXIT_ERROR = 1
"""Unexpected failure (network error, unreadable file, SDK exception...)."""

EXIT_NO_LOGIN = 2
"""No credentials on disk yet -- run ``login`` and scan the QR code."""

EXIT_NO_SESSION = 3
"""No usable ``context_token``; the content was queued instead of sent."""

EXIT_SESSION_EXPIRED = 4
"""``bot_token`` expired (gateway errcode -14); run ``login --force``."""

#: A ``context_token`` younger than this is considered fresh enough to send with.
DEFAULT_TOKEN_MAX_AGE = 30 * 60.0
#: ``prime`` waits this long for one inbound message.
DEFAULT_PRIME_TIMEOUT = 3 * 60.0
#: ``login`` keeps refreshing the QR code until this deadline.
DEFAULT_LOGIN_TIMEOUT = 8 * 60.0
#: Each individual QR code is polled for at most this long before a refresh.
QR_CODE_LIFETIME = 5 * 60.0
#: Sleep between two long-poll attempts / QR status polls (seconds).
POLL_INTERVAL = 1.0
#: A daemon heartbeat older than this means the daemon is gone.
DAEMON_STALE_AFTER = 15.0

#: Override the state directory (credentials, queue, logs) without flags.
STATE_ENV = "WECHAT_NOTIFY_STATE_DIR"
#: Python interpreter used by the optional DSH host plugin.
PYTHON_ENV = "WECHAT_NOTIFY_PYTHON"
#: Absolute path of ``wechat_notify.py`` for the optional DSH host plugin.
SCRIPT_ENV = "WECHAT_NOTIFY_SCRIPT"
