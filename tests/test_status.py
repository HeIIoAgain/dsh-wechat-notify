"""`status` output: human summary and the machine-readable ``--json`` form."""

from __future__ import annotations

import json

import pytest

from wechat_notify import cli, config
from wechat_notify.state import State, atomic_write_json


def test_status_reports_empty_state(tmp_path, capsys):
    code = cli.main(["--state-dir", str(tmp_path), "status"])
    out = capsys.readouterr().out
    assert code == config.EXIT_OK
    assert "未登录" in out
    assert "会话令牌：❌" in out
    assert "待补发队列：0 条" in out


def test_status_json_shape(logged_in: State, capsys: pytest.CaptureFixture[str]):
    atomic_write_json(
        logged_in.target_path,
        {
            "user_id": "wx-user-test@im.wechat",
            "context_token": "token-value",
            "updated_at": "2026-10-22 23:16:22",
            "updated_ts": 0,
        },
    )
    atomic_write_json(
        logged_in.daemon_path,
        {"pid": 4242, "started_at": "2026-10-22 23:15:57", "heartbeat": 9e18, "queue": 0},
    )

    code = cli.main(["--state-dir", str(logged_in.dir), "status", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == config.EXIT_OK
    assert payload["login"]["ok"] is True
    assert payload["login"]["accountId"] == "demo****.bot"
    assert payload["token"]["ok"] is True
    assert payload["queue"]["count"] == 0
    assert payload["stateDir"] == str(logged_in.dir)


def test_status_counts_queued_items(logged_in: State, capsys: pytest.CaptureFixture[str]):
    from wechat_notify.queueing import enqueue

    enqueue(logged_in, "queued one", "no token")

    code = cli.main(["--state-dir", str(logged_in.dir), "status", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == config.EXIT_OK
    assert payload["queue"]["count"] == 1
    assert payload["queue"]["items"][0]["text"] == "queued one"


def test_status_reports_stale_daemon_as_stopped(
    logged_in: State, capsys: pytest.CaptureFixture[str]
):
    atomic_write_json(
        logged_in.daemon_path,
        {"pid": 1, "started_at": "2026-10-22 00:00:00", "heartbeat": 0, "queue": 0},
    )

    cli.main(["--state-dir", str(logged_in.dir), "status"])
    out = capsys.readouterr().out
    assert "常驻进程：⛔ 未运行" in out
