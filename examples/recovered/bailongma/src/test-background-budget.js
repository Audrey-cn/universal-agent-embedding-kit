import assert from 'node:assert/strict'
import {
  selectTickBudget,
  selectRecognizerBudget,
  turnHasDurableTool,
  turnHasExplicitMemoryRequest,
  turnHasToolFailure,
} from './runtime/background-budget.js'

assert.deepEqual(
  selectTickBudget({ hasActiveTask: false, startupSelfCheckActive: false }),
  { profile: 'tick-idle', timeoutMs: 45_000, maxTokens: 1_200, maxRounds: 4 },
  'idle Tick uses the strict background budget',
)
assert.deepEqual(
  selectTickBudget({ hasActiveTask: true }),
  { profile: 'tick-active', timeoutMs: 120_000, maxTokens: 2_400, maxRounds: null },
  'an active task keeps the larger Tick budget',
)
assert.equal(
  selectTickBudget({ startupSelfCheckActive: true }).profile,
  'tick-active',
  'startup self-check uses the active Tick profile',
)

const ordinary = { userMessage: '随便聊聊', toolCallLog: [] }
const explicit = { userMessage: '请记住我喜欢红茶', toolCallLog: [] }
const durable = { userMessage: '查一下资料', toolCallLog: [{ name: 'web_read', ok: true }] }
const failed = { userMessage: '执行一下', toolCallLog: [{ name: 'exec_command', ok: false }] }
const fallbackFailure = { userMessage: '执行一下', toolCallLog: [{ name: 'exec_command', ok: false, fallback: true }] }

assert.deepEqual(
  selectRecognizerBudget([ordinary]),
  { profile: 'recognizer-ordinary', timeoutMs: 25_000, maxTokens: 700, maxRounds: 4 },
  'ordinary recognizer work uses the smaller budget',
)
assert.deepEqual(
  selectRecognizerBudget([explicit]),
  { profile: 'recognizer-durable', timeoutMs: 60_000, maxTokens: 1_400, maxRounds: 6 },
  'explicit memory requests use the durable budget',
)
assert.equal(selectRecognizerBudget([durable]).profile, 'recognizer-durable')
assert.equal(selectRecognizerBudget([failed]).profile, 'recognizer-durable')

assert.equal(turnHasExplicitMemoryRequest(explicit), true)
assert.equal(turnHasExplicitMemoryRequest(ordinary), false)
assert.equal(turnHasDurableTool(durable), true)
assert.equal(turnHasDurableTool({ toolCallLog: [{ name: 'web_read', ok: false }] }), false)
assert.equal(turnHasToolFailure(failed), true)
assert.equal(turnHasToolFailure(fallbackFailure), false)

console.log('background budget tests passed')
