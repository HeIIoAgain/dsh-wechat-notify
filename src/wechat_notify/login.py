"""QR-code login against the iLink bot gateway.

The gateway hands out a QR code, the user confirms it in WeChat, and we persist the
resulting ``bot_token`` (valid for weeks) in ``credentials.json``. A ``bot_token`` is
a bot identity: treat the file like a password.
"""

from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path

from .config import (
    BOT_TYPE,
    DEFAULT_BASE_URL,
    DEFAULT_LOGIN_TIMEOUT,
    POLL_INTERVAL,
    QR_CODE_LIFETIME,
)
from .state import State, atomic_write_json
from .util import log, mask, now_str

CLIENT_VERSION_HEADER = "iLink-App-ClientVersion"


async def fetch_qrcode(http, base: str) -> dict:
    """Ask the gateway for a fresh QR code payload."""
    response = await http.get(f"{base}/ilink/bot/get_bot_qrcode", params={"bot_type": BOT_TYPE})
    response.raise_for_status()
    body = response.json()
    if not body.get("qrcode"):
        raise RuntimeError("网关没有返回二维码，稍后再试")
    return body


async def qr_status(http, base: str, qrcode: str) -> dict:
    """Poll the scan state of one QR code; network hiccups read as ``wait``."""
    try:
        response = await http.get(
            f"{base}/ilink/bot/get_qrcode_status",
            params={"qrcode": qrcode},
            headers={CLIENT_VERSION_HEADER: "1"},
        )
        return response.json() if response.text else {}
    except Exception:
        return {}


def render_qr_image(content: str, out_path: Path) -> str:
    """Render the gateway payload into ``out_path`` and describe how to open it.

    The gateway may return a data URI, a plain ``http(s)`` URL, raw base64 PNG bytes,
    or (worst case) text. Only the URL case needs ``qrcode``.
    """
    content = (content or "").strip()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if content.startswith("data:image"):
        out_path.write_bytes(base64.b64decode(content.split(",", 1)[1]))
        return f"PNG 已生成：{out_path}"

    if content.startswith("http"):
        import qrcode

        qrcode.make(content).save(out_path)
        return f"PNG 已生成：{out_path}\n二维码内容（也可直接在微信里打开）：{content}"

    try:
        raw = base64.b64decode(content)
        if raw[:8] == b"\x89PNG\r\n\x1a\n":
            out_path.write_bytes(raw)
            return f"PNG 已生成：{out_path}"
    except Exception:
        pass

    out_path.write_text(content, encoding="utf-8")
    return f"二维码内容是文本，已写入：{out_path}\n{content}"


async def qr_login(
    state: State,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_LOGIN_TIMEOUT,
) -> dict:
    """Run the scan-and-confirm loop and save credentials; raises on timeout."""
    import httpx

    base = base_url.rstrip("/")
    deadline = time.monotonic() + max(timeout, 30.0)

    async with httpx.AsyncClient(follow_redirects=True, timeout=35.0) as http:
        while time.monotonic() < deadline:
            body = await fetch_qrcode(http, base)
            qrcode = body["qrcode"]
            info = render_qr_image(body.get("qrcode_img_content") or qrcode, state.qr_path)
            log(state, f"请用微信扫码登录：\n{info}")
            log(state, f"QR_PATH={state.qr_path}")
            print("扫码后请在手机上点确认；二维码过期会自动刷新。", flush=True)

            started = time.monotonic()
            scanned = False
            while time.monotonic() - started < QR_CODE_LIFETIME and time.monotonic() < deadline:
                status_body = await qr_status(http, base, qrcode)
                status = status_body.get("status", "wait")

                if status == "confirmed":
                    bot_id = status_body.get("ilink_bot_id")
                    if not bot_id:
                        raise RuntimeError("登录已确认但网关没有返回 ilink_bot_id")
                    creds = {
                        "bot_token": status_body.get("bot_token") or "",
                        "account_id": bot_id,
                        "base_url": status_body.get("baseurl") or base,
                        "user_id": status_body.get("ilink_user_id") or "",
                        "logged_in_at": now_str(),
                    }
                    atomic_write_json(state.credentials_path, creds)
                    log(state, f"登录成功，account_id={mask(bot_id)}")
                    return creds

                if status == "scaned":
                    if not scanned:
                        scanned = True
                        log(state, "已扫码，等待手机上确认…")
                elif status == "expired":
                    log(state, "二维码过期，正在刷新…")
                    break

                await asyncio.sleep(POLL_INTERVAL)

        raise RuntimeError("扫码登录超时，请重跑 login")
