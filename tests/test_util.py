"""Tests for the small pure helpers."""

from __future__ import annotations

import time

from wechat_notify.util import age_text, mask, truncate


def test_mask_keeps_short_values_readable():
    assert mask(None) == "(空)"
    assert mask("") == "(空)"
    assert mask("abc") == "ab***"


def test_mask_hides_the_middle_of_long_values():
    masked = mask("demo-bot-1234567890.bot")
    assert masked == "demo****.bot"
    assert "1234567890" not in masked


def test_age_text_buckets():
    now = time.time()
    assert age_text(now - 5) == "5 秒前"
    assert age_text(now - 120) == "2 分钟前"
    assert age_text(now - 7200) == "2 小时前"
    assert age_text(now - 172800) == "2 天前"
    assert age_text(None) == "未知"


def test_truncate_collapses_whitespace():
    assert truncate("a\n\n b\tc", 10) == "a b c"
    assert truncate("0123456789abcdef", 5) == "01234…"
    assert truncate("", 5) == ""
