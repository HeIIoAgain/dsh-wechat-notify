"""`send` subcommand: exit-code contract, queueing fallbacks, input handling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wechat_notify import cli, config
from wechat_notify.state import State, atomic_write_json


def run(capsys, *argv: str) -> tuple[int, str]:
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def test_send_without_login_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    code, out = run(capsys, "--state-dir", str(tmp_path / "s"), "send", "hi")
    assert code == config.EXIT_NO_LOGIN
    assert "还没有扫码登录" in out


def test_send_without_token_queues_and_exits_3(
    logged_in: State, capsys: pytest.CaptureFixture[str]
):
    code, out = run(capsys, "--state-dir", str(logged_in.dir), "send", "hi")
    assert code == config.EXIT_NO_SESSION
    assert "已排队" in out
    queued = list(logged_in.queue_dir.glob("*.json"))
    assert len(queued) == 1
    assert json.loads(queued[0].read_text(encoding="utf-8"))["text"] == "hi"


def test_successful_send_exits_0(
    logged_in: State, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    atomic_write_json(logged_in.target_path, {"user_id": "u", "context_token": "c"})
    calls: list[dict] = []

    async def fake_send(state, text=None, image=None, attach=None, target=None):
        calls.append({"text": text, "image": image, "attach": attach})

    monkeypatch.setattr(cli, "send_once", fake_send)
    code, out = run(capsys, "--state-dir", str(logged_in.dir), "send", "hi")
    assert code == config.EXIT_OK
    assert "✅ 已发送" in out
    assert calls == [{"text": "hi", "image": None, "attach": None}]


def test_title_is_prefixed(
    logged_in: State, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    sent: list[str | None] = []

    async def fake_send(state, text=None, image=None, attach=None, target=None):
        sent.append(text)

    monkeypatch.setattr(cli, "send_once", fake_send)
    code, _ = run(capsys, "--state-dir", str(logged_in.dir), "send", "--title", "标题", "正文")
    assert code == config.EXIT_OK
    assert sent == ["【标题】\n正文"]


def test_missing_image_file_exits_1(logged_in: State, capsys: pytest.CaptureFixture[str]):
    code, out = run(
        capsys, "--state-dir", str(logged_in.dir), "send", "--image", "E:/nope/missing.png"
    )
    assert code == config.EXIT_ERROR
    assert "图片不存在" in out


def test_empty_payload_exits_1(logged_in: State, capsys: pytest.CaptureFixture[str]):
    code, out = run(capsys, "--state-dir", str(logged_in.dir), "send")
    assert code == config.EXIT_ERROR
    assert "内容为空" in out


def test_file_input_keeps_unicode(
    logged_in: State,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    body = tmp_path / "body.txt"
    body.write_text("中文正文\n第二行", encoding="utf-8")
    sent: list[str | None] = []

    async def fake_send(state, text=None, image=None, attach=None, target=None):
        sent.append(text)

    monkeypatch.setattr(cli, "send_once", fake_send)
    code, _ = run(capsys, "--state-dir", str(logged_in.dir), "send", "--file", str(body))
    assert code == config.EXIT_OK
    assert sent == ["中文正文\n第二行"]


def test_expired_session_is_classified_as_exit_4(
    logged_in: State, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    class Expired(Exception):
        api_errcode = -14

    async def fake_send(state, text=None, image=None, attach=None, target=None):
        raise Expired("session expired")

    monkeypatch.setattr(cli, "send_once", fake_send)
    code, out = run(capsys, "--state-dir", str(logged_in.dir), "send", "hi")
    assert code == config.EXIT_SESSION_EXPIRED
    assert "errcode=-14" in out
    assert len(list(logged_in.queue_dir.glob("*.json"))) == 1


def test_prepare_failed_is_classified_as_exit_3(
    logged_in: State, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    class PrepareFailed(Exception):
        api_errcode = -2

    async def fake_send(state, text=None, image=None, attach=None, target=None):
        raise PrepareFailed("prepare failed")

    monkeypatch.setattr(cli, "send_once", fake_send)
    code, out = run(capsys, "--state-dir", str(logged_in.dir), "send", "hi")
    assert code == config.EXIT_NO_SESSION
    assert "prepare failed" in out


def test_unknown_errors_are_queued_as_exit_1(
    logged_in: State, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    async def fake_send(state, text=None, image=None, attach=None, target=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "send_once", fake_send)
    code, out = run(capsys, "--state-dir", str(logged_in.dir), "send", "hi")
    assert code == config.EXIT_ERROR
    assert "发送失败" in out
    assert len(list(logged_in.queue_dir.glob("*.json"))) == 1
