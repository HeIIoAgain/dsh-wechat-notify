"""Thin wrapper around the ``wechat-openclaw-sdk`` client.

Nothing here is import-time heavy: the SDK is imported lazily so ``status`` and
``--help`` keep working before dependencies are installed.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from .config import DEFAULT_BASE_URL
from .errors import NoLoginError, NoSessionError
from .state import State, load_credentials, load_target


def base_url_of(creds: dict) -> str:
    """Gateway base URL with any trailing slash removed."""
    return (creds.get("base_url") or DEFAULT_BASE_URL).rstrip("/")


def build_client(creds: dict) -> Any:
    """Build an SDK client for ``creds``.

    Kept as a module-level function so tests can monkeypatch it without a network.
    """
    from wechat_openclaw import NoopCoordinator, OpenClawClient, SDKConfig
    from wechat_openclaw.qrlogin import WeChatCredentials

    config = SDKConfig(base_url=base_url_of(creds))
    credentials = WeChatCredentials(
        bot_token=creds["bot_token"],
        account_id=creds.get("account_id", ""),
        base_url=creds.get("base_url", ""),
        user_id=creds.get("user_id", ""),
    )
    return OpenClawClient(credentials, NoopCoordinator(), config)


async def send_once(
    state: State,
    text: str | None = None,
    image: str | Path | None = None,
    attach: str | Path | None = None,
    target: dict | None = None,
) -> None:
    """Send exactly one notification (text, then image, then file).

    Every failure is raised to the caller, which decides between queueing and
    reporting. Sending order matters: the text arrives first so the recipient has
    context for the attachments.
    """
    creds = load_credentials(state)
    if not creds:
        raise NoLoginError()
    target = target or load_target(state)
    if not target:
        raise NoSessionError("还没有 context_token，请先运行 prime 并在微信里给机器人发一条消息")

    client = build_client(creds)
    try:
        user_id = target["user_id"]
        token = target["context_token"]
        if text:
            await client.send_text(user_id, text, context_token=token)
        if image:
            await client.send_image(user_id, Path(image).read_bytes(), context_token=token)
        if attach:
            path = Path(attach)
            await client.send_file(user_id, path.read_bytes(), path.name, context_token=token)
    finally:
        with contextlib.suppress(Exception):  # best-effort cleanup
            await client.api.aclose()
