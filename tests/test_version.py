"""Version numbers must not drift between the package and the packaging metadata."""

from __future__ import annotations

import re
from pathlib import Path

import wechat_notify

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_version_matches_package():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert match, "pyproject.toml has no static version"
    assert match.group(1) == wechat_notify.__version__


def test_changelog_documents_the_current_version():
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{wechat_notify.__version__}]" in changelog


def test_requirements_mirror_the_runtime_dependencies():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")

    block = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)^\]", pyproject)
    assert block, "pyproject.toml has no dependencies list"

    declared = re.findall(r'"([^"]+)"', block.group(1))
    expected = {"wechat-openclaw-sdk", "qrcode"}

    assert len(declared) == 2
    assert {re.split(r"[<>=!\[]", dep)[0] for dep in declared} == expected
    for name in expected:
        assert name in requirements
