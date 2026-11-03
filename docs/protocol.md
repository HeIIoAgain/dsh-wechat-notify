# 协议与令牌生命周期

这份文档解释"为什么必须先 `prime`"，以及 `bot_token` / `context_token` 各自的寿命。
代码里的实现见 `src/wechat_notify/login.py`、`client.py`、`daemon.py`。

## 两个令牌，别搞混

| 令牌 | 谁给的 | 存在哪 | 寿命 | 失效表现 |
|---|---|---|---|---|
| `bot_token` | 扫码并确认后由网关下发 | `state/credentials.json` | 数周（网关侧决定） | `errcode -14`，退出码 4 |
| `context_token` | **每条入站消息**都会带一个 | `state/target.json` | 网关按会话窗口判定，经验值约 30 分钟 | `prepare failed`，退出码 3 |

`context_token` 无法伪造、无法预取、也没有"创建会话"的接口——这是微信侧对机器人主动推送的
反滥用设计。所以工具能做的只有两件事：

1. **等**：`prime` 起一个长轮询，等你给机器人发一条消息，然后把消息里的 `context_token`
   落盘并立刻把队列里的积压发掉；
2. **常驻**：`run` 持续长轮询，收到消息就刷新令牌，同时补发队列、回 `/ping`。

## 登录流程

```
GET  /ilink/bot/get_bot_qrcode?bot_type=3      -> { qrcode, qrcode_img_content }
GET  /ilink/bot/get_qrcode_status?qrcode=...   -> status: wait | scaned | confirmed | expired
                                                 confirmed 时带 ilink_bot_id / bot_token / baseurl
```

- `qrcode_img_content` 可能是 data URI、http 链接、裸 base64 PNG，甚至纯文本；三种都做了兜底
  （`render_qr_image`），最终统一落成 `state/qr.png`。
- 单个二维码最多轮询 5 分钟，`expired` / 超时会自动换一张，直到 `--timeout`（默认 8 分钟）。
- 拿到凭据后立刻 `atomic_write_json`（临时文件 + `os.replace`），避免半截文件。

## 发送流程

```
send_once()
  ├─ 读 credentials.json        -> 没有 => NoLoginError            (退出码 2)
  ├─ 读 target.json             -> 没有 => NoSessionError          (退出码 3，进队列)
  └─ client.send_text/image/file(context_token=...)
        ├─ errcode -14          -> 登录过期                        (退出码 4，进队列)
        ├─ errcode -2 / prepare failed -> 令牌过期                 (退出码 3，进队列)
        └─ 其它异常             -> 未知错误                        (退出码 1，进队列)
```

发送顺序固定为 **文字 → 图片 → 文件**：先给收件人上下文，再给附件。每个附件单独一条消息。

## 队列

- 发不出去的内容写进 `state/queue/<毫秒时间戳>-<随机6位>.json`，附件会**复制**到
  `state/queue/attachments/`，所以源文件被改/删也不会破坏积压。
- `flush_queue` 按文件名排序（即时间顺序）逐条发；**遇到第一个失败就停**，保留剩余队列。
  原因很简单：后一条几乎总是依赖前一条的上下文，跳过失败项会让对方收到断头消息。
- 成功发送后记录搬到 `state/sent/`，便于事后对账。

## 常驻进程

- `run` 用 `state/daemon.lock` 做单实例互斥：Windows 走 `msvcrt.locking`，POSIX 走 `flock`。
  进程崩溃时锁由操作系统释放，不会留下僵尸锁。
- `state/daemon.json` 是心跳（PID、启动时间、队列长度），`status` 用 15 秒新鲜度判断它是否还活着。
- 长轮询失败不会退出：记一行日志、等 1 秒、重开一轮。只有 `errcode -14` 才会退出。

## 频控与内容

- 微信对机器人消息有频控；同一轮对话里把多条信息合并成一条，比连发更可靠。
- 出站文本按纯文本渲染：Markdown 不生效，只有 `**粗体**` / `__粗体__` 是原生的。
- 单聊有效；群聊行为未经验证，不要承诺。

## 与 DSH 的集成点

- `SKILL.md`：Agent 读的技能定义（触发条件、命令、退出码处理）。
- `plugin/index.js`：可选的 Host 插件，订阅 `session/event` 的 `turn/end` 后 `spawn` 一次 `send`；
  子进程 `stdio: 'ignore'` + `unref()`，失败只写自己的 `plugin.log`。
