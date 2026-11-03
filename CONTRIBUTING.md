# Contributing

Thanks for taking a look. This project is small on purpose; the notes below keep it that way.

## Development setup

```bash
git clone https://github.com/OWNER/dsh-wechat-notify.git
cd dsh-wechat-notify
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run everything:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
node --test plugin/test/index.test.mjs     # needs Node >= 18
```

All tests must pass without network access. If your change needs the real gateway, keep it out
of `tests/` and describe the manual verification in the pull request instead.

## Ground rules

1. **Never touch real credentials in tests.** Point the state at `tmp_path` (the `state`
   fixture does this) instead of `~/.dsh` or `~/.wechat-notify`.
2. **Keep the exit-code contract.** `0/1/2/3/4` are documented in `README.md`,
   `SKILL.md` and `cli.py`; scripts and the plugin branch on them.
3. **Keep the skill contract.** `SKILL.md` is what the agent loads, and
   `scripts/wechat_notify.py` is what it and the plugin execute. Both must keep working after
   `install.ps1` / `install.sh` copies the bundle.
4. **No machine-specific paths in code.** Use `DSH_HOME`, `WECHAT_NOTIFY_*` or config fields.
   `tools/check_repo.py` enforces this in CI.
5. **No new runtime dependencies** without a very good reason. The only two are
   `wechat-openclaw-sdk` (the channel) and `qrcode` (QR rendering). The host plugin must stay
   dependency-free and Node-builtin-only.
6. **Chinese user-facing strings are fine** (the channel is WeChat); code, docstrings and
   commit messages should be English.

## Style

- Python 3.10+ syntax, type hints on public functions, `from __future__ import annotations`.
- Formatting and import order: `ruff format` / `ruff check --fix`. Line length 100.
- Comments explain *why*, not *what*; the modules already carry the protocol background.
- JavaScript: ESM, no semicolons-free bikeshedding -- just match `plugin/index.js`.

## Adding a feature

1. Open an issue first for anything that changes behaviour or adds a subcommand.
2. Add tests next to the existing ones (`tests/test_*.py`, `plugin/test/*.mjs`).
3. Update the docs that mention behaviour: `README.md`, `README.en.md`, `SKILL.md`
   (agent-facing) and `plugin/README.md` (plugin-facing).
4. Add a `CHANGELOG.md` entry under `## [Unreleased]`.

## Pull request checklist

- [ ] `ruff check` and `ruff format --check` pass
- [ ] `pytest` passes on Python 3.10+ (CI runs the matrix)
- [ ] `node --test plugin/test/index.test.mjs` passes if the plugin changed
- [ ] No credentials, tokens, personal paths or `state/` content in the diff
- [ ] Docs updated; `CHANGELOG.md` has an entry
- [ ] Exit codes and `SKILL.md` behaviour unchanged, or the change is documented and justified

## Reporting bugs

Use the issue template and include: OS, Python version, `wechat-notify --version`, the command
you ran, the exit code, and the relevant tail of `state/notify.log` **with ids and message
bodies redacted**.

Security issues: please follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
