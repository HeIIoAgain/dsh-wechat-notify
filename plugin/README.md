# 可选：每轮对话结束自动推微信（DSH Host 插件）

`index.js` 是一个**纯 Host、零依赖**的 DSH 插件：监听 `session/event` → `turn/end`，
在一轮对话结束时 `spawn` 一个 Python 子进程调用 `wechat_notify.py send …`。
子进程 `stdio: 'ignore'` + `unref()`，发不出去不会影响 DSH 的任何一轮。

> **默认不启用。** 按需发送用技能即可；只有明确想要"自动推"时才照下面开。
> 每轮都推会很吵，建议至少设 `minTurnMs: 15000`。

## 前置

技能已安装（`install.ps1` / `install.sh` / `pip install .` 都行），假设装在：

```
<技能目录> = %DSH_HOME%\skills\wechat-notify        # 默认 C:\Users\<你>\.dsh\skills\wechat-notify
脚本       = <技能目录>\scripts\wechat_notify.py
插件文件   = <技能目录>\plugin\index.js
```

插件本身**不写死任何机器路径**，优先级是：`cordis.patch.yml` 里的 config →
环境变量 → 约定默认值（`DSH_HOME` → `skills/wechat-notify/...`）。

## 1. 写用户 patch 层

文件：`%DSH_HOME%\cordis.patch.yml`（默认 `C:\Users\<你>\.dsh\cordis.patch.yml`）。

> ⚠️ 空文件或只有注释会让 DSH 启动失败。文件不存在就新建并写下面这段；
> 已存在就把 `- insert:` 这一段追加进**顶层列表**（不要嵌套到别的条目里）。

```yaml
- insert:
    - id: dsh-wechat-notify
      name: 'C:/Users/<你>/.dsh/skills/wechat-notify/plugin/index.js'
      config:
        enabled: true
        # 下面三项不写就用环境变量 / 默认值；写了以这里为准。
        pythonPath: 'C:/Python313/python.exe'
        scriptPath: 'C:/Users/<你>/.dsh/skills/wechat-notify/scripts/wechat_notify.py'
        logPath: 'C:/Users/<你>/.dsh/skills/wechat-notify/scripts/state/plugin.log'
        onlyKinds: [completed, error]   # completed / error / aborted / max-tokens / blocked
        rootsOnly: true                 # 只推根会话，子代理不刷屏
        includePrompt: true             # 正文带用户指令
        includeReply: true              # 正文带回复摘要
        promptMaxChars: 60
        replyMaxChars: 140
        cooldownMs: 10000               # 同一会话同类通知最小间隔
        minTurnMs: 15000                # 低于 15 秒的轮次不推（嫌吵时很有用）
        timeoutMs: 20000
```

保存后约 **2 秒** HMR 生效（不用重启 DSH），`logPath` 里会出现一行
`插件已激活（enabled=true…）`。改 `index.js` **代码**才需要重启 DSH。

## 2. 环境变量（可选，比 patch 更适合多机同步）

| 变量 | 作用 |
|---|---|
| `DSH_HOME` | DSH 配置根，默认 `~/.dsh`；插件据此推导默认路径 |
| `WECHAT_NOTIFY_SKILL_DIR` | 直接指定技能目录 |
| `WECHAT_NOTIFY_PYTHON` | Python 绝对路径（默认 `python`，不保证在 DSH 的 PATH 里） |
| `WECHAT_NOTIFY_SCRIPT` | `wechat_notify.py` 绝对路径 |
| `WECHAT_NOTIFY_STATE_DIR` | 状态目录（插件日志默认放在这里的 `plugin.log`） |

## 3. 验收

先手动确认脚本能发（需要令牌，见技能里的 `prime`）：

```powershell
python "<技能目录>\scripts\wechat_notify.py" send "插件验收测试"
```

然后随便让 DSH 完成一轮对话，手机微信应收到
`🤖 DSH · 任务完成 · 时间｜工作区｜任务：…｜回复：…`。

## 4. 停用 / 调试

- 停用：`enabled: false`（2 秒生效，插件仍加载但不发）。
- 完全移除：删掉整个 `- insert:` 块。
- 排查顺序：`plugin.log` → 手动 `send` → `state/notify.log` → DSH 日志。
- 插件找不到脚本时只会写一行日志并静默退出，不会阻塞对话。

## 配置项

| 字段 | 默认 | 说明 |
|---|---|---|
| `enabled` | `true` | 总开关 |
| `pythonPath` | `python` | 解释器（建议写绝对路径） |
| `scriptPath` | `$DSH_HOME/skills/wechat-notify/scripts/wechat_notify.py` | 主程序路径 |
| `titlePrefix` | `DSH` | 通知标题前缀 |
| `onlyKinds` | `[completed, error]` | 触发推送的结束原因 |
| `rootsOnly` | `true` | 只推根会话 |
| `includePrompt` / `includeReply` | `true` | 正文是否带指令 / 回复摘要 |
| `promptMaxChars` / `replyMaxChars` | `60` / `140` | 截断长度 |
| `cooldownMs` | `10000` | 同一会话同类通知最小间隔 |
| `minTurnMs` | `0` | 低于该耗时的轮次不通知 |
| `timeoutMs` | `20000` | python 子进程超时 |
| `logPath` | `$WECHAT_NOTIFY_STATE_DIR/plugin.log` | 诊断日志（append） |
