"""Repository hygiene check for CI.

Three classes of mistakes are cheap to make and expensive to publish:

1. a real bot / context token committed by accident,
2. an absolute personal path baked into code or docs,
3. runtime state (credentials, queue, logs) tracked by git.

Run it locally with ``python tools/check_repo.py`` before opening a pull request.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    "build",
    "dist",
    "state",
}

TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ps1",
    ".cmd",
    ".sh",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
    ".json",
    ".cfg",
    ".ini",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
}

#: Conventional placeholder names that may appear in docs and tests.
PLACEHOLDERS = {"<", "me", "you", "user", "example", "demo", "name", "someone"}

SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r'"(bot_token|context_token)"\s*:\s*"[^"<>\s]{16,}"'),
        "looks like a real token in JSON",
    ),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "GitHub fine-grained token"),
    (re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"), "API key"),
]

PATH_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?i)\b[a-z]:[\\/](?:users|studyprogram|toolprograms|helperfolder)[\\/]([^\\/\s]*)"
        ),
        "absolute personal path",
    ),
    (re.compile(r"/home/([^/\s]+)/"), "absolute personal path"),
    (re.compile(r"/Users/([^/\s]+)/"), "absolute personal path"),
]


def is_placeholder(name: str) -> bool:
    return name.lower() in PLACEHOLDERS or name.startswith("<")


LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")


def check_markdown_links(path: Path) -> list[str]:
    """Relative links in docs rot silently; CI should catch that."""
    problems: list[str] = []
    relative = path.relative_to(ROOT).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    for target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        clean = target.split("#", 1)[0]
        if not clean:
            continue
        if not (path.parent / clean).resolve().exists():
            problems.append(f"{relative}: broken relative link -> {target}")
    return problems


FORBIDDEN_FILES = {
    "scripts/state/credentials.json",
    "scripts/state/target.json",
    "scripts/state/queue",
    "state/credentials.json",
    "state/target.json",
}


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts[:-1]):
            continue
        if path == Path(__file__).resolve():
            continue  # this file contains the patterns themselves
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {".gitignore", ".gitattributes"}:
            files.append(path)
    return sorted(files)


def check_file(path: Path) -> list[str]:
    problems: list[str] = []
    relative = path.relative_to(ROOT).as_posix()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:  # pragma: no cover - unreadable file
        return [f"{relative}: cannot read ({exc})"]

    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(line):
                problems.append(f"{relative}:{line_number}: {label}")
        for pattern, label in PATH_PATTERNS:
            match = pattern.search(line)
            if match and not is_placeholder(match.group(1)):
                problems.append(f"{relative}:{line_number}: {label} -> {match.group(0)}")
    return problems


def main() -> int:
    problems: list[str] = []

    for forbidden in sorted(FORBIDDEN_FILES):
        if (ROOT / forbidden).exists():
            problems.append(f"{forbidden}: runtime state must not be tracked")

    if not (ROOT / "LICENSE").is_file():
        problems.append("LICENSE: missing")
    if not (ROOT / "SKILL.md").is_file():
        problems.append("SKILL.md: missing (the DSH skill would break)")

    for path in iter_text_files():
        problems.extend(check_file(path))
        if path.suffix.lower() == ".md":
            problems.extend(check_markdown_links(path))

    if problems:
        print("Repository hygiene check failed:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"Repository hygiene check passed ({len(iter_text_files())} files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
