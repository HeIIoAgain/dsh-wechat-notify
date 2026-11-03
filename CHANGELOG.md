# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-26

First public release. This is the initial GitHub-ready version of what was previously a
private `wechat-notify-skill-0.1.0` bundle.

### Added

- `wechat-notify` console script and `python -m wechat_notify` entry point.
- `--version`, `--state-dir` (accepted before or after the subcommand) and `status --json`.
- `send --file` for reading the body from a UTF-8 file, avoiding Windows console mojibake.
- Offline test suite (pytest) for state, queue, send classification, login rendering, daemon
  helpers and CLI wiring; 61 tests.
- Node test suite for the optional host plugin (11 tests) using `node:test`.
- GitHub Actions CI: Python matrix (3.10/3.12/3.13 x Linux/macOS/Windows), ruff check and
  format, plugin tests, repository hygiene job.
- `tools/check_repo.py` to fail CI on committed tokens, credentials or absolute personal paths.
- Documentation: Chinese and English READMEs, protocol notes, plugin guide, contributing,
  security policy, code of conduct, issue and pull-request templates.

### Changed

- The 800-line single-file script was split into the `wechat_notify` package
  (`cli`, `client`, `state`, `queueing`, `login`, `daemon`, `util`, `config`, `errors`).
- `scripts/wechat_notify.py` is now a thin compatibility shim, so `SKILL.md` and the host
  plugin keep working unchanged.
- Configuration is explicit: the host plugin no longer hardcodes machine paths; every default
  comes from `DSH_HOME` / `WECHAT_NOTIFY_*` environment variables or the `cordis.patch.yml`
  config block.
- Errors are classified by gateway `errcode` instead of message sniffing alone, and every
  classification is covered by a test.
- `flush_queue` stops at the first failure (keeping the rest of the backlog) instead of
  continuing past an error.

### Fixed

- `prime` no longer logs "已扫码，等待手机上确认…" on every poll iteration.
- Queue flushes no longer drop an item when its attachment was deleted; the text is still sent.
- `login` no longer takes an unused `force` argument internally.

### Security

- `.gitignore` excludes the whole `scripts/state/` tree (bot token, context token, queue,
  logs) plus loose `credentials.json` / `target.json` files.
- Logs and `status` only print masked account and user ids.

## [0.1.0] - 2026-10-22

Initial private bundle: `login` / `prime` / `send` / `run` / `status`, Windows screenshot
helper, and an opt-in host plugin. Never published.
