const TICK_IDLE = Object.freeze({
  profile: 'tick-idle',
  timeoutMs: 45_000,
  maxTokens: 1_200,
  maxRounds: 4,
})

const TICK_ACTIVE = Object.freeze({
  profile: 'tick-active',
  timeoutMs: 120_000,
  maxTokens: 2_400,
  maxRounds: null,
})

const RECOGNIZER_ORDINARY = Object.freeze({
  profile: 'recognizer-ordinary',
  timeoutMs: 25_000,
  maxTokens: 700,
  maxRounds: 4,
})

const RECOGNIZER_DURABLE = Object.freeze({
  profile: 'recognizer-durable',
  timeoutMs: 60_000,
  maxTokens: 1_400,
  maxRounds: 6,
})

const DURABLE_INFO_TOOLS = new Set([
  'web_search',
  'web_read',
  'fetch_url',
  'browser_read',
  'read_file',
  'exec_command',
])

const EXPLICIT_MEMORY_RE = /(?:记住|记一下|记得|别忘了|以后(?:你)?(?:要|记得|别|不要)?|保存(?:一下|到记忆)?|remember|keep in mind|note that|don't forget|do not forget)/i

export function turnHasExplicitMemoryRequest(turn) {
  return EXPLICIT_MEMORY_RE.test(String(turn?.userMessage || ''))
}

export function turnHasDurableTool(turn) {
  return Array.isArray(turn?.toolCallLog)
    && turn.toolCallLog.some(entry => DURABLE_INFO_TOOLS.has(entry?.name) && entry?.ok !== false)
}

export function turnHasToolFailure(turn) {
  return Array.isArray(turn?.toolCallLog)
    && turn.toolCallLog.some(entry => entry?.ok === false && !entry?.ack && !entry?.fallback)
}

export function selectTickBudget({ hasActiveTask = false, startupSelfCheckActive = false } = {}) {
  return { ...(hasActiveTask || startupSelfCheckActive ? TICK_ACTIVE : TICK_IDLE) }
}

export function selectRecognizerBudget(turns = []) {
  const durable = turns.some(turn =>
    turnHasExplicitMemoryRequest(turn)
    || turnHasDurableTool(turn)
    || turnHasToolFailure(turn),
  )
  return { ...(durable ? RECOGNIZER_DURABLE : RECOGNIZER_ORDINARY) }
}
