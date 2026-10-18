import assert from 'node:assert/strict'
import test from 'node:test'
import {
  WARM_WINDOW_MS, COOL_WINDOW_MS, MAX_THREADS_IN_MEMORY, MAX_WARM_INJECTED,
  makeThread, threadTemperature, buildThreadView, openCommitment, closeCommitment,
  latestOpenCommitment, touchCommitmentThread, mergeThreads, evictColdThreads,
  attributeUserMessage, appendConclusion,
} from '../src/memory/threads.js'
import { extractKeywords } from '../src/memory/keywords.js'

const now = Date.parse('2030-01-01T00:00:00Z')
const stateWith = (threads, foregroundId = null, commitments = []) => ({
  threadState: { threads, foregroundId, commitments },
})
function agedThread(age, topic = ['reference']) {
  const thread = makeThread(topic)
  thread.createdAt = thread.lastEventAt = new Date(now - age).toISOString()
  return thread
}

test('cooling uses exact wall-clock boundaries without modifying thread data', () => {
  const thread = agedThread(WARM_WINDOW_MS - 1)
  const state = stateWith([thread])
  const before = structuredClone(state)
  assert.equal(threadTemperature(state, thread, { now }), 'warm')
  assert.equal(threadTemperature(state, thread, { now: now + 1 }), 'cool')
  assert.equal(threadTemperature(state, thread, { now: now + COOL_WINDOW_MS - WARM_WINDOW_MS + 1 }), 'cold')
  assert.deepEqual(state, before)
  state.threadState.foregroundId = thread.id
  assert.equal(threadTemperature(state, thread, { now: now + COOL_WINDOW_MS }), 'foreground')
})

test('commitments pin background topics until closed and update rather than duplicate', () => {
  const state = {}
  const commitment = openCommitment(state, { text: 'Build reference adapter', tick: 7, channel: 'test' })
  const thread = state.threadState.threads[0]
  assert.equal(commitment.threadId, thread.id)
  assert.equal(thread.lastEventTick, 7)
  assert.equal(openCommitment(state, { text: 'Review adapter', threadId: thread.id }), commitment)
  assert.equal(commitment.text, 'Review adapter')
  assert.equal(state.threadState.commitments.length, 1)
  state.threadState.foregroundId = null
  thread.lastEventAt = new Date(now - COOL_WINDOW_MS * 2).toISOString()
  assert.equal(threadTemperature(state, thread, { now }), 'warm')
  assert.equal(touchCommitmentThread(state, { tick: 9 }), true)
  assert.equal(thread.lastEventTick, 9)
  thread.lastEventAt = new Date(now - COOL_WINDOW_MS * 2).toISOString()
  assert.equal(closeCommitment(state, { commitmentId: commitment.id, status: 'cancelled' }), commitment)
  assert.equal(commitment.status, 'cancelled')
  assert.ok(commitment.closedAt)
  assert.equal(threadTemperature(state, thread, { now }), 'cold')
  assert.equal(closeCommitment(state, { commitmentId: commitment.id }), null)
})

test('latest commitment prefers the requested channel, with insertion order breaking ties', () => {
  const thread = makeThread(['reference'])
  const commitments = [
    { id: 'a', threadId: thread.id, status: 'open', channel: 'alpha', createdAt: '2030-01-01T00:00:00Z' },
    { id: 'b', threadId: thread.id, status: 'open', channel: 'beta', createdAt: '2030-01-02T00:00:00Z' },
    { id: 'c', threadId: thread.id, status: 'open', channel: 'alpha', createdAt: '2030-01-01T00:00:00Z' },
    { id: 'd', threadId: thread.id, status: 'done', channel: 'beta', createdAt: '2030-01-03T00:00:00Z' },
  ]
  const state = stateWith([thread], thread.id, commitments)
  assert.equal(latestOpenCommitment(state).id, 'b')
  assert.equal(latestOpenCommitment(state, { channel: 'alpha' }).id, 'c')
  assert.equal(latestOpenCommitment(state, { channel: 'missing' }).id, 'b')
})

test('thread views cap warm context, retain foreground, and exclude cold topics', () => {
  const foreground = agedThread(COOL_WINDOW_MS * 2)
  const warm = Array.from({ length: 5 }, (_, i) => agedThread(i * 1000))
  const cold = agedThread(COOL_WINDOW_MS)
  const state = stateWith([foreground, ...warm, cold], foreground.id)
  const view = buildThreadView(state, { now })
  assert.equal(view.foreground, foreground)
  assert.equal(view.background.length, MAX_WARM_INJECTED)
  assert.deepEqual(view.background.map(item => item.thread.id), warm.slice(0, MAX_WARM_INJECTED).map(item => item.id))
  assert.equal(state.threadState.threads.length, 7)
})

test('merging transfers foreground and commitments and keeps a bounded conclusion history', () => {
  const target = agedThread(2000, ['target'])
  const source = agedThread(1000, ['source'])
  target.conclusions = ['one', 'two', 'three', 'four', 'five']
  source.conclusions = ['five', 'six', 'seven']
  source.summary = 'source summary'
  source.lastEventTick = 8
  const commitment = { id: 'commitment', threadId: source.id, status: 'open' }
  const state = stateWith([target, source], source.id, [commitment])
  assert.equal(mergeThreads(state, source.id, target.id), target)
  assert.equal(state.threadState.foregroundId, target.id)
  assert.equal(commitment.threadId, target.id)
  assert.deepEqual(target.conclusions, ['three', 'four', 'five', 'six', 'seven'])
  assert.equal(target.summary, 'source summary')
  assert.equal(target.lastEventTick, 8)
  assert.equal(target.hitCount, 2)
  assert.equal(state.threadState.threads.length, 1)
  assert.equal(mergeThreads(state, target.id, target.id), null)
  appendConclusion(target, 'seven')
  assert.equal(target.conclusions.length, 5)
})

test('eviction protects foreground and open commitments while removing the coldest excess', () => {
  const threads = Array.from({ length: MAX_THREADS_IN_MEMORY + 2 }, (_, i) => agedThread(COOL_WINDOW_MS + i * 1000))
  const foreground = threads.at(-1)
  const pinned = threads.at(-2)
  const state = stateWith(threads, foreground.id, [{ threadId: pinned.id, status: 'open' }])
  const evicted = evictColdThreads(state, { now })
  assert.deepEqual(evicted.map(thread => thread.id), [threads.at(-3).id, threads.at(-4).id])
  assert.equal(state.threadState.threads.length, MAX_THREADS_IN_MEMORY)
  assert.ok(state.threadState.threads.includes(foreground))
  assert.ok(state.threadState.threads.includes(pinned))
})

test('heartbeat and one-off messages do not create topics; generic references keep foreground', () => {
  const thread = makeThread(['reference', 'adapter'])
  const state = stateWith([thread], thread.id)
  assert.equal(attributeUserMessage(state, 'TICK scheduled heartbeat').event, 'noop')
  assert.equal(attributeUserMessage(state, '今天天气怎么样').event, 'noop')
  const result = attributeUserMessage(state, '打开那个网页', { tick: 12 })
  assert.equal(result.event, 'continued')
  assert.equal(result.thread, thread)
  assert.equal(thread.lastEventTick, 12)
  assert.equal(state.threadState.threads.length, 1)
})

test('keyword extraction respects a result cap and filters relative-time stop words', () => {
  assert.deepEqual(extractKeywords(''), [])
  assert.equal(extractKeywords('reference adapter reference adapter memory', 2).length, 2)
  assert.ok(extractKeywords('reference adapter reference adapter memory', 2).includes('reference'))
  assert.ok(!extractKeywords('昨天', 20).includes('昨天'))
})
