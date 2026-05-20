import { useCallback } from 'react'
import { toast } from 'sonner'
import type { SSEHandlers } from '@/services/api/agent'
import { useAgentStore } from '@/stores/agentStore'

export interface AgentStreamHandlerOptions {
  runId: string
  sessionId: string
  onTitleUpdated?: (sessionId: string, title: string) => void
  onStreamSettled?: () => void
  setSubmitStatus?: (status: 'ready' | 'submitted' | 'streaming') => void
  setItemLoading?: (sessionId: string, loading: boolean) => void
  refreshSessions?: () => void | Promise<void>
}

/** Builds SSE handler map for a single agent run (shared by session restore and new runs). */
export function useAgentStreamHandlers() {
  const {
    setThinking,
    handleAgentUpdate,
    handleSqlGenerated,
    handleWebDatasourceProposed,
    handleAnswerChunk,
    handleDone,
    handleError,
  } = useAgentStore()

  const buildHandlers = useCallback(
    (opts: AgentStreamHandlerOptions): SSEHandlers => {
      const {
        runId,
        sessionId,
        onTitleUpdated,
        onStreamSettled,
        setSubmitStatus,
        setItemLoading,
        refreshSessions,
      } = opts

      const settle = () => {
        setSubmitStatus?.('ready')
        setItemLoading?.(sessionId, false)
        onStreamSettled?.()
      }

      return {
        onThinking: (d) => setThinking(runId, d.message, d.agent),
        onAgentUpdate: (d) => handleAgentUpdate(runId, d),
        onSqlGenerated: (d) => handleSqlGenerated(runId, d),
        onWebDatasourceProposed: (d) => handleWebDatasourceProposed(runId, d),
        onAnswerChunk: (d) => handleAnswerChunk(runId, d),
        onTitleUpdated: (d) => {
          if (d.session_id && d.title) {
            onTitleUpdated?.(d.session_id, d.title)
          }
        },
        onDone: (d) => {
          handleDone(runId, d)
          settle()
          void refreshSessions?.()
        },
        onError: (d) => {
          handleError(runId, d.message)
          toast.error(d.message)
          settle()
          void refreshSessions?.()
        },
        onClose: settle,
      }
    },
    [
      setThinking,
      handleAgentUpdate,
      handleSqlGenerated,
      handleWebDatasourceProposed,
      handleAnswerChunk,
      handleDone,
      handleError,
    ]
  )

  return { buildHandlers }
}
