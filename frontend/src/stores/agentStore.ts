import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type {
  AgentUpdateEvent,
  SqlGeneratedEvent,
  WebDatasourceProposal,
  DoneEvent,
  AnswerChunkEvent,
} from '@/services/api/agent'
import type { ReportBlock } from '@/types/report'

export type RunPhase =
  | 'idle'
  | 'starting'
  | 'thinking'
  | 'running'
  | 'awaiting_approval'
  | 'done'
  | 'error'
  /** User closed the SSE stream (stop button); backend may still be running. */
  | 'stopped'

export type ApprovalKind = 'sql' | 'web_datasource' | null

export interface WebDiscoverCandidate {
  title: string
  url: string
  snippet?: string
  score?: number
  reason?: string
}

export interface WebDatasourceProposal {
  query: string
  reason: string
  selected_urls: string[]
  candidates: WebDiscoverCandidate[]
  proposed_name?: string
}

export interface AgentRun {
  runId: string
  sessionId: string
  query: string
  phase: RunPhase
  currentAgent: string
  agentSteps: string[]
  thinkingMessage: string
  approvalKind: ApprovalKind
  // HITL SQL
  pendingSql: string
  pendingSqlExplanation: string
  pendingWebProposal: WebDatasourceProposal | null
  // Streaming answer (token/chunk accumulator while phase is active)
  streamingAnswer: string
  // Results
  content: ReportBlock[]
  insights: string
  error: string
}

interface AgentStore {
  sessionId: string | null
  /** All runs in the current session (conversation thread) */
  runs: AgentRun[]
  /** The actively streaming run (last in the list while running) */
  activeRunId: string | null
  /** User-preferred model id, persisted across sessions */
  preferredModel: string
  /**
   * IDs of runs the user explicitly stopped or abandoned.
   * Persisted so a page reload won't auto-reconnect SSE to a run we
   * intentionally let go of.
   */
  cancelledRunIds: string[]
  /** Selected tables per session — persisted so navigating back restores the selection. */
  sessionTables: Record<string, string[]>

  setSessionId: (id: string) => void
  resetSession: () => void
  setPreferredModel: (model: string) => void
  setSessionTables: (sessionId: string, tables: string[]) => void
  getSessionTables: (sessionId: string) => string[] | undefined

  addRun: (runId: string, sessionId: string, query: string) => void
  setPhase: (runId: string, phase: RunPhase) => void
  setThinking: (runId: string, message: string, agent: string) => void
  handleAgentUpdate: (runId: string, data: AgentUpdateEvent) => void
  handleSqlGenerated: (runId: string, data: SqlGeneratedEvent) => void
  handleWebDatasourceProposed: (runId: string, data: WebDatasourceProposal) => void
  updatePendingSql: (runId: string, sql: string) => void
  handleAnswerChunk: (runId: string, data: AnswerChunkEvent) => void
  handleDone: (runId: string, data: DoneEvent) => void
  handleError: (runId: string, message: string) => void
  /**
   * Cancel a run.
   * - `dropRun: true`  — remove the run from the visible chat entirely.
   * - `dropRun: false` — keep the run (prompt bubble), but wipe any
   *   in-flight generation (used by the edit-prompt flow so the textarea
   *   stays mounted while we silently stop the stream).
   */
  cancelRun: (runId: string, opts?: { dropRun?: boolean }) => void
  /** Check whether a runId has been cancelled previously. */
  isCancelled: (runId: string) => boolean

  /** Truncate runs starting at given index (inclusive) — used by edit-prompt flow */
  truncateRunsAfter: (index: number) => void

  /** Restore run state when opening a deep-linked or historical session */
  setRunsFromReports: (runs: AgentRun[]) => void
  /** Set active streaming run */
  setActiveRunId: (runId: string | null) => void
}

const MAX_CANCELLED_IDS = 500

function updateRun(runs: AgentRun[], runId: string, patch: Partial<AgentRun>): AgentRun[] {
  return runs.map((r) => (r.runId === runId ? { ...r, ...patch } : r))
}

export const useAgentStore = create<AgentStore>()(
  persist(
    (set, get) => ({
      sessionId: null,
      runs: [],
      activeRunId: null,
      preferredModel: '',
      cancelledRunIds: [],
      sessionTables: {},

      setSessionId: (id) => set({ sessionId: id }),

      resetSession: () => set({ sessionId: null, runs: [], activeRunId: null }),

      setPreferredModel: (model) => set({ preferredModel: model }),

      setSessionTables: (sessionId, tables) =>
        set((s) => ({
          sessionTables: { ...s.sessionTables, [sessionId]: tables },
        })),

      getSessionTables: (sessionId) => get().sessionTables[sessionId],

      addRun: (runId, sessionId, query) => {
        const run: AgentRun = {
          runId,
          sessionId,
          query,
          phase: 'starting',
          currentAgent: '',
          agentSteps: [],
          thinkingMessage: 'Starting analysis...',
          approvalKind: null,
          pendingSql: '',
          pendingSqlExplanation: '',
          pendingWebProposal: null,
          streamingAnswer: '',
          content: [],
          insights: '',
          error: '',
        }
        set((s) => ({ runs: [...s.runs, run], activeRunId: runId }))
      },

      setPhase: (runId, phase) =>
        set((s) => ({ runs: updateRun(s.runs, runId, { phase }) })),

      setThinking: (runId, message, agent) =>
        set((s) => ({
          runs: updateRun(s.runs, runId, {
            phase: 'thinking',
            thinkingMessage: message,
            ...(agent ? { currentAgent: agent } : {}),
          }),
        })),

      handleAgentUpdate: (runId, data) =>
        set((s) => {
          const nextAgent = data.current_agent || data.agent || ''
          const incomingSteps = Array.isArray(data.agent_steps) ? data.agent_steps : []
          const existing = s.runs.find((r) => r.runId === runId)
          // Merge: never regress to empty agent_steps when we already have history.
          const mergedSteps =
            incomingSteps.length > 0
              ? incomingSteps
              : existing?.agentSteps ?? []
          return {
            runs: updateRun(s.runs, runId, {
              phase: 'running',
              currentAgent: nextAgent || existing?.currentAgent || '',
              agentSteps: mergedSteps,
            }),
          }
        }),

      handleSqlGenerated: (runId, data) =>
        set((s) => ({
          runs: updateRun(s.runs, runId, {
            phase: 'awaiting_approval',
            approvalKind: 'sql',
            pendingSql: data.sql,
            pendingSqlExplanation: data.explanation,
            pendingWebProposal: null,
          }),
        })),

      handleWebDatasourceProposed: (runId, data) =>
        set((s) => ({
          runs: updateRun(s.runs, runId, {
            phase: 'awaiting_approval',
            approvalKind: 'web_datasource',
            pendingWebProposal: data,
            pendingSql: '',
            pendingSqlExplanation: '',
          }),
        })),

      updatePendingSql: (runId, sql) =>
        set((s) => ({
          runs: updateRun(s.runs, runId, { pendingSql: sql }),
        })),

      handleAnswerChunk: (runId, data) =>
        set((s) => {
          const existing = s.runs.find((r) => r.runId === runId)
          const next = (existing?.streamingAnswer ?? '') + (data.content ?? '')
          return {
            runs: updateRun(s.runs, runId, { streamingAnswer: next }),
          }
        }),

      handleDone: (runId, data) =>
        set((s) => ({
          runs: updateRun(s.runs, runId, {
            phase: 'done',
            content: data.content,
            insights: data.insights || '',
            streamingAnswer: '',
          }),
          activeRunId: null,
        })),

      handleError: (runId, message) =>
        set((s) => ({
          runs: updateRun(s.runs, runId, { phase: 'error', error: message }),
          activeRunId: null,
        })),

      cancelRun: (runId, opts) =>
        set((s) => {
          const dropRun = opts?.dropRun ?? true
          const existing = s.runs.find((r) => r.runId === runId)
          const alreadyTerminal =
            existing &&
            (existing.phase === 'done' || existing.phase === 'error')

          const nextCancelled = s.cancelledRunIds.includes(runId)
            ? s.cancelledRunIds
            : [runId, ...s.cancelledRunIds].slice(0, MAX_CANCELLED_IDS)

          const activeRunId = s.activeRunId === runId ? null : s.activeRunId

          if (!existing || alreadyTerminal) {
            return { activeRunId, cancelledRunIds: nextCancelled }
          }

          if (dropRun) {
            return {
              runs: s.runs.filter((r) => r.runId !== runId),
              activeRunId,
              cancelledRunIds: nextCancelled,
            }
          }

          return {
            runs: updateRun(s.runs, runId, {
              phase: 'stopped',
              streamingAnswer: '',
              thinkingMessage: '',
              currentAgent: '',
              agentSteps: [],
              pendingSql: '',
              pendingSqlExplanation: '',
              pendingWebProposal: null,
              approvalKind: null,
            }),
            activeRunId,
            cancelledRunIds: nextCancelled,
          }
        }),

      isCancelled: (runId) => get().cancelledRunIds.includes(runId),

      truncateRunsAfter: (index) =>
        set((s) => ({
          runs: s.runs.slice(0, Math.max(0, index)),
          activeRunId: null,
        })),

      setRunsFromReports: (runs) => set({ runs, activeRunId: null }),

      setActiveRunId: (runId) => set({ activeRunId: runId }),
    }),
    {
      name: 'agent-store',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        preferredModel: state.preferredModel,
        cancelledRunIds: state.cancelledRunIds,
        sessionTables: state.sessionTables,
      }),
    }
  )
)
