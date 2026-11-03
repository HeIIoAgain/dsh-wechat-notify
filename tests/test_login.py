"""QR rendering and login bookkeeping (network-free)."""

from __future__ import annotations

import base64
from pathlib import Path

from wechat_notify.login import render_qr_image

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
# 1x1 transparent PNG
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def test_data_uri_is_written_verbatim(tmp_path: Path):
    out = tmp_path / "qr.png"
    content = "data:image/png;base64," + base64.b64encode(TINY_PNG).decode()
    message = render_qr_image(content, out)

    assert out.read_bytes() == TINY_PNG
    assert "PNG 已生成" in message


def test_http_url_is_rendered_as_qr(tmp_path: Path):
    out = tmp_path / "qr.png"
    message = render_qr_image("https://liteapp.weixin.qq.com/q/demo?x=1", out)

    assert out.read_bytes().startswith(PNG_MAGIC)
    assert "二维码内容" in message
    assert out.stat().st_size > 100


def test_raw_base64_png_is_detected(tmp_path: Path):
    out = tmp_path / "qr.png"
    render_qr_image(base64.b64encode(TINY_PNG).decode(), out)
    assert out.read_bytes() == TINY_PNG


def test_non_image_payload_falls_back_to_text_file(tmp_path: Path):
    out = tmp_path / "qr.txt"
    message = render_qr_image("not-a-qr-payload", out)

    assert out.read_text(encoding="utf-8") == "not-a-qr-payload"
    assert "二维码内容是文本" in message
