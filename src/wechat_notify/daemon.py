"""Long-running helpers: ``prime`` (wait for an inbound message) and ``run`` (daemon).

Both exist because of one protocol rule: an outbound message must carry a
``context_token``, and that token is only ever echoed by the gateway after the user
sends something to the bot. So before pushing anything we need either a recent
token (``prime``) or a process that keeps listening (``run``).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import time

from . import client, queueing
from .config import (
    DAEMON_STALE_AFTER,
    EXIT_ERROR,
    EXIT_NO_LOGIN,
    EXIT_NO_SESSION,
    EXIT_OK,
    EXIT_SESSION_EXPIRED,
    POLL_INTERVAL,
)
from .state import (
    State,
    acquire_lock,
    atomic_write_json,
    load_credentials,
    load_target,
    read_json,
)
from .util import log, mask, now_str


def extract_text(message) -> str:
    """Concatenate text (and voice transcripts) from an SDK message object."""
    parts: list[str] = []
    for item in message.item_list or []:
        if item.text_item and item.text_item.text:
            parts.append(item.text_item.text)
        elif item.voice_item and item.voice_item.text:
            parts.append(item.voice_item.text)
    return "\n".join(parts).strip()


def remember_target(state: State, message, text: str) -> dict:
    """Persist the sender id and the fresh ``context_token`` from an inbound message."""
    target = {
        "user_id": message.from_user_id,
        "context_token": message.context_token,
        "updated_at": now_str(),
        "updated_ts": time.time(),
        "last_text": text[:100],
    }
    atomic_write_json(state.target_path, target)
    return target


def daemon_alive(state: State) -> dict | None:
    """Return the heartbeat when it is younger than :data:`DAEMON_STALE_AFTER`."""
    data = read_json(state.daemon_path)
    if not data:
        return None
    try:
        fresh = time.time() - float(data.get("heartbeat", 0)) < DAEMON_STALE_AFTER
    except (TypeError, ValueError):
        return None
    return data if fresh else None


def _auto_reply(text: str, first_contact: bool) -> str | None:
    """Canned replies that make the bot feel alive during setup.

    ``/ping`` always answers, a brand new conversation answers once, everything else
    stays silent so the bot never talks over the user's own messages.
    """
    lowered = text.lower()
    if lowered in ("/ping", "/p", "ping", "在吗", "在不在"):
        return f"✅ 微信通知在线 · {now_str()}\n以后我可以主动给你发消息了。"
    if first_contact:
        return f"✅ 已连接微信通知 · {now_str()}\n以后机器人可以主动给你发消息；想测活就发 /ping。"
    return None


async def prime(
    state: State,
    timeout: float,
    max_age: float,
) -> int:
    """Block until one inbound message refreshes the token, then flush the queue."""
    from wechat_openclaw import OpenClawAPI
    from wechat_openclaw.api import SessionExpiredError
    from wechat_openclaw.models import GetUpdatesRequest, WeChatMessageType

    creds = load_credentials(state)
    if not creds:
        print("还没有扫码登录。先运行：wechat_notify.py login", file=sys.stderr)
        return EXIT_NO_LOGIN

    target = load_target(state)
    if target and max_age > 0:
        age = time.time() - float(target.get("updated_ts") or 0)
        if age <= max_age:
            print(f"令牌还新鲜（{int(age)} 秒前刷新），可以直接发送。")
            await queueing.flush_queue(state)
            return EXIT_OK

    lock = acquire_lock(state)
    if not lock:
        # A daemon owns the poller; wait for it to refresh target.json instead.
        print("监听进程正在运行，等待它刷新会话令牌…（请给微信机器人发一条消息）", flush=True)
        before = float((target or {}).get("updated_ts") or 0)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = load_target(state)
            if current and float(current.get("updated_ts") or 0) > before:
                print(f"✅ 令牌已刷新：{current.get('updated_at')}")
                await queueing.flush_queue(state)
                return EXIT_OK
            await asyncio.sleep(POLL_INTERVAL)
        print("超时：监听进程没有刷新令牌（请在微信里给机器人发一条消息）。", file=sys.stderr)
        return EXIT_NO_SESSION

    api = OpenClawAPI(creds["bot_token"], base_url=client.base_url_of(creds))
    buf = ""
    deadline = time.monotonic() + timeout
    print(f"等待你给微信机器人发一条消息（最多 {int(timeout)} 秒）…", flush=True)
    print("TOKEN_WAITING", flush=True)
    try:
        while time.monotonic() < deadline:
            response = await api.get_updates(GetUpdatesRequest(get_updates_buf=buf))
            if response.get_updates_buf:
                buf = response.get_updates_buf
            for message in response.msgs or []:
                if message.message_type != WeChatMessageType.USER:
                    continue
                text = extract_text(message)
                remember_target(state, message, text)
                print(f"✅ 收到入站消息，令牌已刷新：{text[:40]!r}")
                await queueing.flush_queue(state)
                return EXIT_OK
    except SessionExpiredError:
        print("登录已过期，请重新扫码：wechat_notify.py login --force", file=sys.stderr)
        return EXIT_SESSION_EXPIRED
    finally:
        with contextlib.suppress(Exception):  # best-effort cleanup
            await api.aclose()
        lock.release()

    print("超时：没有收到入站消息。", file=sys.stderr)
    return EXIT_NO_SESSION


async def run_forever(state: State) -> int:
    """Keep polling forever: refresh the token, answer pings, flush the queue."""
    from wechat_openclaw import OpenClawAPI
    from wechat_openclaw.api import SessionExpiredError
    from wechat_openclaw.models import GetUpdatesRequest, WeChatMessageType

    creds = load_credentials(state)
    if not creds:
        print("还没有扫码登录。先运行：wechat_notify.py login", file=sys.stderr)
        return EXIT_NO_LOGIN

    lock = acquire_lock(state)
    if not lock:
        print("已经有一个 run 进程在跑了（state/daemon.lock 被占用）。", file=sys.stderr)
        print("如果要重启，先结束旧进程：Get-Process python | Stop-Process", file=sys.stderr)
        return EXIT_ERROR

    api = OpenClawAPI(creds["bot_token"], base_url=client.base_url_of(creds))
    poll_task: asyncio.Task | None = None
    buf = ""
    started = now_str()
    log(
        state,
        f"开始监听（account_id={mask(creds.get('account_id'))}，网关 {client.base_url_of(creds)}）",
    )
    print("\n👉 现在请在微信里给这个机器人随便发一条消息（例如「在吗」），")
    print("   这样我才能拿到 context_token 主动给你发通知。")
    print("   发 /ping 可以测活。按 Ctrl+C 退出。\n", flush=True)

    if load_target(state):
        log(state, "已有历史会话令牌，先尝试补发离线期间排队的通知")
        await queueing.flush_queue(state)

    heartbeat = {
        "pid": os.getpid(),
        "started_at": started,
        "heartbeat": time.time(),
        "account_id": mask(creds.get("account_id")),
        "queue": len(queueing.pending(state)),
    }
    atomic_write_json(state.daemon_path, heartbeat)

    try:
        while True:
            if poll_task is None:
                poll_task = asyncio.create_task(
                    api.get_updates(GetUpdatesRequest(get_updates_buf=buf))
                )
            done, _ = await asyncio.wait({poll_task}, timeout=1.0)

            if poll_task in done:
                task, poll_task = poll_task, None
                try:
                    response = task.result()
                except SessionExpiredError as exc:
                    log(state, f"登录已过期：{exc}\n请重新扫码：wechat_notify.py login --force")
                    return EXIT_SESSION_EXPIRED
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log(state, f"长轮询出错（{type(exc).__name__}: {exc}），1 秒后重试")
                    await asyncio.sleep(POLL_INTERVAL)
                    response = None

                if response is not None:
                    if response.get_updates_buf:
                        buf = response.get_updates_buf
                    for message in response.msgs or []:
                        if message.message_type != WeChatMessageType.USER:
                            continue
                        text = extract_text(message)
                        first_contact = load_target(state) is None
                        remember_target(state, message, text)
                        log(
                            state,
                            f"收到消息（{mask(message.from_user_id)}）：{text[:60]!r}，令牌已刷新",
                        )
                        reply = _auto_reply(text, first_contact)
                        if reply:
                            try:
                                await client.send_once(state, reply)
                                log(state, "已回复确认消息")
                            except Exception as exc:
                                log(state, f"回复失败：{type(exc).__name__}: {exc}")

            await queueing.flush_queue(state)
            heartbeat["heartbeat"] = time.time()
            heartbeat["queue"] = len(queueing.pending(state))
            atomic_write_json(state.daemon_path, heartbeat)
    except KeyboardInterrupt:
        log(state, "收到 Ctrl+C，退出")
        return EXIT_OK
    finally:
        if poll_task:
            poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await poll_task
        with contextlib.suppress(Exception):  # best-effort cleanup
            await api.aclose()
        lock.release()
        with contextlib.suppress(OSError):
            state.daemon_path.unlink(missing_ok=True)
