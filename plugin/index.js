/**
 * dsh-wechat-notify -- optional DSH host plugin: push the end of every turn to WeChat.
 *
 * Zero dependencies on purpose. A host plugin loaded straight from a file is not on
 * the profile's package resolution path, so it may only import Node builtins:
 * `node:child_process`, `node:fs`, `node:os` and `node:path`.
 *
 * Hooks:
 *   session/event        user/message      remember the instruction (for the preview)
 *                        assistant/message remember the last reply text
 *                        turn/end          turn finished -> spawn one `send`
 *
 * Only root sessions notify (child agents are ignored unless `rootsOnly: false`).
 * The child process is detached through `unref()` and its stdio is discarded, so a
 * slow or failing WeChat call can never stall or crash a turn.
 *
 * Nothing here is machine-specific: paths come from `DSH_HOME`, `WECHAT_NOTIFY_*`
 * environment variables, or the config block in `cordis.patch.yml`.
 *
 * Disabled by default -- see plugin/README.md before turning it on.
 */

import { spawn } from 'node:child_process'
import { appendFileSync, existsSync, mkdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'

export const name = 'dsh-wechat-notify'
export const inject = []

/** Human labels for the turn-end reason kinds DSH reports. */
export const KIND_LABEL = {
  completed: '任务完成',
  error: '任务出错',
  aborted: '任务被中止',
  'max-tokens': '达到输出上限',
  blocked: '回合被阻断',
  interrupted: '任务中断',
}

/** Reason kinds the plugin is willing to notify about. */
export const NOTIFIABLE_KINDS = Object.keys(KIND_LABEL)

/**
 * Build the default configuration for this machine.
 * @param {Record<string, string | undefined>} env
 */
export function resolveDefaults(env = process.env) {
  const dshHome = env.DSH_HOME || join(homedir(), '.dsh')
  const skillDir = env.WECHAT_NOTIFY_SKILL_DIR || join(dshHome, 'skills', 'wechat-notify')
  const stateDir = env.WECHAT_NOTIFY_STATE_DIR || join(skillDir, 'scripts', 'state')
  return {
    enabled: true,
    pythonPath: env.WECHAT_NOTIFY_PYTHON || 'python',
    scriptPath: env.WECHAT_NOTIFY_SCRIPT || join(skillDir, 'scripts', 'wechat_notify.py'),
    titlePrefix: 'DSH',
    onlyKinds: ['completed', 'error'],
    rootsOnly: true,
    includePrompt: true,
    includeReply: true,
    promptMaxChars: 60,
    replyMaxChars: 140,
    cooldownMs: 10000,
    minTurnMs: 0,
    timeoutMs: 20000,
    logPath: join(stateDir, 'plugin.log'),
  }
}

/**
 * Merge user config over the resolved defaults and clamp numeric fields.
 * @param {Record<string, unknown>} [config]
 * @param {Record<string, string | undefined>} [env]
 */
export function normalize(config = {}, env = process.env) {
  const defaults = resolveDefaults(env)
  const cfg = { ...defaults }
  for (const [key, value] of Object.entries(config || {})) {
    if (value !== undefined && value !== null) cfg[key] = value
  }

  const kinds = Array.isArray(cfg.onlyKinds) ? cfg.onlyKinds.map(String) : []
  cfg.onlyKinds = kinds.filter((kind) => NOTIFIABLE_KINDS.includes(kind))
  if (cfg.onlyKinds.length === 0) cfg.onlyKinds = ['completed']

  cfg.cooldownMs = Math.max(0, Math.floor(Number(cfg.cooldownMs) || 0))
  cfg.minTurnMs = Math.max(0, Math.floor(Number(cfg.minTurnMs) || 0))
  cfg.timeoutMs = Math.max(1000, Math.floor(Number(cfg.timeoutMs) || 20000))
  cfg.promptMaxChars = Math.max(10, Math.floor(Number(cfg.promptMaxChars) || 60))
  cfg.replyMaxChars = Math.max(20, Math.floor(Number(cfg.replyMaxChars) || 140))
  cfg.rootsOnly = cfg.rootsOnly !== false
  cfg.enabled = cfg.enabled !== false
  cfg.includePrompt = cfg.includePrompt !== false
  cfg.includeReply = cfg.includeReply !== false
  cfg.pythonPath = String(cfg.pythonPath || 'python')
  cfg.scriptPath = String(cfg.scriptPath || '')
  cfg.logPath = String(cfg.logPath || '')
  return cfg
}

/** Collapse whitespace and cut to `max` characters. */
export function truncate(text, max) {
  const flat = String(text ?? '').replace(/\s+/g, ' ').trim()
  return flat.length <= max ? flat : `${flat.slice(0, max)}…`
}

/** Pull plain text out of a DSH message's content blocks. */
export function textOf(message, max) {
  const blocks = message?.content
  if (!Array.isArray(blocks)) return ''
  const parts = []
  for (const block of blocks) {
    if (block?.type === 'text' && typeof block.text === 'string' && block.text.trim()) {
      parts.push(block.text.trim())
    }
  }
  return truncate(parts.join(' '), max)
}

/** Last path segment of a workspace path, for the notification header. */
export function workspaceLabel(cwd) {
  if (typeof cwd !== 'string' || !cwd) return ''
  const parts = cwd.replace(/[\\/]+$/, '').split(/[\\/]/)
  return parts[parts.length - 1] || ''
}

/**
 * Compose the notification body.
 * @param {{ prefix?: string, kind?: string, at?: string, workspace?: string,
 *           prompt?: string, reply?: string, errorMessage?: string,
 *           includePrompt?: boolean, includeReply?: boolean }} input
 */
export function buildBody(input = {}) {
  const label = KIND_LABEL[input.kind] ?? `任务结束(${input.kind ?? 'unknown'})`
  const lines = [`🤖 ${input.prefix || 'DSH'} · ${label} · ${input.at || ''}`.trim()]
  if (input.workspace) lines.push(`工作区：${input.workspace}`)
  if (input.includePrompt !== false && input.prompt) lines.push(`任务：${input.prompt}`)
  if (input.includeReply !== false && input.reply) lines.push(`回复：${input.reply}`)
  if (input.errorMessage) lines.push(`错误：${truncate(input.errorMessage, 100)}`)
  return lines.join('\n')
}

function nowTime() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

/**
 * Register the plugin.
 * @param {any} ctx DSH plugin context
 * @param {Record<string, unknown>} [config]
 */
export function apply(ctx, config = {}) {
  const cfg = normalize(config)
  const logger = ctx?.logger

  const log = (line) => {
    const text = `[${new Date().toISOString()}] ${line}`
    try {
      if (cfg.logPath) {
        mkdirSync(dirname(cfg.logPath), { recursive: true })
        appendFileSync(cfg.logPath, `${text}\n`, 'utf8')
      }
    } catch {
      // A broken log path must never break notifications.
    }
    try {
      logger?.info?.(`wechat-notify: ${line}`)
    } catch {
      // ignore logger failures
    }
  }

  log(
    `插件已激活（enabled=${cfg.enabled}，onlyKinds=${cfg.onlyKinds.join(',')}，` +
      `rootOnly=${cfg.rootsOnly}）`,
  )
  if (!cfg.enabled) return

  if (!cfg.scriptPath || !existsSync(cfg.scriptPath)) {
    log(`未找到 wechat_notify.py（scriptPath=${cfg.scriptPath}），插件不发送`)
    return
  }

  /** sessionId -> { prompt, reply, turnStart, lastSentAt } */
  const states = new Map()

  const stateFor = (id) => {
    let state = states.get(id)
    if (!state) {
      state = { prompt: '', reply: '', turnStart: 0, lastSentAt: 0 }
      states.set(id, state)
    }
    return state
  }

  const fire = (body) => {
    let child
    try {
      child = spawn(cfg.pythonPath, [cfg.scriptPath, 'send', body], {
        windowsHide: true,
        stdio: 'ignore',
        timeout: cfg.timeoutMs,
      })
    } catch (error) {
      log(`spawn 失败：${String(error)}`)
      return
    }
    child.on('error', (error) => log(`spawn error：${String(error)}`))
    child.on('exit', (code, signal) => {
      if (code !== 0 && code !== null) log(`send 退出码 ${code}${signal ? ` (${signal})` : ''}`)
    })
    try {
      child.unref()
    } catch {
      // older runtimes may not support unref on this handle
    }
  }

  const onSessionEvent = (session, event) => {
    try {
      if (!event || typeof event.type !== 'string') return
      const id = session?.id
      if (id == null) return

      if (event.type === 'turn/start') {
        stateFor(id).turnStart = Number(event.data?.ts ?? Date.now())
        return
      }

      if (event.type === 'user/message') {
        const state = stateFor(id)
        const text = textOf(event.data?.message, cfg.promptMaxChars)
        if (text) state.prompt = text
        state.turnStart = state.turnStart || Number(event.data?.ts ?? 0)
        return
      }

      if (event.type === 'assistant/message') {
        const state = stateFor(id)
        const text = textOf(event.data?.message, cfg.replyMaxChars)
        if (text) state.reply = text
        return
      }

      if (event.type !== 'turn/end') return

      const depth = session?.header?.delegationDepth
      if (cfg.rootsOnly && depth != null && depth !== 0) return

      const kind = String(event.data?.reason?.kind ?? 'completed')
      if (!cfg.onlyKinds.includes(kind)) return

      const state = stateFor(id)
      const elapsed = state.turnStart ? Date.now() - state.turnStart : 0
      if (cfg.minTurnMs > 0 && elapsed > 0 && elapsed < cfg.minTurnMs) {
        state.reply = ''
        return
      }

      const now = Date.now()
      if (now - state.lastSentAt < cfg.cooldownMs) return
      state.lastSentAt = now

      const body = buildBody({
        prefix: cfg.titlePrefix,
        kind,
        at: nowTime(),
        workspace: workspaceLabel(session?.header?.cwd),
        prompt: state.prompt,
        reply: truncate(state.reply, cfg.replyMaxChars),
        errorMessage: event.data?.reason?.error?.message,
        includePrompt: cfg.includePrompt,
        includeReply: cfg.includeReply,
      })

      log(`发送通知（${kind}，${body.length} 字）：${body.replace(/\n/g, '｜')}`)
      fire(body)
      state.reply = ''
    } catch (error) {
      log(`session/event 处理异常：${String(error)}`)
    }
  }

  const offSession = ctx.on('session/event', onSessionEvent)
  const offDisposed = ctx.on('agent/disposed', ({ agent } = {}) => {
    try {
      const id = agent?.session?.id
      if (id != null) states.delete(id)
    } catch {
      // ignore
    }
  })

  ctx.effect(() => () => {
    try {
      offSession()
      offDisposed()
    } catch {
      // ignore
    }
    states.clear()
  })
}
