const SUMMARY_PLACEHOLDER = '[摘要待生成]'
const APPROVED_SUMMARY_FLAG = 'privacyApprovedSummary'
const PRIVATE_THREAD_FIELD_PROVENANCE = '_privateFieldProvenance'

function normalizedSummary(value) {
  return String(value || '').trim().replace(/\s+/g, ' ').slice(0, 300)
}

export function prepareConversationWrite(policy, row) {
  if (policy?.conversation === 'transient') return null
  if (policy?.conversation !== 'redacted-summary') return row

  const approved = row?.[APPROVED_SUMMARY_FLAG] === true
  const { [APPROVED_SUMMARY_FLAG]: _approval, ...metadata } = row || {}
  return {
    ...metadata,
    content: approved ? String(row?.content || SUMMARY_PLACEHOLDER) : SUMMARY_PLACEHOLDER,
    focus_topic: '',
  }
}

export function prepareThreadStateWrite(policy, threadState) {
  if (policy?.conversation === 'transient') return null
  const hasPrivateProvenance = (threadState?.threads || []).some(item => item?._privateRawProvenance === true)
    || (threadState?.threads || []).some(item => item?.[PRIVATE_THREAD_FIELD_PROVENANCE])
    || (threadState?.commitments || []).some(item => item?._privateRawProvenance === true)
  if (policy?.conversation !== 'redacted-summary' && !hasPrivateProvenance) return threadState

  const ts = threadState || {}
  return {
    threads: (ts.threads || []).map(thread => {
      const privateRaw = thread?._privateRawProvenance === true
      if (!privateRaw) {
        const provenance = thread?.[PRIVATE_THREAD_FIELD_PROVENANCE]
        if (!provenance) return thread
        const restoreArray = (field) => {
          const baseline = [...(provenance.baseline?.[field] || [])]
          const baselineValues = new Set(baseline.map(value => String(value)))
          const privateValues = new Set((provenance.privateValues?.[field] || []).map(value => String(value)))
          const currentPublic = (thread?.[field] || []).filter(value => (
            baselineValues.has(String(value)) || !privateValues.has(String(value))
          ))
          return [...new Set([...baseline, ...currentPublic])]
        }
        const privateSummaries = new Set((provenance.privateValues?.summary || []).map(value => String(value)))
        const currentSummary = String(thread?.summary || '')
        return {
          ...thread,
          topic: restoreArray('topic'),
          signature: restoreArray('signature'),
          summary: privateSummaries.has(currentSummary)
            ? String(provenance.baseline?.summary || '')
            : currentSummary,
          conclusions: restoreArray('conclusions'),
        }
      }
      const approved = thread?.privacyApprovedSummary === true
      return {
        ...thread,
        topic: [],
        signature: [],
        label: approved ? String(thread.label || '') : '',
        summary: approved ? String(thread.summary || '') : '',
        conclusions: approved ? [...(thread.conclusions || [])] : [],
      }
    }),
    foregroundId: ts.foregroundId || null,
    commitments: (ts.commitments || []).map(commitment => {
      const privateRaw = commitment?._privateRawProvenance === true
      return privateRaw ? {
        ...commitment,
        text: commitment?.privacyApprovedSummary === true ? String(commitment.text || '') : '',
      } : commitment
    }),
    mergedAwayIds: Array.isArray(ts.mergedAwayIds) ? [...ts.mergedAwayIds] : undefined,
  }
}

export function markPrivateThreadRawProvenance(policy, threadState) {
  if (!['transient', 'redacted-summary'].includes(policy?.conversation)) return threadState
  for (const item of [...(threadState?.threads || []), ...(threadState?.commitments || [])]) {
    Object.defineProperty(item, '_privateRawProvenance', { value: true, configurable: false, enumerable: false })
  }
  return threadState
}

export function propagatePrivateThreadMergeProvenance(target, source) {
  if (!target || !source || target._privateRawProvenance === true) return target
  const sourceFieldProvenance = source[PRIVATE_THREAD_FIELD_PROVENANCE]
  if (source._privateRawProvenance !== true && !sourceFieldProvenance) return target

  let provenance = target[PRIVATE_THREAD_FIELD_PROVENANCE]
  if (!provenance) {
    provenance = {
      baseline: {
        topic: [...(target.topic || [])],
        signature: [...(target.signature || [])],
        summary: String(target.summary || ''),
        conclusions: [...(target.conclusions || [])],
      },
      privateValues: { topic: [], signature: [], summary: [], conclusions: [] },
    }
    Object.defineProperty(target, PRIVATE_THREAD_FIELD_PROVENANCE, {
      value: provenance,
      configurable: false,
      enumerable: false,
    })
  }

  for (const field of ['topic', 'signature', 'conclusions']) {
    const incoming = source._privateRawProvenance === true
      ? (source[field] || [])
      : (sourceFieldProvenance?.privateValues?.[field] || [])
    provenance.privateValues[field] = [...new Set([...provenance.privateValues[field], ...incoming])]
  }
  const incomingSummaries = source._privateRawProvenance === true
    ? [source.summary]
    : (sourceFieldProvenance?.privateValues?.summary || [])
  provenance.privateValues.summary = [...new Set([
    ...provenance.privateValues.summary,
    ...incomingSummaries.filter(value => String(value || '')),
  ])]
  return target
}

export function prepareActionLogWrite(policy, row) {
  if (!['security-metadata', 'operation-metadata'].includes(policy?.actionLog)) return row

  return {
    timestamp: row?.timestamp,
    tool: row?.tool,
    summary: policy.actionLog === 'operation-metadata' ? normalizedSummary(row?.summary) : '',
    detail: '',
    status: row?.status,
    risk: row?.risk,
    args_json: '{}',
    result_preview: '',
    error: '',
    duration_ms: row?.duration_ms,
    source: row?.source,
  }
}

export function allowMemoryWrite(policy, { explicit = false } = {}) {
  if (policy?.memory === 'disabled') return false
  if (policy?.memory === 'explicit-only') return explicit === true
  return true
}

export function allowProfileWrite(policy) {
  return policy?.profile === 'enabled'
}

const AUDIT_METADATA_KEYS = new Set([
  'eventType',
  'event_type',
  'timestamp',
  'created_at',
  'component',
  'path',
  'outcome',
  'correlationId',
  'correlation_id',
  'source',
  'channel',
  'chosen_count',
  'skipped',
])

function selectAuditMetadata(row) {
  const selected = {}
  for (const [key, value] of Object.entries(row || {})) {
    if (AUDIT_METADATA_KEYS.has(key)) selected[key] = value
  }
  return selected
}

export function prepareAuditWrite(policy, row) {
  if (!['minimal', 'conservative'].includes(policy?.mode)) return row

  const prepared = selectAuditMetadata(row)
  if (row?.payload && typeof row.payload === 'object') {
    prepared.payload = selectAuditMetadata(row.payload)
  }
  return prepared
}
