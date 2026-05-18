import { create } from 'zustand'
import type { ReportBlock, AgentUpdateEvent, SqlGeneratedEvent, DoneEvent } from '@/api/agentApi'

export type RunPhase =
  | 'idle'
  | 'starting'
  | 'thinking'
  | 'running'
  | 'awaiting_approval'
  | 'done'
  | 'error'

export interface AgentRun {
  runId: string
  sessionId: string
  query: string
  phase: RunPhase
  currentAgent: string
  agentSteps: string[]
  thinkingMessage: string
  // HITL
  pendingSql: string
  pendingSqlExplanation: string
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

  setSessionId: (id: string) => void
  resetSession: () => void

  addRun: (runId: string, sessionId: string, query: string) => void
  setPhase: (runId: string, phase: RunPhase) => void
  setThinking: (runId: string, message: string, agent: string) => void
  handleAgentUpdate: (runId: string, data: AgentUpdateEvent) => void
  handleSqlGenerated: (runId: string, data: SqlGeneratedEvent) => void
  handleDone: (runId: string, data: DoneEvent) => void
  handleError: (runId: string, message: string) => void

  /** Restore run state when opening a deep-linked or historical session */
  setRunsFromReports: (runs: AgentRun[]) => void
  /** Set active streaming run */
  setActiveRunId: (runId: string | null) => void
}

function updateRun(runs: AgentRun[], runId: string, patch: Partial<AgentRun>): AgentRun[] {
  return runs.map((r) => (r.runId === runId ? { ...r, ...patch } : r))
}

export const useAgentStore = create<AgentStore>((set) => ({
  sessionId: null,
  runs: [],
  activeRunId: null,

  setSessionId: (id) => set({ sessionId: id }),

  resetSession: () => set({ sessionId: null, runs: [], activeRunId: null }),

  addRun: (runId, sessionId, query) => {
    const run: AgentRun = {
      runId,
      sessionId,
      query,
      phase: 'starting',
      currentAgent: '',
      agentSteps: [],
      thinkingMessage: 'Starting analysis...',
      pendingSql: '',
      pendingSqlExplanation: '',
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
    set((s) => ({
      runs: updateRun(s.runs, runId, {
        phase: 'running',
        currentAgent: data.current_agent || data.agent,
        agentSteps: data.agent_steps,
      }),
    })),

  handleSqlGenerated: (runId, data) =>
    set((s) => ({
      runs: updateRun(s.runs, runId, {
        phase: 'awaiting_approval',
        pendingSql: data.sql,
        pendingSqlExplanation: data.explanation,
      }),
    })),

  handleDone: (runId, data) =>
    set((s) => ({
      runs: updateRun(s.runs, runId, {
        phase: 'done',
        content: data.content,
        insights: data.insights || '',
      }),
      activeRunId: null,
    })),

  handleError: (runId, message) =>
    set((s) => ({
      runs: updateRun(s.runs, runId, { phase: 'error', error: message }),
      activeRunId: null,
    })),

  setRunsFromReports: (runs) => set({ runs, activeRunId: null }),

  setActiveRunId: (runId) => set({ activeRunId: runId }),
}))
