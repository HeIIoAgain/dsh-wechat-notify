"""Persistent state: JSON credentials, queue, daemon heartbeat and file lock.

Everything the tool remembers lives under one directory (``State.dir``):

==================  =========================================================
``credentials.json``  ``bot_token`` / ``account_id`` / gateway from ``login``
``target.json``       ``user_id`` + ``context_token`` from the latest inbound message
``queue/``            notifications that could not be sent yet (plus attachments)
``sent/``             copies of queue items after a successful send
``daemon.json``       heartbeat written by ``run``
``daemon.lock``       single-instance lock held by ``run``
``qr.png``            rendered login QR code
``notify.log``        append-only activity log
==================  =========================================================

The directory is resolved in this order: ``--state-dir``, then
``$WECHAT_NOTIFY_STATE_DIR``, then ``<repo>/scripts/state`` when running from a
source checkout or skill bundle, then ``~/.wechat-notify/state``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .config import STATE_ENV


def resolve_state_dir(explicit: str | Path | None = None) -> Path:
    """Return the state directory, honouring CLI flag, env var and layout."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get(STATE_ENV)
    if env:
        return Path(env).expanduser().resolve()

    package_dir = Path(__file__).resolve().parent  # .../src/wechat_notify
    repo_root = package_dir.parent.parent  # .../<repo>
    if (repo_root / "SKILL.md").is_file():
        return (repo_root / "scripts" / "state").resolve()
    return (Path.home() / ".wechat-notify" / "state").resolve()


@dataclass(frozen=True)
class State:
    """Paths inside one state directory.

    The object is immutable on purpose: paths are derived properties, so tests can
    point the CLI at a temporary directory without patching module globals.
    """

    dir: Path

    @classmethod
    def at(cls, path: str | Path | None = None) -> State:
        return cls(resolve_state_dir(path))

    # -- well-known files ---------------------------------------------------
    @property
    def credentials_path(self) -> Path:
        return self.dir / "credentials.json"

    @property
    def target_path(self) -> Path:
        return self.dir / "target.json"

    @property
    def queue_dir(self) -> Path:
        return self.dir / "queue"

    @property
    def sent_dir(self) -> Path:
        return self.dir / "sent"

    @property
    def daemon_path(self) -> Path:
        return self.dir / "daemon.json"

    @property
    def lock_path(self) -> Path:
        return self.dir / "daemon.lock"

    @property
    def qr_path(self) -> Path:
        return self.dir / "qr.png"

    @property
    def log_path(self) -> Path:
        return self.dir / "notify.log"

    def ensure(self) -> State:
        """Create the directory (idempotent)."""
        self.dir.mkdir(parents=True, exist_ok=True)
        return self


def read_json(path: Path) -> dict | None:
    """Read a JSON object, returning ``None`` for missing or corrupt files."""
    try:
        # utf-8-sig tolerates files re-saved by Notepad (BOM) without breaking JSON parsing.
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def atomic_write_json(path: Path, obj: dict) -> None:
    """Write JSON via a temp file + ``os.replace`` so readers never see halves."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_credentials(state: State) -> dict | None:
    """Return credentials when they contain a ``bot_token``."""
    data = read_json(state.credentials_path)
    if not data or not data.get("bot_token"):
        return None
    return data


def load_target(state: State) -> dict | None:
    """Return the cached ``user_id`` + ``context_token`` pair when complete."""
    data = read_json(state.target_path)
    if not data or not data.get("context_token") or not data.get("user_id"):
        return None
    return data


class SingleInstanceLock:
    """Cross-platform single-instance lock for the long-running ``run`` loop.

    Windows uses an ``msvcrt`` byte lock (released by the OS if the process dies);
    other platforms use an ``fcntl`` lock on POSIX where available and fall back to
    a PID probe elsewhere.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle = None
        self._locked = False

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._handle = self.path.open("a+", encoding="utf-8")
        except OSError:
            return False
        try:
            import msvcrt  # Windows

            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            self._locked = True
            return True
        except ImportError:
            pass
        except OSError:
            self.release()
            return False
        try:
            import fcntl  # POSIX

            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._locked = True
            return True
        except (ImportError, OSError):
            self.release()
            return False

    def release(self) -> None:
        if self._handle is None:
            return
        if self._locked:
            try:
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            except (ImportError, OSError):
                try:
                    import fcntl

                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
                except (ImportError, OSError):
                    pass
        self._handle.close()
        self._handle = None
        self._locked = False

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, *exc_info: object) -> None:
        self.release()


def acquire_lock(state: State) -> SingleInstanceLock | None:
    """Return a held lock, or ``None`` when another ``run`` already owns it."""
    lock = SingleInstanceLock(state.lock_path)
    return lock if lock.acquire() else None
