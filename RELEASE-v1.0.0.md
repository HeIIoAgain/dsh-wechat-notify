# v1.0.0 — 首个公开版本

> **English summary:** On-demand WeChat notifications (text, screenshots, files) for
> DeepSeek Harness (DSH) agents and plain scripts, over the WeChat iLink OpenClaw bot
> channel. Nothing is ever pushed on its own — only when you explicitly ask.

把文字 / 图片 / 文件按需发到**你自己**微信的 DSH 技能 + 命令行工具。

## 它解决什么问题

DSH 在电脑上跑长任务时，人不在跟前。你希望手机上收到结果，而不是回电脑前才发现跑完了。
这个工具把「我要的结果」推到微信：文字、截图、文件都行，一条命令，或者让 Agent 自己调技能。

## 亮点

- **三种触发方式**：DSH 技能（Agent 判断该发）、CLI（你自己用）、可选 Host 插件（每轮结束自动推，默认关闭）
- **默认不主动发送**：只有你明确说「发我微信」才会发，不会变成推送轰炸
- **失败不丢内容**：没有 `context_token` 或网关抽风时自动进队列，下次 `prime` / `run` 补发
- **退出码即契约**：`0/1/2/3/4` 语义明确，脚本和插件都能分支处理
- **凭据只在本机**：扫码得到的 `bot_token` 存 `state/credentials.json`，不进仓库、不进日志（日志里只有掩码）
- **零配置安装**：`install.ps1` / `install.sh` 自动定位 `$DSH_HOME/skills` 并装依赖
- **跨平台**：Windows / macOS / Linux；截图脚本仅 Windows（GDI，无输入事件注入）

## 通道的硬边界（来自协议，不是实现偷懒）

- 只能发给**扫码登录的那个微信号**（单聊；群聊未验证）
- **不能冷启动主动发消息**：每条出站消息都要带 `context_token`，而它只由入站消息下发。
  所以发送前需要「最近 30 分钟内你给机器人发过一条消息」（`prime`），或者让 `run` 常驻收消息
- 有频控：请合并内容，别刷屏

## 安装

作为 DSH 技能（推荐）：

```powershell
git clone https://github.com/HeIIoAgain/dsh-wechat-notify.git
cd dsh-wechat-notify
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1     # Windows
```

```bash
bash install.sh                                                       # macOS / Linux
```

装到 `$DSH_HOME/skills/wechat-notify`，重启 DSH 或新开会话后技能列表里出现 `wechat-notify`。

只当命令行工具：

```bash
python -m pip install "git+https://github.com/HeIIoAgain/dsh-wechat-notify.git"
wechat-notify --version
```

要求 Python ≥ 3.10；Node ≥ 18 仅用于可选 Host 插件。

## 首条消息

```powershell
python "<技能目录>\scripts\wechat_notify.py" login         # 扫码
python "<技能目录>\scripts\wechat_notify.py" prime --timeout 180
#   这时在微信里给机器人随便发一条，例如 /ping
python "<技能目录>\scripts\wechat_notify.py" send "第一条测试"
```

嫌弃麻烦就让 `run` 常驻：收到消息即刷新令牌，并自动补发队列。

## 退出码

| 码 | 含义 | 建议动作 |
|---|---|---|
| `0` | 成功 | — |
| `1` | 其他错误（网络 / 文件 / SDK） | 看 stderr；内容已排队 |
| `2` | 还没登录 | `login` |
| `3` | 没有可用 `context_token` | 内容已排队；`prime` + 在微信里发一句 |
| `4` | `bot_token` 过期（`errcode -14`） | `login --force` |

## 安全

- `state/credentials.json`（`bot_token`）与 `state/target.json`（`context_token`）是本机密钥，
  等同机器人身份；不要提交、不要贴聊天记录、不要放共享目录
- 日志里的 `account_id` / `user_id` 都是掩码，但**正文内容会写进 `notify.log`**
- 数据经腾讯 iLink 网关（`https://ilinkai.weixin.qq.com`）与 CDN 传输，这是渠道本身的路径

## 免责声明

非官方项目，与腾讯 / 微信无关联。使用微信机器人渠道请遵守微信相关服务条款；账号风险自负。

---

**Full Changelog**: https://github.com/HeIIoAgain/dsh-wechat-notify/blob/main/CHANGELOG.md
