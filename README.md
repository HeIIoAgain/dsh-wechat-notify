# dsh-wechat-notify

把文字 / 图片 / 文件按需发到**你自己**微信的 DSH 技能 + 命令行工具，走微信 iLink OpenClaw
机器人渠道。默认不主动发送：只有你明确说"发我微信"才会发。

[![CI](https://github.com/HeIIoAgain/dsh-wechat-notify/actions/workflows/ci.yml/badge.svg)](https://github.com/HeIIoAgain/dsh-wechat-notify/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Node](https://img.shields.io/badge/node-%E2%89%A518%20%28plugin%20only%29-green.svg)](#可选插件每轮结束自动推)

[English](README.en.md) | 简体中文

---

## 它解决什么问题

DSH 在电脑上跑长任务时，人不在跟前。你希望手机上收到结果，而不是回电脑前才发现跑完了。
这个工具把「我要的结果」推到微信：文字、截图、文件都行，一条命令，或者让 Agent 自己调技能。

它的**边界**（来自渠道协议，不是实现懒惰）：

- 只能发给**扫码登录的那个微信号**（单聊；群聊未验证）；
- **不能冷启动主动发消息**：每条出站消息都要带 `context_token`，而它只由入站消息下发。
  所以发送前需要「最近 30 分钟内你给机器人发过一条消息」（`prime`），或者让 `run` 常驻收消息；
- 有频控：请合并内容，别刷屏。

## 特性

- **三种触发方式**：DSH 技能（Agent 自己判断该发）、CLI（你自己用）、可选 Host 插件（每轮结束自动推）
- **文字 / 图片 / 文件**：一张截图、一份 PDF 报告，直接发
- **失败不丢内容**：没有令牌 / 网关抽风时自动进队列，下次 `prime` 或 `run` 补发
- **退出码即契约**：`0/1/2/3/4` 语义明确，脚本和插件都能分支处理
- **零配置安装**：`install.ps1` / `install.sh` 自动定位 `$DSH_HOME/skills` 并装依赖
- **凭据只在本机**：扫码得到的 `bot_token` 存 `state/credentials.json`，不进仓库、不进日志（日志里只有掩码）
- **跨平台**：Windows / macOS / Linux；截图脚本仅 Windows（GDI，无输入事件注入）

## 安装

### 方式一：作为 DSH 技能（推荐）

```powershell
# Windows
git clone https://github.com/HeIIoAgain/dsh-wechat-notify.git
cd dsh-wechat-notify
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

```bash
# macOS / Linux
git clone https://github.com/HeIIoAgain/dsh-wechat-notify.git
cd dsh-wechat-notify
bash install.sh
```

装到 `$DSH_HOME/skills/wechat-notify`（默认 `~/.dsh/skills/wechat-notify`），重启 DSH 或新开一个
会话后，技能列表里会出现 `wechat-notify`。

安装器参数：`-Dest` / `--dest`（目标目录）、`-Python` / `--python`（解释器）、`-NoDeps` /
`--no-deps`（跳过 pip）、`-Force` / `--force`（覆盖，保留 `scripts/state`）。

### 方式二：只当命令行工具

```bash
python -m pip install "git+https://github.com/HeIIoAgain/dsh-wechat-notify.git"
wechat-notify --version
```

状态目录默认为 `~/.wechat-notify/state`，可用 `--state-dir` 或 `WECHAT_NOTIFY_STATE_DIR` 改。

### 方式三：源码直接跑（不装）

```bash
python scripts/wechat_notify.py --version     # src/ 由入口脚本自动加入 sys.path
```

要求：Python ≥ 3.10，Node ≥ 18 仅用于可选的 Host 插件（`node --test plugin/test`）。

## 首次使用（每台机器一次）

```powershell
python "<技能目录>\scripts\wechat_notify.py" login
```

终端会打印二维码路径（`scripts\state\qr.png`）和一段可点击的链接。用微信扫码 → 手机上点确认 →
凭据落盘，打印 `account_id`。之后不用再扫（除非报 `errcode -14`）。

> `credentials.json` 等同机器人身份：能看就别转贴。仓库 `.gitignore` 已经排除了整个 `state/`。

## 发第一条

这个渠道拿不到 `context_token` 就发不了，而它只由入站消息下发。所以：

```powershell
# 1) 起一个等待进程（180 秒）
python "<技能目录>\scripts\wechat_notify.py" prime --timeout 180

# 2) 这时在微信里给机器人随便发一条，例如 /ping

# 3) prime 返回 0 后，直接发
python "<技能目录>\scripts\wechat_notify.py" send "第一条测试"
```

嫌麻烦就让 `run` 常驻（收到消息即刷新令牌，并自动补发队列）：

```powershell
python "<技能目录>\scripts\wechat_notify.py" run
```

## 常用命令

| 命令 | 作用 |
|---|---|
| `login [--force] [--base-url URL]` | 扫码登录，保存 `bot_token` |
| `send "正文"` | 发文字 |
| `send --title "标题" "正文"` | 带标题（会变成 `【标题】\n正文`） |
| `send --image shot.png` | 发图片 |
| `send --attach report.pdf` | 发文件 |
| `send -` | 从 stdin 读正文（`"hi" \| wechat-notify send -`） |
| `send --file body.txt` | 从 UTF-8 文本文件读正文（避免命令行中文乱码） |
| `prime [--timeout 180] [--max-age 1800]` | 等一条入站消息刷新 `context_token`，并补发队列 |
| `run` | 前台常驻：收消息、刷新令牌、补发队列、回 `/ping` |
| `status [--json]` | 看登录 / 令牌年龄 / 常驻进程 / 队列 |
| `--state-dir DIR` | 指定状态目录（可放在子命令前或后） |
| `--version` | 版本号 |

不带子命令直接给文字也等价于 `send`：

```powershell
wechat-notify 你好     # == wechat-notify send 你好
```

### 退出码

| 码 | 含义 | 建议动作 |
|---|---|---|
| `0` | 成功 | — |
| `1` | 其他错误（网络、文件、SDK 异常） | 看 stderr；内容已排队 |
| `2` | 还没登录 | `login` |
| `3` | 没有可用 `context_token` | 内容已排队；`prime` + 在微信里发一句 |
| `4` | `bot_token` 过期（`errcode -14`） | `login --force` 重新扫码 |

## 在 DSH 里怎么用

技能（`SKILL.md`）里写好了触发边界：只有你说"发我微信""把截图发我微信"这类话才会发，
任务跑完不会自己推。Agent 会先 `status`，再 `send`；遇到退出码 3 会 `prime` 并提示你在微信里发一句。

## 可选插件：每轮结束自动推

`plugin/index.js` 是零依赖的 DSH Host 插件，监听 `turn/end`，每轮结束 `spawn` 一次 `send`。
**默认关闭**，开启方式与全部配置项见 [plugin/README.md](plugin/README.md)。建议 `minTurnMs: 15000`
以上，否则会很吵。

## 截图（Windows）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<技能目录>\scripts\screenshot.ps1" -Out "$env:TEMP\shot.png"
wechat-notify send --image "$env:TEMP\shot.png"
```

`-Mode window -WindowTitle "…" ` 只抓某个窗口。实现走 GDI `BitBlt` / `PrintWindow`，
**不调用 `SendInput` / `SendKeys`，不移动光标，不抢焦点**（脚本自己会打印 idle 计数与光标位置自证）。
截不到的东西：DRM 内容、UAC 安全桌面、锁屏。

## 安全

- `state/credentials.json`（`bot_token`）与 `state/target.json`（`context_token`）是本机密钥，
  等同机器人身份；不要提交、不要贴聊天记录、不要放共享目录。
- 日志里的 `account_id` / `user_id` 都是掩码（`demo****.bot`），但**正文内容会写进 `notify.log`**，
  介意就别发敏感内容，或者把日志目录放到加密盘。
- 数据会经腾讯 iLink 网关（`https://ilinkai.weixin.qq.com`）与 CDN 传输；这是渠道本身的路径。
- 详见 [SECURITY.md](SECURITY.md)。

## 目录结构

```
.
├─ SKILL.md                  DSH 技能定义（Agent 读这个）
├─ src/wechat_notify/        Python 包（CLI + 状态 + 队列 + 登录 + 常驻）
├─ scripts/
│  ├─ wechat_notify.py       兼容入口（SKILL.md 与插件调用它）
│  ├─ wechat-notify.cmd      Windows 启动器
│  └─ screenshot.ps1         Windows 无输入事件截屏
├─ plugin/                   可选 DSH Host 插件（每轮推送）
├─ tests/                    pytest（离线，不碰真实凭据）
├─ docs/protocol.md          协议与生命周期说明
├─ install.ps1 / install.sh  安装器
└─ tools/check_repo.py       CI 仓库卫生检查（密钥 / 绝对路径）
```

## 开发

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
node --test plugin/test/index.test.mjs     # Node ≥ 18
```

测试全部离线：SDK 客户端与网络调用都被替换，状态目录指向 `tmp_path`，不会碰你的真实凭据。
细节见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 故障排查

| 现象 | 原因 / 处理 |
|---|---|
| `退出码 3` / `prepare failed` | 令牌过期：`prime` + 在微信里发一句；队列会自动补发 |
| `退出码 4` / `errcode -14` | `bot_token` 过期：`login --force` |
| 发了但手机没通知 | 微信里能看到 = 已送到；检查勿扰 / 该会话"消息免打扰" / 微信通知权限 |
| `ModuleNotFoundError: wechat_openclaw` | 依赖没装：`pip install -r requirements.txt` |
| 中文成乱码 | 用 `send --file body.txt`（UTF-8 文件）而不是命令行参数 |
| 插件不生效 | 看 `plugin.log`；确认 patch 里 `enabled: true` 且 `scriptPath` 存在 |

## 免责声明

非官方项目，与腾讯 / 微信无关联。使用微信机器人渠道请遵守微信相关服务条款；账号风险自负。

## License

[MIT](LICENSE)
