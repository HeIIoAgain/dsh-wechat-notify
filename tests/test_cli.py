"""CLI wiring: version, help, shorthand, and state-dir placement."""

from __future__ import annotations

from pathlib import Path

import pytest

from wechat_notify import __version__, cli, config


def test_version_flag(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_help_lists_every_command(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--help"])
    out = capsys.readouterr().out
    assert excinfo.value.code == 0
    for command in ("login", "run", "prime", "send", "status"):
        assert command in out


def test_bare_text_is_treated_as_send(tmp_path: Path):
    assert cli.main(["--state-dir", str(tmp_path / "s"), "你好"]) == config.EXIT_NO_LOGIN


def test_state_dir_is_accepted_after_the_subcommand(tmp_path: Path):
    state_dir = tmp_path / "after"
    assert cli.main(["send", "hi", "--state-dir", str(state_dir)]) == config.EXIT_NO_LOGIN


def test_state_dir_flag_beats_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setenv(config.STATE_ENV, str(tmp_path / "from-env"))
    assert cli.main(["--state-dir", str(tmp_path / "flag"), "status"]) == config.EXIT_OK
    assert str(tmp_path / "flag") in capsys.readouterr().out


def test_missing_subcommand_is_an_error(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2
