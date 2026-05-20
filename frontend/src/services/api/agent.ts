import { agentClient, AGENT_BASE_URL } from '@/services/api/client'
import type { ReportBlock } from '@/types/report'

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

export interface SessionListItem {
  session_id: string
  title: string
  updated_at: string
}

export interface SessionListResponse {
  sessions: SessionListItem[]
}

export interface SessionDetailResponse {
  session_id: string
  title: string
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

export type { ReportBlock }

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

export interface AnswerChunkEvent {
  content: string
}

export interface DoneEvent {
  content: ReportBlock[]
  insights?: string
}

export interface ErrorEvent {
  message: string
}

export interface TitleUpdatedEvent {
  session_id: string
  title: string
}

// ── REST API ─────────────────────────────────────────────────────────────────

export const createSession = async (): Promise<CreateSessionResponse> => {
  const res = await agentClient.post<CreateSessionResponse>('/agent/sessions', {})
  return res.data
}

export const listSessions = async (): Promise<SessionListResponse> => {
  const res = await agentClient.get<SessionListResponse>('/agent/sessions')
  return res.data
}

export const getSessionDetail = async (
  sessionId: string
): Promise<SessionDetailResponse> => {
  const res = await agentClient.get<SessionDetailResponse>(
    `/agent/sessions/${sessionId}`
  )
  return res.data
}

export const deleteSession = async (sessionId: string): Promise<void> => {
  await agentClient.delete(`/agent/sessions/${sessionId}`)
}

export const getSessionRuns = async (
  sessionId: string
): Promise<SessionRunsResponse> => {
  const res = await agentClient.get<SessionRunsResponse>(
    `/agent/sessions/${sessionId}/runs`
  )
  return res.data
}

export const startRun = async (
  sessionId: string,
  body: StartRunRequest
): Promise<StartRunResponse> => {
  const res = await agentClient.post<StartRunResponse>(
    `/agent/sessions/${sessionId}/runs`,
    body
  )
  return res.data
}

export const approveSQL = async (
  runId: string,
  sql?: string
): Promise<{ success: boolean }> => {
  const res = await agentClient.post<{ success: boolean }>(
    `/agent/runs/${runId}/approve`,
    { sql }
  )
  return res.data
}

export const rejectSQL = async (
  runId: string,
  reason: string,
  sql?: string
): Promise<{ success: boolean }> => {
  const res = await agentClient.post<{ success: boolean }>(
    `/agent/runs/${runId}/reject`,
    { reason, sql }
  )
  return res.data
}

export const getRunReport = async (runId: string): Promise<RunReport> => {
  const res = await agentClient.get<RunReport>(`/agent/runs/${runId}/report`)
  return res.data
}

export const stopRun = async (
  runId: string
): Promise<{ success: boolean; already_stopped?: boolean }> => {
  const res = await agentClient.post<{ success: boolean; already_stopped?: boolean }>(
    `/agent/runs/${runId}/stop`
  )
  return res.data
}

export interface GenerateTitleRequest {
  query: string
  model?: string
  base_url?: string
  api_key?: string
}

export const generateTitle = async (body: GenerateTitleRequest): Promise<string> => {
  try {
    const res = await agentClient.post<{ title: string }>('/agent/generate-title', {
      query: body.query,
      model: body.model ?? '',
      base_url: body.base_url ?? '',
      api_key: body.api_key ?? '',
    })
    return res.data.title || body.query.substring(0, 50)
  } catch {
    return body.query.length > 50 ? `${body.query.substring(0, 50)}...` : body.query
  }
}

// ── SSE Streaming ────────────────────────────────────────────────────────────

export interface SSEHandlers {
  onThinking?: (data: ThinkingEvent) => void
  onAgentUpdate?: (data: AgentUpdateEvent) => void
  onSqlGenerated?: (data: SqlGeneratedEvent) => void
  onAnswerChunk?: (data: AnswerChunkEvent) => void
  onTitleUpdated?: (data: TitleUpdatedEvent) => void
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

  es.addEventListener('answer_chunk', (e: MessageEvent) => {
    handlers.onAnswerChunk?.(parse(e.data))
  })

  es.addEventListener('title_updated', (e: MessageEvent) => {
    handlers.onTitleUpdated?.(parse(e.data))
  })

  es.addEventListener('done', (e: MessageEvent) => {
    handlers.onDone?.(parse(e.data))
    es.close()
    handlers.onClose?.()
  })

  es.addEventListener('error', (e: MessageEvent) => {
    if ((e as MessageEvent & { data?: string }).data) {
      handlers.onError?.(parse((e as MessageEvent).data))
    }
    es.close()
    handlers.onClose?.()
  })

  return es
}
