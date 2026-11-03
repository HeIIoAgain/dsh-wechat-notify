# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.x | ✅ |

## What this tool stores, and why it matters

| File | Contents | Sensitivity |
|---|---|---|
| `state/credentials.json` | `bot_token`, `account_id`, gateway URL | **High** -- a bot identity. Anyone with it can send messages as your bot until it is revoked/expired. |
| `state/target.json` | `user_id`, `context_token` | **High** -- a live session token bound to your WeChat conversation. |
| `state/queue/` | Pending notifications and copied attachments | Medium -- whatever you tried to send. |
| `state/notify.log` | Timestamps, masked ids, **message bodies** | Medium -- bodies are logged verbatim. |

Nothing is encrypted at rest. Protect the directory (`icacls` / `chmod 700`), keep it off
sync/shared folders, and point `--state-dir` at an encrypted volume if you send sensitive
content.

## Reporting a vulnerability

Please **do not** open a public issue for anything that could leak credentials, allow command
injection, or bypass the "only send when explicitly asked" rule.

Instead, open a private security advisory on the repository
(GitHub → Security → Advisories → "Report a vulnerability") with:

- affected version (`wechat-notify --version`),
- a minimal reproduction,
- impact assessment (token disclosure, arbitrary file access, message injection, ...).

Expect an initial response within a few days. Please give us a reasonable window to ship a fix
before publishing details.

## Threat model notes

- **Subprocess boundary.** The host plugin spawns
  `<pythonPath> <scriptPath> send <body>`. Both paths come from configuration, not from
  message content; the body is passed as a single argv element, never through a shell.
- **Filesystem input.** `--file`, `--image` and `--attach` read arbitrary local paths by
  design (that is the feature). Do not run the tool as a service with untrusted callers.
- **Network.** Traffic goes to `https://ilinkai.weixin.qq.com` and its CDN. The gateway is
  selected by the login response; `--base-url` exists for testing and makes the client trust
  whatever host you give it.
- **Log injection.** Message bodies are written to `notify.log` after newline flattening in
  notifications, but a multiline `--file` body keeps its newlines. Treat the log as data.

## Hardening checklist

- [ ] `state/` is excluded from git (the shipped `.gitignore` does this)
- [ ] `state/` is not inside OneDrive/Dropbox/a network share
- [ ] The bot token is revoked (WeChat bot console) if it may have been exposed
- [ ] `notify.log` is rotated or deleted if it contained sensitive content
