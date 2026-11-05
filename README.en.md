# dsh-wechat-notify

On-demand WeChat notifications (text, screenshots, files) for **DeepSeek Harness (DSH)**
agents and plain scripts, delivered through the WeChat iLink OpenClaw bot channel.

Nothing is ever pushed on its own: a message goes out only when you explicitly ask for it
("send me that on WeChat", "push the result to my WeChat", and so on).

[![CI](https://github.com/HeIIoAgain/dsh-wechat-notify/actions/workflows/ci.yml/badge.svg)](https://github.com/HeIIoAgain/dsh-wechat-notify/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

English | [简体中文](README.md)

---

## Why it exists

Long agent runs happen on a desktop you are not sitting at. This tool puts the outcome --
text, a screenshot, a PDF -- on your phone, either as a CLI call or as a DSH skill the agent
picks up when you ask for it.

What the channel itself does **not** allow (protocol limits, not laziness):

- It only delivers to the WeChat account that scanned the login QR code (1:1 chats; group
  behaviour is unverified).
- It **cannot** start a conversation cold: every outbound message carries a `context_token`
  that the gateway only issues after an inbound message. So before sending you need either a
  token younger than 30 minutes (`prime`) or a long-running `run` daemon that keeps refreshing it.
- It is rate limited. Batch your content.

## Features

- **Three triggers**: DSH skill (agent decides), CLI (you decide), optional host plugin
  (after every turn -- off by default).
- **Text, images and files** in one send call.
- **Nothing is lost**: if the token is missing or the gateway hiccups, the content is queued
  and flushed by the next `prime`/`run`.
- **Exit codes are a contract**: `0/1/2/3/4`, documented and covered by tests.
- **Zero-config install**: `install.ps1` / `install.sh` locate `$DSH_HOME/skills`, check
  Python, install dependencies.
- **Secrets stay local**: the `bot_token` lives in `state/credentials.json`; logs only ever
  show masked ids.
- **Cross-platform**: Windows, macOS, Linux. Screenshots are Windows-only (GDI, no input
  event injection).

## Install

### As a DSH skill (recommended)

```powershell
git clone https://github.com/HeIIoAgain/dsh-wechat-notify.git
cd dsh-wechat-notify
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1     # Windows
```

```bash
bash install.sh                                                       # macOS / Linux
```

This copies the bundle to `$DSH_HOME/skills/wechat-notify` (default `~/.dsh/skills/...`).
Restart DSH or open a new session and `wechat-notify` appears in the skill catalog.

Flags: `-Dest/--dest`, `-Python/--python`, `-NoDeps/--no-deps`, `-Force/--force`
(an existing `scripts/state` is always preserved).

### As a standalone CLI

```bash
python -m pip install "git+https://github.com/HeIIoAgain/dsh-wechat-notify.git"
wechat-notify --version
```

The state directory defaults to `~/.wechat-notify/state`; override it with `--state-dir` or
`WECHAT_NOTIFY_STATE_DIR`.

### From a checkout

```bash
python scripts/wechat_notify.py --version     # adds src/ to sys.path automatically
```

Requirements: Python 3.10+. Node 18+ only for the optional host plugin and its tests.

## First run (once per machine)

```bash
wechat-notify login
```

The CLI writes a QR code to `state/qr.png` and prints a tappable link. Scan it with WeChat,
confirm on the phone, and the credentials are stored (the `account_id` is printed, masked).
Re-scan only if you hit `errcode -14`.

> `credentials.json` is a bot identity. Treat it like a password; `state/` is git-ignored.

## Sending your first message

```bash
wechat-notify prime --timeout 180     # 1) waits for one inbound message
#   2) now send anything to the bot in WeChat, e.g. /ping
wechat-notify send "first message from DSH"   # 3) prime exits 0 -> this succeeds
```

Alternatively run the daemon and forget about tokens:

```bash
wechat-notify run
```

## Command reference

| Command | What it does |
|---|---|
| `login [--force] [--base-url URL]` | QR login, saves the `bot_token` |
| `send "text"` | Send text |
| `send --title "T" "text"` | Prefix the body with `【T】` |
| `send --image shot.png` | Send an image |
| `send --attach report.pdf` | Send a file |
| `send -` | Read the body from stdin |
| `send --file body.txt` | Read a UTF-8 file (avoids console encoding issues) |
| `prime [--timeout 180] [--max-age 1800]` | Wait for an inbound message, then flush the queue |
| `run` | Foreground daemon: poll, refresh the token, answer `/ping`, flush the queue |
| `status [--json]` | Login / token age / daemon / queue |
| `--state-dir DIR` | Override the state directory (accepted before or after the subcommand) |
| `--version` | Print the version |

A bare payload is shorthand for `send`:

```bash
wechat-notify "hi"     # == wechat-notify send "hi"
```

### Exit codes

| Code | Meaning | What to do |
|---|---|---|
| `0` | Sent | -- |
| `1` | Other error (network, file, SDK) | Check stderr; the content was queued |
| `2` | Not logged in | `login` |
| `3` | No usable `context_token` | Queued; run `prime` and message the bot |
| `4` | `bot_token` expired (`errcode -14`) | `login --force` |

## Using it from DSH

`SKILL.md` encodes the trigger rules: the agent sends only when you explicitly ask, checks
`status` first, and on exit code 3 runs `prime` and asks you to message the bot. There is no
"notify me when the task finishes" behaviour unless you enable the plugin below.

## Optional plugin: notify after every turn

`plugin/index.js` is a zero-dependency DSH host plugin that listens for `turn/end` and spawns
one `send`. It is **disabled by default**; enabling it, its full config table and the
environment variables it reads are documented in [plugin/README.md](plugin/README.md).
Set `minTurnMs` to at least 15000 unless you enjoy noise.

## Screenshots (Windows)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\screenshot.ps1 -Out "$env:TEMP\shot.png"
wechat-notify send --image "$env:TEMP\shot.png"
```

`-Mode window -WindowTitle "..."` captures a single window. The script uses GDI `BitBlt` /
`PrintWindow` and never calls `SendInput`/`SendKeys`, moves the cursor or steals focus -- it
prints idle-counter and cursor evidence to prove it. DRM content, the UAC secure desktop and
the lock screen cannot be captured.

## Security

- `state/credentials.json` and `state/target.json` are machine-local secrets. Never commit
  them, paste them, or keep them on a share.
- Ids are masked in output (`demo****.bot`), but **message bodies are written to
  `notify.log`** -- point the state directory at an encrypted volume if that matters.
- Content travels through Tencent's iLink gateway (`https://ilinkai.weixin.qq.com`) and CDN.
  That is inherent to the channel.
- See [SECURITY.md](SECURITY.md).

## Layout

```
SKILL.md                  DSH skill definition the agent reads
src/wechat_notify/        Python package (cli, state, queue, login, daemon)
scripts/                  compatibility entry point, .cmd launcher, screenshot.ps1
plugin/                   optional DSH host plugin (per-turn pushes)
tests/                    offline pytest suite (never touches real credentials)
docs/protocol.md          token lifecycle and protocol notes
install.ps1 / install.sh  installers
tools/check_repo.py       CI hygiene check (secrets, absolute paths)
```

## Development

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
node --test plugin/test/index.test.mjs
```

Everything runs offline: the SDK client and network calls are patched, and each test gets a
temporary state directory. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Exit code 3 / `prepare failed` | Token expired: `prime` + message the bot; queued items flush automatically |
| Exit code 4 / `errcode -14` | `login --force` |
| Message arrives, no phone notification | Delivered; check Do Not Disturb, this chat's "mute notifications", WeChat's notification permissions |
| `ModuleNotFoundError: wechat_openclaw` | `pip install -r requirements.txt` |
| Mojibake on Windows | Use `send --file body.txt` (UTF-8) instead of a command-line argument |
| Plugin does nothing | Check `plugin.log`; verify `enabled: true` and that `scriptPath` exists |

## Disclaimer

Unofficial project, not affiliated with Tencent or WeChat. Respect WeChat's terms of service
when using a bot account; you are responsible for your own account.

## License

[MIT](LICENSE)
