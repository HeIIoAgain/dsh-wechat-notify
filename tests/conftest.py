"""Shared fixtures: make ``src/`` importable and provide isolated state dirs."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wechat_notify.state import State  # noqa: E402


@pytest.fixture()
def state(tmp_path: Path) -> State:
    """A throwaway state directory -- never the real ``~/.wechat-notify``."""
    return State.at(tmp_path / "state").ensure()


@pytest.fixture()
def logged_in(state: State) -> State:
    """State with a fake credential file (no network involved)."""
    from wechat_notify.state import atomic_write_json

    atomic_write_json(
        state.credentials_path,
        {
            "bot_token": "test-token",
            "account_id": "demo-bot-1234567890.bot",
            "base_url": "https://ilinkai.weixin.qq.com",
            "user_id": "u-1",
            "logged_in_at": "2026-10-22 23:14:23",
        },
    )
    return state
