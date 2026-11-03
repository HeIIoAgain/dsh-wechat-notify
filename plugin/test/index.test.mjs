import assert from 'node:assert/strict'
import { join } from 'node:path'
import { test } from 'node:test'

import {
  KIND_LABEL,
  buildBody,
  normalize,
  resolveDefaults,
  textOf,
  truncate,
  workspaceLabel,
} from '../index.js'

test('resolveDefaults derives every path from DSH_HOME', () => {
  const defaults = resolveDefaults({ DSH_HOME: 'C:/Users/example/.dsh' })
  assert.equal(defaults.pythonPath, 'python')
  assert.match(defaults.scriptPath, /skills[\\/]wechat-notify[\\/]scripts[\\/]wechat_notify\.py$/)
  assert.match(defaults.logPath, /scripts[\\/]state[\\/]plugin\.log$/)
  assert.equal(defaults.enabled, true)
})

test('resolveDefaults honours WECHAT_NOTIFY_* overrides', () => {
  const defaults = resolveDefaults({
    DSH_HOME: '/home/example/.dsh',
    WECHAT_NOTIFY_PYTHON: '/usr/bin/python3.12',
    WECHAT_NOTIFY_SCRIPT: '/opt/wechat/wechat_notify.py',
    WECHAT_NOTIFY_STATE_DIR: '/var/lib/wechat',
  })
  assert.equal(defaults.pythonPath, '/usr/bin/python3.12')
  assert.equal(defaults.scriptPath, '/opt/wechat/wechat_notify.py')
  // path.join is platform-specific, so build the expectation the same way.
  assert.equal(defaults.logPath, join('/var/lib/wechat', 'plugin.log'))
})

test('normalize clamps numbers and rejects unknown kinds', () => {
  const cfg = normalize({
    onlyKinds: ['completed', 'nonsense'],
    cooldownMs: -5,
    timeoutMs: 10,
    promptMaxChars: 1,
    replyMaxChars: 2,
  })
  assert.deepEqual(cfg.onlyKinds, ['completed'])
  assert.equal(cfg.cooldownMs, 0)
  assert.equal(cfg.timeoutMs, 1000)
  assert.equal(cfg.promptMaxChars, 10)
  assert.equal(cfg.replyMaxChars, 20)
})

test('normalize keeps explicit false values', () => {
  const cfg = normalize({ enabled: false, rootsOnly: false, includeReply: false })
  assert.equal(cfg.enabled, false)
  assert.equal(cfg.rootsOnly, false)
  assert.equal(cfg.includeReply, false)
})

test('normalize falls back to completed when onlyKinds is empty', () => {
  assert.deepEqual(normalize({ onlyKinds: [] }).onlyKinds, ['completed'])
})

test('truncate flattens whitespace and appends an ellipsis', () => {
  assert.equal(truncate('a\n\n b\tc', 10), 'a b c')
  assert.equal(truncate('0123456789', 4), '0123…')
  assert.equal(truncate(null, 4), '')
})

test('textOf reads only text blocks', () => {
  const message = {
    content: [
      { type: 'text', text: 'hi ' },
      { type: 'image', data: 'ignored' },
      { type: 'text', text: 'world' },
    ],
  }
  assert.equal(textOf(message, 100), 'hi world')
  assert.equal(textOf({ content: 'nope' }, 100), '')
  assert.equal(textOf(null, 100), '')
})

test('workspaceLabel handles both separators', () => {
  assert.equal(workspaceLabel('C:\\work\\demo-project'), 'demo-project')
  assert.equal(workspaceLabel('/home/demo/project/'), 'project')
  assert.equal(workspaceLabel(''), '')
  assert.equal(workspaceLabel(undefined), '')
})

test('buildBody includes only the requested sections', () => {
  const full = buildBody({
    prefix: 'DSH',
    kind: 'completed',
    at: '23:30:00',
    workspace: 'demo',
    prompt: '把结果发我',
    reply: '已完成',
  })
  assert.equal(
    full,
    ['🤖 DSH · 任务完成 · 23:30:00', '工作区：demo', '任务：把结果发我', '回复：已完成'].join('\n'),
  )

  const minimal = buildBody({
    kind: 'error',
    at: '01:02:03',
    includePrompt: false,
    includeReply: false,
  })
  assert.equal(minimal, '🤖 DSH · 任务出错 · 01:02:03')
})

test('buildBody appends the error message and labels unknown kinds', () => {
  const body = buildBody({ kind: 'weird', at: '00:00:00', errorMessage: 'boom' })
  assert.match(body, /任务结束\(weird\)/)
  assert.match(body, /错误：boom/)
})

test('every notifiable kind has a Chinese label', () => {
  for (const label of Object.values(KIND_LABEL)) {
    assert.equal(typeof label, 'string')
    assert.ok(label.length > 0)
  }
})
