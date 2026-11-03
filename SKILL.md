---
name: wechat-notify
description: 按需把文字/图片/文件发到用户本人的微信（微信 iLink OpenClaw 机器人渠道）。仅在用户明确要求时使用，例如"发我微信""微信通知我""推到我微信""把结果/截图发我微信""微信上说一声"。默认绝不主动发送，不要拿它做任务完成后的自动通知。
---

# 微信通知（按需发送）

**铁律**

1. **只有用户明确要求才发**。任务跑完、命令结束、报错、定时到点，都不主动发。
2. 一次对话里能合并就合并成一条，别刷屏（微信有频控）。
3. 发完要如实告诉用户"发了什么 / 成功没有"，不许假装发过。
4. 按纯文本考虑：微信不渲染 Markdown，只有 `**粗体**` / `__粗体__` 原生生效。

## 位置与首次准备

- 主程序：`<S>/scripts/wechat_notify.py`（`wechat-notify` 命令等价，需 `pip install .`）
- `<S>` = **本技能目录**（加载技能时给出的 Base directory；没给就用本 SKILL.md 所在目录）
- 运行时状态（含密钥）：`<S>/scripts/state/` —— `credentials.json`（bot_token）、`target.json`（context_token）、`queue/`（待补发）、`notify.log`
- 解释器：Windows 用 `python`（或 `py -3`），macOS/Linux 用 `python3`；下文统一写 `python`

**首次使用**（每台机器一次）：先装依赖，再扫码登录。

```powershell
python -m pip install -r "<S>/requirements.txt"
python "<S>/scripts/wechat_notify.py" login      # 二维码在 <S>/scripts/state/qr.png，用微信扫
```

登录成功后会打印 `account_id`；凭据存 `state/credentials.json`，之后不用再扫（除非报 errcode -14）。

## 标准流程

1. **看状态**：`python "<S>/scripts/wechat_notify.py" status`（加 `--json` 可机器读）
   - 登录 ✅ → 继续；登录 ❌ → 让用户扫码登录（见上）。
2. **发送**（按需选一种，可组合）：

   ```powershell
   python "<S>/scripts/wechat_notify.py" send "正文"
   python "<S>/scripts/wechat_notify.py" send --title "标题" "正文"
   python "<S>/scripts/wechat_notify.py" send --image "E:\path\shot.png"      # 图片
   python "<S>/scripts/wechat_notify.py" send --attach "E:\path\report.pdf"   # 文件
   "正文" | python "<S>/scripts/wechat_notify.py" send -                      # stdin
   ```

3. **读退出码**：`0` 成功；`2` 未登录；`3` 没有可用会话令牌（内容已排队）；`4` 登录过期（已排队）；`1` 其它错误。
4. 退出码 **3**（`prepare failed` / 没有 token）→ 补令牌，**不要反复重试 `send`**：

   ```powershell
   python "<S>/scripts/wechat_notify.py" prime --timeout 180
   ```

   同时告诉用户：**"请在微信里给机器人随便发一条消息（例如 `/ping`），我这边马上把消息发出去。"**
   `prime` 返回 0 = 令牌已刷新（并会顺手把队列里的积压发掉），此时重跑第 2 步。
   `prime` 超时 → 让用户确认发的是登录时那个机器人会话，再试一次。
5. 退出码 **4**（`errcode=-14`）→ 登录已过期：`python "<S>/scripts/wechat_notify.py" login --force` 重新扫码，再发。

## 发截图（Windows）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<S>/scripts/screenshot.ps1" -Out "$env:TEMP\shot.png"
python "<S>/scripts/wechat_notify.py" send --image "$env:TEMP\shot.png"
# 只抓某个窗口（不会激活该窗口）：-Mode window -WindowTitle "窗口标题关键字"
```

`screenshot.ps1` 用 GDI BitBlt / PrintWindow 读取屏幕像素，**不注入键盘鼠标事件**。

## 排查

| 现象 | 处理 |
|---|---|
| 退出码 3 / `prepare failed` | 令牌过期：`prime` + 让用户发一条消息；队列在 `prime` 成功时会补发 |
| 退出码 4 / `errcode -14` | bot_token 过期：`login --force` 重新扫码 |
| 发送成功但用户没收到 | 确认看的是登录时的机器人会话；查 `state/notify.log` |
| 队列有积压 | `python "<S>/scripts/wechat_notify.py" run`（常驻并补发）；或下一次 `prime` 自动补发 |
| `ModuleNotFoundError: wechat_openclaw` | 依赖没装：`python -m pip install -r "<S>/requirements.txt"` |

## 限制（别对用户乱承诺）

- 只能单聊：发给扫码登录的那个人，群聊行为未验证。
- **不能冷启动主动发消息**：必须有最近的入站消息才有 `context_token`，所以 `prime` 这一步绕不开。
- 有频控：内容要合并，别连发多条。
- `state/credentials.json` 等同微信机器人身份，别外传、别贴进聊天内容。

## 可选：每轮对话结束自动推（插件）

`plugin/index.js` 是 DSH Host 插件，装了就能在每轮对话结束时自动推。**本技能默认不启用它**；
启用方法见 `plugin/README.md`。用户没明确要求时不要开启。
