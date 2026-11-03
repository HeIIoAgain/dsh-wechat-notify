"""Queue behaviour: durable backlog, attachment copies, flush ordering."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from wechat_notify import client, queueing
from wechat_notify.errors import NoSessionError
from wechat_notify.state import State, read_json


def run_flush(state: State) -> int:
    return asyncio.run(queueing.flush_queue(state))


def test_enqueue_persists_text_and_reason(state: State, tmp_path: Path):
    path = queueing.enqueue(state, "queued text", "no token")
    record = read_json(path)
    assert record is not None
    assert record["text"] == "queued text"
    assert record["reason"] == "no token"
    assert record["created_at"]
    assert path.parent == state.queue_dir


def test_enqueue_copies_attachments_into_the_queue(state: State, tmp_path: Path):
    source = tmp_path / "report.txt"
    source.write_text("payload", encoding="utf-8")

    path = queueing.enqueue(state, "see attached", "no token", attach=str(source))
    record = read_json(path) or {}

    copied = Path(record["attach"])
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == "payload"
    assert state.queue_dir in copied.parents

    source.unlink()  # the queue must survive deletion of the original
    assert copied.is_file()


def test_pending_is_ordered_by_time(state: State):
    first = queueing.enqueue(state, "one", "r")
    second = queueing.enqueue(state, "two", "r")
    assert queueing.pending(state) == [first, second]


def test_flush_sends_in_order_and_archives(state: State, monkeypatch: pytest.MonkeyPatch):
    calls: list[str | None] = []

    async def fake_send(state, text=None, image=None, attach=None, target=None):
        calls.append(text)

    monkeypatch.setattr(client, "send_once", fake_send)
    for text in ("one", "two"):
        queueing.enqueue(state, text, "no token")

    assert run_flush(state) == 2
    assert calls == ["one", "two"]
    assert queueing.pending(state) == []
    assert len(list(state.sent_dir.glob("*.json"))) == 2


def test_flush_stops_when_a_send_fails(state: State, monkeypatch: pytest.MonkeyPatch):
    attempted: list[str | None] = []

    async def failing_send(state, text=None, image=None, attach=None, target=None):
        attempted.append(text)
        raise RuntimeError("gateway hiccup")

    monkeypatch.setattr(client, "send_once", failing_send)
    queueing.enqueue(state, "one", "r")
    queueing.enqueue(state, "two", "r")

    assert run_flush(state) == 0
    assert attempted == ["one"]  # later items are not attempted
    assert len(queueing.pending(state)) == 2  # nothing is lost


def test_flush_stops_without_a_session_token(state: State, monkeypatch: pytest.MonkeyPatch):
    async def no_session(state, text=None, image=None, attach=None, target=None):
        raise NoSessionError("no token")

    monkeypatch.setattr(client, "send_once", no_session)
    queueing.enqueue(state, "keep me", "r")

    assert run_flush(state) == 0
    assert len(queueing.pending(state)) == 1


def test_flush_skips_entries_whose_attachment_vanished(
    state: State, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    sent: list[tuple[str | None, str | None]] = []

    async def fake_send(state, text=None, image=None, attach=None, target=None):
        sent.append((text, image))

    monkeypatch.setattr(client, "send_once", fake_send)
    source = tmp_path / "gone.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\n")
    path = queueing.enqueue(state, "text", "r", image=str(source))
    record = read_json(path) or {}
    Path(record["image"]).unlink()

    assert run_flush(state) == 1
    assert sent == [("text", None)]


def test_flush_drops_empty_records(state: State, monkeypatch: pytest.MonkeyPatch):
    async def fake_send(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("nothing to send")

    monkeypatch.setattr(client, "send_once", fake_send)
    state.queue_dir.mkdir(parents=True, exist_ok=True)
    empty = state.queue_dir / "0-empty.json"
    empty.write_text("{}", encoding="utf-8")

    assert run_flush(state) == 0
    assert not empty.exists()
