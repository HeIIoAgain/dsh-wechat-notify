"""Offline queue: keep a notification until a ``context_token`` exists again.

The WeChat channel cannot cold-start an outbound message, so ``send`` may fail with
:class:`NoSessionError`. Instead of dropping the content we persist it (attachments
included) and let the next ``prime``/``run`` flush the backlog in order.
"""

from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

from . import client
from .errors import NoSessionError
from .state import State, atomic_write_json, read_json
from .util import log, now_str

# Queue files are named "<13-digit ms>-<6-digit sequence>-<random>.json" and flushed
# in filename order, so the name has to be strictly increasing. A bare millisecond
# stamp is not enough: two enqueues inside the same millisecond would only differ by
# the random suffix, and `pending()` would then hand back an arbitrary order.
_last_ms = 0
_sequence = 0


def _next_queue_path(queue_dir: Path) -> Path:
    """Return a queue filename that sorts strictly after everything already queued.

    The name drives flush order, so it must not go backwards even if the system
    clock does (NTP step, timezone-less VM restore), and it must stay unique even
    when two processes land in the same millisecond.
    """
    global _last_ms, _sequence
    ms = int(time.time() * 1000)
    # Never sort behind a file that is already in the backlog.
    for existing in queue_dir.glob("*.json"):
        head = existing.name.split("-", 1)[0]
        if head.isdigit() and int(head) > ms:
            ms = int(head)
    if ms > _last_ms:
        _last_ms, _sequence = ms, 0
    else:
        # Same millisecond, or the clock moved backwards: keep the ordering.
        _sequence += 1
    while True:
        path = queue_dir / f"{_last_ms:013d}-{_sequence:06d}-{uuid.uuid4().hex[:6]}.json"
        if not path.exists():
            return path
        _sequence += 1


def enqueue(
    state: State,
    text: str | None,
    reason: str,
    image: str | Path | None = None,
    attach: str | Path | None = None,
) -> Path:
    """Persist one queued notification and return its file path.

    Attachments are copied into the queue so later edits or deletions of the source
    file cannot corrupt the backlog.
    """
    state.queue_dir.mkdir(parents=True, exist_ok=True)
    path = _next_queue_path(state.queue_dir)
    record: dict = {"text": text or "", "created_at": now_str(), "reason": reason}

    attachments = state.queue_dir / "attachments"
    for key, source in (("image", image), ("attach", attach)):
        if not source:
            continue
        source_path = Path(source)
        attachments.mkdir(parents=True, exist_ok=True)
        destination = attachments / f"{uuid.uuid4().hex[:8]}-{source_path.name}"
        shutil.copy2(source_path, destination)
        record[key] = str(destination)

    atomic_write_json(path, record)
    return path


def pending(state: State) -> list[Path]:
    """Queued notification files, oldest first (the filename starts with a timestamp)."""
    if not state.queue_dir.is_dir():
        return []
    return sorted(state.queue_dir.glob("*.json"))


async def flush_queue(state: State) -> int:
    """Send queued notifications in order; return how many were delivered.

    A failure keeps the remaining queue intact and stops the flush, because a later
    item is almost always useless without the earlier context.
    """
    sent = 0
    for path in pending(state):
        item = read_json(path) or {}
        text = (item.get("text") or "").strip()
        image = item.get("image")
        attach = item.get("attach")
        if not text and not image and not attach:
            path.unlink(missing_ok=True)
            continue

        for value in (image, attach):
            if value and not Path(value).is_file():
                log(state, f"队列附件丢失：{value}（{path.name}），跳过")
                image = None if image == value else image
                attach = None if attach == value else attach
        try:
            await client.send_once(state, text or None, image=image, attach=attach)
        except NoSessionError as exc:
            log(state, f"补发跳过（无会话令牌）：{exc}")
            break
        except Exception as exc:
            log(state, f"补发失败（{type(exc).__name__}: {exc}），队列保留：{path.name}")
            break

        state.sent_dir.mkdir(parents=True, exist_ok=True)
        item["sent_at"] = now_str()
        atomic_write_json(state.sent_dir / path.name, item)
        path.unlink(missing_ok=True)
        sent += 1
        log(state, f"已补发排队内容：{path.name}")
    return sent
