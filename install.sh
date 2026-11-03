#!/usr/bin/env bash
#
# Install the wechat-notify skill for DeepSeek Harness (macOS / Linux).
#
# Usage:
#   ./install.sh                        # install into ${DSH_HOME:-~/.dsh}/skills/wechat-notify
#   ./install.sh --dest ~/skills/wechat-notify
#   ./install.sh --no-deps --force
#
set -euo pipefail

SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST=""
PYTHON=""
NO_DEPS="0"
FORCE="0"

usage() {
  sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dest) DST="${2:?--dest needs a value}"; shift 2 ;;
    --python) PYTHON="${2:?--python needs a value}"; shift 2 ;;
    --no-deps) NO_DEPS="1"; shift ;;
    --force) FORCE="1"; shift ;;
    -h|--help) usage 0 ;;
    *) echo "unknown argument: $1" >&2; usage 2 ;;
  esac
done

if [ -z "$DST" ]; then
  DST="${DSH_HOME:-$HOME/.dsh}/skills/wechat-notify"
fi
DST="$(cd "$(dirname "$DST")" 2>/dev/null && pwd)/$(basename "$DST")" || DST="$DST"

echo "== wechat-notify installer =="
echo "source : $SOURCE"
echo "target : $DST"

if [ -d "$DST" ] && [ "$FORCE" != "1" ]; then
  echo "目标已存在：$DST" >&2
  echo "加 --force 覆盖（scripts/state 里的凭据和队列会保留）。" >&2
  exit 1
fi

if [ -z "$PYTHON" ]; then
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then PYTHON="$(command -v "$candidate")"; break; fi
  done
fi
if [ -z "$PYTHON" ]; then
  echo "找不到 python3，请安装 Python 3.10+，或用 --python 指定解释器。" >&2
  exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "需要 Python >= 3.10，当前是 $("$PYTHON" -c 'import sys; print(sys.version.split()[0])')" >&2
  exit 1
fi
echo "python : $PYTHON ($("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])'))"

if [ "$NO_DEPS" = "0" ]; then
  echo "deps   : 安装 wechat-openclaw-sdk / qrcode …"
  "$PYTHON" -m pip install --disable-pip-version-check -r "$SOURCE/requirements.txt"
else
  echo "deps   : 已跳过（--no-deps），记得自己装 requirements.txt"
fi

mkdir -p "$DST"
cp -f "$SOURCE/SKILL.md" "$SOURCE/README.md" "$SOURCE/LICENSE" "$SOURCE/requirements.txt" "$DST/"
# cp -R merges into an existing tree, so scripts/state (credentials) survives upgrades.
for directory in src scripts plugin; do
  mkdir -p "$DST/$directory"
  cp -R "$SOURCE/$directory/." "$DST/$directory/"
done

ENTRY="$DST/scripts/wechat_notify.py"
echo
echo "已安装：$DST"
echo "版本  ：$("$PYTHON" "$ENTRY" --version)"
echo
echo "下一步："
echo "  1) 扫码登录：\"$PYTHON\" \"$ENTRY\" login"
echo "  2) 让机器人拿到会话令牌：在微信里给它发一条消息，或先跑 prime 等着"
echo "     \"$PYTHON\" \"$ENTRY\" prime --timeout 180"
echo "  3) 发一条测试：\"$PYTHON\" \"$ENTRY\" send \"测试消息\""
echo "  4) 看状态：\"$PYTHON\" \"$ENTRY\" status"
echo
echo "重启 DSH（或新开一个会话）后，技能列表里会出现 wechat-notify。"
echo "想让每轮对话结束自动推微信，见 plugin/README.md（默认关闭）。"
