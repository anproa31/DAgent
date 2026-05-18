import axios from 'axios'

const AGENT_BASE_URL =
  import.meta.env.VITE_AGENT_SERVICE_URL || 'http://localhost:8074'

// ── Types ────────────────────────────────────────────────────────────────────

export interface CreateSessionResponse {
  session_id: string
}

export interface SessionRunSummary {
  run_id: string
  query: string
  done: boolean
  error?: string
}

export interface SessionRunsResponse {
  session_id: string
  runs: SessionRunSummary[]
}

export interface StartRunRequest {
  query: string
  tables?: string[]
  model?: string
  base_url?: string
  api_key?: string
}

export interface StartRunResponse {
  run_id: string
  error?: string
}

export interface RunReport {
  done: boolean
  error?: string
  query: string
  current_agent: string
  sql_draft?: string
  sql_explanation?: string
  sql_approved: boolean
  pending_approval: boolean
  insights?: string
  content: ReportBlock[]
  agent_steps: string[]
}

export type ReportBlock =
  | { type: 'markdown'; content: string }
  | { type: 'image'; base64: string }
  | { type: 'table'; table: string }
  | { type: 'variable'; data: string }

// SSE event payloads
export interface ThinkingEvent {
  message: string
  agent: string
}

export interface AgentUpdateEvent {
  agent: string
  current_agent: string
  agent_steps: string[]
}

export interface SqlGeneratedEvent {
  sql: string
  explanation: string
  query: string
}

export interface DoneEvent {
  content: ReportBlock[]
  insights?: string
}

export interface ErrorEvent {
  message: string
}

// ── REST API ─────────────────────────────────────────────────────────────────

export const createSession = async (): Promise<CreateSessionResponse> => {
  const res = await axios.post<CreateSessionResponse>(
    `${AGENT_BASE_URL}/agent/sessions`,
    {}
  )
  return res.data
}

export const deleteSession = async (sessionId: string): Promise<void> => {
  await axios.delete(`${AGENT_BASE_URL}/agent/sessions/${sessionId}`)
}

export const getSessionRuns = async (sessionId: string): Promise<SessionRunsResponse> => {
  const res = await axios.get<SessionRunsResponse>(
    `${AGENT_BASE_URL}/agent/sessions/${sessionId}/runs`
  )
  return res.data
}

export const startRun = async (
  sessionId: string,
  body: StartRunRequest
): Promise<StartRunResponse> => {
  const res = await axios.post<StartRunResponse>(
    `${AGENT_BASE_URL}/agent/sessions/${sessionId}/runs`,
    body
  )
  return res.data
}

export const approveSQL = async (
  runId: string,
  sql?: string
): Promise<{ success: boolean }> => {
  const res = await axios.post<{ success: boolean }>(
    `${AGENT_BASE_URL}/agent/runs/${runId}/approve`,
    { sql }
  )
  return res.data
}

export const rejectSQL = async (
  runId: string,
  reason: string
): Promise<{ success: boolean }> => {
  const res = await axios.post<{ success: boolean }>(
    `${AGENT_BASE_URL}/agent/runs/${runId}/reject`,
    { reason }
  )
  return res.data
}

export const getRunReport = async (runId: string): Promise<RunReport> => {
  const res = await axios.get<RunReport>(
    `${AGENT_BASE_URL}/agent/runs/${runId}/report`
  )
  return res.data
}

// ── SSE Streaming ────────────────────────────────────────────────────────────

export interface SSEHandlers {
  onThinking?: (data: ThinkingEvent) => void
  onAgentUpdate?: (data: AgentUpdateEvent) => void
  onSqlGenerated?: (data: SqlGeneratedEvent) => void
  onDone?: (data: DoneEvent) => void
  onError?: (data: ErrorEvent) => void
  onClose?: () => void
}

export function streamRun(runId: string, handlers: SSEHandlers): EventSource {
  const url = `${AGENT_BASE_URL}/agent/runs/${runId}/stream`
  const es = new EventSource(url)

  const parse = (raw: string) => {
    try {
      return JSON.parse(raw)
    } catch {
      return {}
    }
  }

  es.addEventListener('thinking', (e: MessageEvent) => {
    handlers.onThinking?.(parse(e.data))
  })

  es.addEventListener('agent_update', (e: MessageEvent) => {
    handlers.onAgentUpdate?.(parse(e.data))
  })

  es.addEventListener('sql_generated', (e: MessageEvent) => {
    handlers.onSqlGenerated?.(parse(e.data))
  })

  es.addEventListener('done', (e: MessageEvent) => {
    handlers.onDone?.(parse(e.data))
    es.close()
    handlers.onClose?.()
  })

  es.addEventListener('error', (e: MessageEvent) => {
    if ((e as any).data) {
      handlers.onError?.(parse((e as any).data))
    }
    es.close()
    handlers.onClose?.()
  })

  return es
}
