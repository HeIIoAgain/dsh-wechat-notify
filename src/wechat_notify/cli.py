"""Command-line interface.

Design rules that the tests rely on:

* ``main(argv)`` is pure with respect to process state: it never calls
  ``sys.exit`` and always returns an integer exit code.
* Every subcommand receives an explicit :class:`~wechat_notify.state.State`, so a
  test can point the CLI at a temporary directory with ``--state-dir``.
* Exit codes are the public contract (see :mod:`wechat_notify.config`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from . import __version__, config, daemon, login, queueing
from .client import base_url_of, send_once
from .errors import NoLoginError, NoSessionError
from .state import State, load_credentials, load_target, read_json
from .util import age_text, configure_stdio, mask

COMMANDS = ("login", "run", "prime", "send", "status")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


async def cmd_login(args: argparse.Namespace, state: State) -> int:
    base = args.base_url or config.DEFAULT_BASE_URL
    existing = load_credentials(state)
    if existing and not args.force:
        print(
            f"已有登录凭据（account_id={mask(existing.get('account_id'))}，"
            f"登录于 {existing.get('logged_in_at', '未知')}）。"
        )
        print("如果推送时报「会话过期 / prepare failed」，请加 --force 重新扫码。")
        return config.EXIT_OK
    if args.base_url:
        print(f"使用自定义网关：{base}")
    try:
        await login.qr_login(state, base_url=base, timeout=args.timeout)
    except Exception as exc:
        print(f"登录失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return config.EXIT_ERROR

    print("\n下一步：运行 `wechat-notify run`，然后在微信里给机器人随便发一条消息，")
    print("       这样才有 context_token，之后才能主动推送。")
    return config.EXIT_OK


async def cmd_send(args: argparse.Namespace, state: State) -> int:
    text = args.text
    if args.file:
        try:
            text = Path(args.file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            print(f"读不到文件：{exc}", file=sys.stderr)
            return config.EXIT_ERROR
    if text == "-":
        text = sys.stdin.read().strip()
    if args.title:
        text = f"【{args.title}】\n{text or ''}".strip()

    image, attach = args.image, args.attach
    for label, path in (("图片", image), ("附件", attach)):
        if path and not Path(path).is_file():
            print(f"{label}不存在：{path}", file=sys.stderr)
            return config.EXIT_ERROR

    text = (text or "").strip()
    if not text and not image and not attach:
        print("内容为空，什么都没发。", file=sys.stderr)
        return config.EXIT_ERROR

    what: list[str] = []
    if text:
        what.append(f"{len(text)} 字")
    if image:
        what.append(f"图片 {Path(image).name}")
    if attach:
        what.append(f"附件 {Path(attach).name}")
    print("发送中…（" + "，".join(what) + "）", flush=True)

    try:
        await send_once(state, text or None, image=image, attach=attach)
    except NoLoginError:
        print("还没有扫码登录。先运行：wechat-notify login", file=sys.stderr)
        return config.EXIT_NO_LOGIN
    except NoSessionError as exc:
        path = queueing.enqueue(state, text, str(exc), image, attach)
        print(f"没有可用的会话令牌，已排队：{path.name}", file=sys.stderr)
        print("解决办法：运行 prime，然后在微信里给机器人发一条任意消息。", file=sys.stderr)
        return config.EXIT_NO_SESSION
    except Exception as exc:
        errcode = getattr(exc, "api_errcode", None)
        message = str(exc)
        if errcode == -14 or "session expired" in message.lower():
            path = queueing.enqueue(state, text, message, image, attach)
            print(f"登录已过期（errcode=-14），已排队：{path.name}", file=sys.stderr)
            print("请重新扫码：wechat-notify login --force", file=sys.stderr)
            return config.EXIT_SESSION_EXPIRED
        if errcode == -2 or "prepare failed" in message.lower():
            path = queueing.enqueue(state, text, message, image, attach)
            print(f"会话令牌失效（prepare failed），已排队：{path.name}", file=sys.stderr)
            print("请运行 prime，然后在微信里给机器人发一条任意消息刷新令牌。", file=sys.stderr)
            return config.EXIT_NO_SESSION
        path = queueing.enqueue(state, text, f"{type(exc).__name__}: {message}", image, attach)
        print(f"发送失败：{type(exc).__name__}: {message}\n已排队：{path.name}", file=sys.stderr)
        return config.EXIT_ERROR

    print("✅ 已发送", flush=True)
    return config.EXIT_OK


async def cmd_prime(args: argparse.Namespace, state: State) -> int:
    return await daemon.prime(state, timeout=args.timeout, max_age=args.max_age)


async def cmd_run(args: argparse.Namespace, state: State) -> int:
    return await daemon.run_forever(state)


def cmd_status(args: argparse.Namespace, state: State) -> int:
    creds = load_credentials(state)
    target = load_target(state)
    alive = daemon.daemon_alive(state)
    pending = queueing.pending(state)

    if args.json:
        queued: list[dict] = []
        for path in pending[:20]:
            item = read_json(path) or {}
            queued.append(
                {
                    "name": path.name,
                    "createdAt": item.get("created_at"),
                    "text": (item.get("text") or "")[:120],
                }
            )
        payload = {
            "stateDir": str(state.dir),
            "version": __version__,
            "login": {
                "ok": bool(creds),
                "accountId": mask(creds.get("account_id")) if creds else None,
                "baseUrl": base_url_of(creds) if creds else None,
                "loggedInAt": creds.get("logged_in_at") if creds else None,
            },
            "token": {
                "ok": bool(target),
                "updatedAt": target.get("updated_at") if target else None,
                "ageSeconds": (
                    max(0, int(time.time() - float(target.get("updated_ts") or 0)))
                    if target
                    else None
                ),
            },
            "daemon": {
                "running": bool(alive),
                "pid": alive.get("pid") if alive else None,
                "startedAt": alive.get("started_at") if alive else None,
            },
            "queue": {"count": len(pending), "items": queued},
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return config.EXIT_OK

    print(f"目录：{state.dir}")
    if not creds:
        print("登录：❌ 未登录（跑 login 扫码）")
    else:
        print(
            f"登录：✅ account_id={mask(creds.get('account_id'))}，"
            f"网关={base_url_of(creds)}，登录于 {creds.get('logged_in_at', '未知')}"
        )

    if not target:
        print("会话令牌：❌ 无（跑 prime，然后在微信里给机器人发一条消息）")
    else:
        print(
            f"会话令牌：✅ 更新于 {target.get('updated_at', '未知')}"
            f"（{age_text(target.get('updated_ts'))}），user={mask(target.get('user_id'))}"
        )

    if alive:
        print(
            f"常驻进程：✅ 运行中（pid={alive.get('pid')}，自 {alive.get('started_at')}，"
            f"队列 {alive.get('queue', 0)} 条）"
        )
    else:
        print("常驻进程：⛔ 未运行（按需发送用 prime 准备令牌即可，不需要常驻）")

    print(f"待补发队列：{len(pending)} 条")
    for path in pending[:5]:
        item = read_json(path) or {}
        text = (item.get("text") or "").replace("\n", " ")
        print(f"  - {path.name}  {item.get('created_at', '')}  {text[:50]}")
    return config.EXIT_OK


# ---------------------------------------------------------------------------
# Parser plumbing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wechat-notify",
        description="微信通知（微信 iLink OpenClaw 机器人渠道）",
        epilog="直接给出文字（不带子命令）等价于 `wechat-notify send <文字>`。",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    # Declared on a parent parser as well so `--state-dir` is accepted both before
    # and after the subcommand. SUPPRESS matters: argparse copies a subparser's whole
    # namespace back into the parent one, so a plain `None` default would wipe out a
    # value parsed before the subcommand name.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--state-dir", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument(
        "--state-dir",
        default=None,
        help="状态目录（默认 $WECHAT_NOTIFY_STATE_DIR，否则 ~/.wechat-notify/state）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_login = sub.add_parser("login", parents=[common], help="扫码登录并保存凭据")
    p_login.add_argument("--force", action="store_true", help="强制重新扫码（令牌过期时用）")
    p_login.add_argument("--base-url", default=None, help="自定义网关地址")
    p_login.add_argument(
        "--timeout", type=float, default=config.DEFAULT_LOGIN_TIMEOUT, help="等待扫码的秒数"
    )
    p_login.set_defaults(func=cmd_login)

    p_run = sub.add_parser("run", parents=[common], help="前台常驻：接收消息、刷新令牌、补发队列")
    p_run.set_defaults(func=cmd_run)

    p_send = sub.add_parser("send", parents=[common], help="发送一条微信消息（文字 / 图片 / 文件）")
    p_send.add_argument("text", nargs="?", default="", help="要发送的文字（- 表示从 stdin 读）")
    p_send.add_argument("--file", help="从文本文件读取文字内容")
    p_send.add_argument("--image", help="发一张图片（本地路径）")
    p_send.add_argument("--attach", help="发一个文件（本地路径）")
    p_send.add_argument("--title", help="标题，会加在正文前面")
    p_send.set_defaults(func=cmd_send)

    p_prime = sub.add_parser(
        "prime", parents=[common], help="等待入站消息以刷新会话令牌（发送前的准备）"
    )
    p_prime.add_argument(
        "--timeout", type=float, default=config.DEFAULT_PRIME_TIMEOUT, help="最多等多少秒"
    )
    p_prime.add_argument(
        "--max-age",
        type=float,
        default=config.DEFAULT_TOKEN_MAX_AGE,
        help="令牌在这个秒数内刷新过就直接跳过（0 = 总是刷新）",
    )
    p_prime.set_defaults(func=cmd_prime)

    p_status = sub.add_parser("status", parents=[common], help="查看登录 / 令牌 / 常驻进程 / 队列")
    p_status.add_argument("--json", action="store_true", help="输出机器可读的 JSON")
    p_status.set_defaults(func=cmd_status)
    return parser


_GLOBAL_VALUE_OPTS = ("--state-dir",)


def _normalise_argv(args_list: list[str]) -> list[str]:
    """Turn ``wechat-notify 你好`` into ``wechat-notify send 你好``.

    Global options may appear before the shorthand text, so the scan skips known
    value-taking options instead of assuming ``argv[0]`` is the payload. Anything
    that already looks like a command or an unknown flag is returned untouched so
    argparse can produce its normal error message.
    """
    index = 0
    while index < len(args_list):
        token = args_list[index]
        if token in _GLOBAL_VALUE_OPTS:
            index += 2
            continue
        if token.startswith("--state-dir="):
            index += 1
            continue
        if token.startswith("-") or token in COMMANDS:
            return args_list
        return [*args_list[:index], "send", *args_list[index:]]
    return args_list


def main(argv: list[str] | None = None) -> int:
    """Entry point used by both the console script and ``scripts/wechat_notify.py``."""
    configure_stdio()
    args_list = _normalise_argv(list(sys.argv[1:] if argv is None else argv))

    args = build_parser().parse_args(args_list)
    state = State.at(getattr(args, "state_dir", None))

    result = args.func(args, state)
    if asyncio.iscoroutine(result):
        return asyncio.run(result)
    return result
