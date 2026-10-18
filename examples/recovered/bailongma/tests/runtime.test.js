import assert from 'node:assert/strict'
import test from 'node:test'
import { selectTickBudget, selectRecognizerBudget } from '../src/runtime/background-budget.js'
import { buildAutonomousTickDirections } from '../src/runtime/tick-policy.js'

test('budget selection returns independent mutable profiles', () => {
  const selected = selectTickBudget()
  selected.timeoutMs = 1
  assert.equal(selectTickBudget().timeoutMs, 45_000)
  assert.equal(selectTickBudget({ startupSelfCheckActive: true }).maxRounds, null)
  assert.equal(selectRecognizerBudget().profile, 'recognizer-ordinary')
})

test('only unhandled failures or durable evidence select the larger recognizer budget', () => {
  const failedRead = { toolCallLog: [{ name: 'web_read', ok: false, ack: true }] }
  const failedWithFallback = { toolCallLog: [{ name: 'unknown', ok: false, fallback: true }] }
  assert.equal(selectRecognizerBudget([failedRead, failedWithFallback]).profile, 'recognizer-ordinary')
  assert.equal(selectRecognizerBudget([{ toolCallLog: [{ name: 'unknown', ok: false }] }]).profile, 'recognizer-durable')
  assert.equal(selectRecognizerBudget([{ userMessage: 'Please keep in mind this preference' }]).profile, 'recognizer-durable')
})

test('heartbeat text includes active scheduling context and optional discovery', () => {
  const normal = buildAutonomousTickDirections()
  assert.ok(normal.includes('private working text'))
  assert.ok(normal.includes('Runtime guardrails still validate permissions'))
  assert.ok(!normal.includes('Custom heartbeat cadence is active:'))
  const active = buildAutonomousTickDirections({
    awakeningTicks: 2,
    tickerStatus: { active: true, seconds: 30, ttl: 3, reason: 'scheduled review' },
    delegationDiscovery: 'Available worker: reference-worker',
  })
  assert.ok(active.includes('30s interval, 3 heartbeat(s) remaining. Reason: scheduled review.'))
  assert.ok(active.includes('early awakening period (2 heartbeat(s) remain)'))
  assert.ok(active.endsWith('Available worker: reference-worker'))
  assert.equal(buildAutonomousTickDirections({ tickerStatus: { active: false } }), normal)
})
