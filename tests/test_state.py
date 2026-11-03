"""State plumbing: resolution order, atomic JSON, credential/target validation, lock."""

from __future__ import annotations

from pathlib import Path

import pytest

from wechat_notify.state import (
    State,
    acquire_lock,
    atomic_write_json,
    load_credentials,
    load_target,
    read_json,
    resolve_state_dir,
)


def test_explicit_state_dir_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WECHAT_NOTIFY_STATE_DIR", str(tmp_path / "from-env"))
    assert resolve_state_dir(tmp_path / "explicit") == (tmp_path / "explicit").resolve()


def test_env_state_dir_used_when_no_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WECHAT_NOTIFY_STATE_DIR", str(tmp_path / "from-env"))
    assert resolve_state_dir(None) == (tmp_path / "from-env").resolve()


def test_fallback_is_stable_and_absolute(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WECHAT_NOTIFY_STATE_DIR", raising=False)
    resolved = resolve_state_dir(None)
    assert resolved.is_absolute()
    assert resolved.name == "state"


def test_atomic_write_json_is_readable_and_overwrites(state: State):
    atomic_write_json(state.credentials_path, {"bot_token": "one"})
    assert read_json(state.credentials_path) == {"bot_token": "one"}
    atomic_write_json(state.credentials_path, {"bot_token": "two"})
    assert read_json(state.credentials_path) == {"bot_token": "two"}


def test_read_json_tolerates_corruption(state: State):
    state.credentials_path.write_text("{not json", encoding="utf-8")
    assert read_json(state.credentials_path) is None
    assert load_credentials(state) is None


def test_read_json_accepts_a_utf8_bom(state: State):
    """Notepad saves JSON with a BOM; that must not look like a corrupt file."""
    state.credentials_path.write_bytes(b'\xef\xbb\xbf{"bot_token": "bom"}')
    assert read_json(state.credentials_path) == {"bot_token": "bom"}


def test_load_credentials_requires_bot_token(state: State):
    atomic_write_json(state.credentials_path, {"account_id": "x"})
    assert load_credentials(state) is None
    atomic_write_json(state.credentials_path, {"bot_token": "t"})
    assert load_credentials(state) == {"bot_token": "t"}


def test_load_target_requires_both_fields(state: State):
    atomic_write_json(state.target_path, {"user_id": "u"})
    assert load_target(state) is None
    atomic_write_json(state.target_path, {"user_id": "u", "context_token": "c"})
    assert load_target(state) == {"user_id": "u", "context_token": "c"}


def test_lock_is_exclusive(state: State):
    first = acquire_lock(state)
    assert first is not None
    try:
        assert acquire_lock(state) is None
    finally:
        first.release()
    second = acquire_lock(state)
    assert second is not None
    second.release()
