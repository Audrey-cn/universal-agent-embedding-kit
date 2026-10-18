import assert from 'node:assert/strict'
import test from 'node:test'
import {
  prepareConversationWrite, prepareThreadStateWrite, markPrivateThreadRawProvenance,
  prepareActionLogWrite, prepareAuditWrite, allowMemoryWrite, allowProfileWrite,
} from '../src/privacy/write-policy.js'
import { makeThread, mergeThreads, openCommitment } from '../src/memory/threads.js'

test('transient policies suppress conversations and complete thread-state writes', () => {
  assert.equal(prepareConversationWrite({ conversation: 'transient' }, { content: 'private body' }), null)
  assert.equal(prepareThreadStateWrite({ conversation: 'transient' }, { threads: [] }), null)
})

test('conversation summaries require explicit approval and clear topic content without mutating input', () => {
  const policy = { conversation: 'redacted-summary' }
  const row = { content: 'private body', focus_topic: 'private topic', timestamp: 'example-time' }
  const prepared = prepareConversationWrite(policy, row)
  assert.deepEqual(prepared, { content: '[摘要待生成]', focus_topic: '', timestamp: 'example-time' })
  assert.equal(row.content, 'private body')
  const approved = prepareConversationWrite(policy, { ...row, content: 'approved summary', privacyApprovedSummary: true })
  assert.equal(approved.content, 'approved summary')
  assert.equal(Object.hasOwn(approved, 'privacyApprovedSummary'), false)
  assert.equal(prepareConversationWrite({}, row), row)
})

test('private thread and commitment fields are redacted even after policy changes', () => {
  const thread = makeThread(['private-topic'], { signature: ['private-signature'], label: 'private-label' })
  thread.summary = 'private-summary'
  thread.conclusions = ['private-conclusion']
  const state = { threadState: { threads: [thread], foregroundId: thread.id, commitments: [] } }
  const commitment = openCommitment(state, { text: 'private-task', threadId: thread.id })
  markPrivateThreadRawProvenance({ conversation: 'redacted-summary' }, state.threadState)
  assert.equal(Object.keys(thread).includes('_privateRawProvenance'), false)
  const prepared = prepareThreadStateWrite({ conversation: 'full' }, state.threadState)
  assert.deepEqual(prepared.threads[0].topic, [])
  assert.deepEqual(prepared.threads[0].signature, [])
  assert.equal(prepared.threads[0].label, '')
  assert.equal(prepared.threads[0].summary, '')
  assert.deepEqual(prepared.threads[0].conclusions, [])
  assert.equal(prepared.commitments[0].text, '')
  assert.equal(commitment.text, 'private-task')
  assert.equal(thread.summary, 'private-summary')
})

test('approved private summaries retain only the supported approved text fields', () => {
  const thread = makeThread(['private-topic'], { signature: ['private-signature'], label: 'approved label' })
  thread.summary = 'approved summary'
  thread.conclusions = ['approved conclusion']
  thread.privacyApprovedSummary = true
  const commitment = { text: 'approved task summary', privacyApprovedSummary: true }
  const state = { threads: [thread], foregroundId: thread.id, commitments: [commitment] }
  markPrivateThreadRawProvenance({ conversation: 'redacted-summary' }, state)
  const prepared = prepareThreadStateWrite({ conversation: 'redacted-summary' }, state)
  assert.deepEqual(prepared.threads[0].topic, [])
  assert.deepEqual(prepared.threads[0].signature, [])
  assert.equal(prepared.threads[0].label, 'approved label')
  assert.equal(prepared.threads[0].summary, 'approved summary')
  assert.deepEqual(prepared.threads[0].conclusions, ['approved conclusion'])
  assert.equal(prepared.commitments[0].text, 'approved task summary')
})

test('private merge provenance survives multiple merges and preserves later public additions', () => {
  const firstPublic = makeThread(['public-a'])
  firstPublic.conclusions = ['public conclusion a']
  const privateThread = makeThread(['private-topic'], { signature: ['private-signature'] })
  privateThread.summary = 'private-summary'
  privateThread.conclusions = ['private-conclusion']
  const secondPublic = makeThread(['public-b'])
  const state = { threadState: { threads: [firstPublic, privateThread, secondPublic], foregroundId: privateThread.id, commitments: [] } }
  const commitment = openCommitment(state, { text: 'private-commitment', threadId: privateThread.id })
  markPrivateThreadRawProvenance({ conversation: 'redacted-summary' }, { threads: [privateThread], commitments: [commitment] })
  mergeThreads(state, privateThread.id, firstPublic.id)
  assert.ok(firstPublic.topic.includes('private-topic'))
  mergeThreads(state, firstPublic.id, secondPublic.id)
  secondPublic.conclusions.push('later public conclusion')
  const prepared = prepareThreadStateWrite({ conversation: 'full' }, state.threadState)
  const serialized = JSON.stringify(prepared)
  for (const privateValue of ['private-topic', 'private-signature', 'private-summary', 'private-conclusion', 'private-commitment']) {
    assert.equal(serialized.includes(privateValue), false, privateValue)
  }
  assert.ok(prepared.threads[0].topic.includes('public-b'))
  assert.ok(prepared.threads[0].topic.includes('public-a'))
  assert.ok(prepared.threads[0].conclusions.includes('later public conclusion'))
  assert.equal(prepared.commitments[0].threadId, secondPublic.id)
  assert.equal(state.threadState.foregroundId, secondPublic.id)
})

test('action metadata excludes raw tool fields and bounds operation summaries', () => {
  const row = {
    timestamp: 'example-time', tool: 'example-tool', summary: '  completed   operation  ',
    detail: 'private detail', status: 'ok', risk: 'low', args_json: '{"private":true}',
    result_preview: 'private result', error: 'private error', duration_ms: 12, source: 'example',
  }
  const security = prepareActionLogWrite({ actionLog: 'security-metadata' }, row)
  assert.equal(security.summary, '')
  assert.equal(security.tool, 'example-tool')
  assert.equal(security.status, 'ok')
  assert.equal(security.duration_ms, 12)
  for (const field of ['detail', 'result_preview', 'error']) assert.equal(security[field], '')
  assert.equal(security.args_json, '{}')
  assert.equal(prepareActionLogWrite({ actionLog: 'operation-metadata' }, row).summary, 'completed operation')
  assert.equal(prepareActionLogWrite({ actionLog: 'operation-metadata' }, { summary: 'x'.repeat(500) }).summary.length, 300)
  assert.equal(row.detail, 'private detail')
})

test('audit preparation allowlists metadata at both levels', () => {
  const row = {
    eventType: 'example-event', content: 'private content', from_id: 'private identity',
    payload: { component: 'worker', outcome: 'ok', input: 'private input', args: { raw: 'private' } },
  }
  assert.deepEqual(prepareAuditWrite({ mode: 'minimal' }, row), {
    eventType: 'example-event', payload: { component: 'worker', outcome: 'ok' },
  })
  assert.deepEqual(prepareAuditWrite({ mode: 'conservative' }, row), {
    eventType: 'example-event', payload: { component: 'worker', outcome: 'ok' },
  })
  assert.equal(prepareAuditWrite({ mode: 'full' }, row), row)
})

test('memory and profile gates preserve the source policy defaults', () => {
  assert.equal(allowMemoryWrite({ memory: 'disabled' }, { explicit: true }), false)
  assert.equal(allowMemoryWrite({ memory: 'explicit-only' }), false)
  assert.equal(allowMemoryWrite({ memory: 'explicit-only' }, { explicit: true }), true)
  assert.equal(allowMemoryWrite({}), true)
  assert.equal(allowProfileWrite({}), false)
  assert.equal(allowProfileWrite({ profile: 'enabled' }), true)
})

test('provenance must remain on live objects until preparation', () => {
  const thread = makeThread(['private-topic'])
  const state = { threads: [thread], commitments: [] }
  markPrivateThreadRawProvenance({ conversation: 'redacted-summary' }, state)
  const serializedEarly = JSON.parse(JSON.stringify(state))
  assert.equal(prepareThreadStateWrite({ conversation: 'full' }, serializedEarly), serializedEarly)
  assert.deepEqual(serializedEarly.threads[0].topic, ['private-topic'])
  assert.deepEqual(prepareThreadStateWrite({ conversation: 'full' }, state).threads[0].topic, [])
})
