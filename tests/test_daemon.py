"""Daemon helpers: inbound parsing, token persistence, heartbeat freshness, replies."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from wechat_notify.daemon import _auto_reply, daemon_alive, extract_text, remember_target
from wechat_notify.state import State, atomic_write_json, load_target


def message(text: str = "你好", user: str = "wx-user-test@im.wechat", token: str = "ctx-1"):
    return SimpleNamespace(
        from_user_id=user,
        context_token=token,
        item_list=[SimpleNamespace(text_item=SimpleNamespace(text=text), voice_item=None)],
    )


def test_extract_text_reads_text_items():
    assert extract_text(message("hi there")) == "hi there"


def test_extract_text_falls_back_to_voice_transcript():
    voice = SimpleNamespace(
        from_user_id="u",
        context_token="t",
        item_list=[SimpleNamespace(text_item=None, voice_item=SimpleNamespace(text="语音转写"))],
    )
    assert extract_text(voice) == "语音转写"


def test_extract_text_joins_multiple_items():
    multi = SimpleNamespace(
        from_user_id="u",
        context_token="t",
        item_list=[
            SimpleNamespace(text_item=SimpleNamespace(text="第一行"), voice_item=None),
            SimpleNamespace(text_item=SimpleNamespace(text="第二行"), voice_item=None),
        ],
    )
    assert extract_text(multi) == "第一行\n第二行"


def test_remember_target_persists_token(state: State):
    remember_target(state, message("你好", token="ctx-42"), "你好")

    target = load_target(state)
    assert target is not None
    assert target["user_id"] == "wx-user-test@im.wechat"
    assert target["context_token"] == "ctx-42"
    assert target["last_text"] == "你好"
    assert target["updated_ts"] > 0


def test_daemon_alive_requires_a_fresh_heartbeat(state: State):
    atomic_write_json(
        state.daemon_path,
        {"pid": 1, "started_at": "now", "heartbeat": time.time(), "queue": 0},
    )
    assert daemon_alive(state) is not None
    assert daemon_alive(state)["pid"] == 1


def test_daemon_alive_rejects_stale_or_corrupt_heartbeats(state: State):
    atomic_write_json(state.daemon_path, {"heartbeat": 0})
    assert daemon_alive(state) is None

    atomic_write_json(state.daemon_path, {"heartbeat": "not-a-number"})
    assert daemon_alive(state) is None

    state.daemon_path.write_text("{", encoding="utf-8")
    assert daemon_alive(state) is None


@pytest.mark.parametrize("text", ["/ping", "/P", "ping", "在吗", "在不在"])
def test_ping_always_gets_an_answer(text: str):
    reply = _auto_reply(text, first_contact=False)
    assert reply is not None
    assert "在线" in reply


def test_first_contact_gets_one_confirmation():
    reply = _auto_reply("你好", first_contact=True)
    assert reply is not None
    assert "已连接微信通知" in reply


def test_ordinary_messages_stay_silent():
    assert _auto_reply("晚饭吃什么", first_contact=False) is None
