import { useEffect, useRef } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { toast } from 'sonner'
import { getRunReport, getSessionRuns, streamRun } from '@/services/api/agent'
import { mapReportToAgentRun } from '@/features/agents/lib/map-report-to-run'
import { useAgentStreamHandlers } from '@/features/agents/hooks/use-agent-stream-handlers'
import { useAgentStore, type AgentRun } from '@/stores/agentStore'

export interface AgentSessionLoaderOptions {
  sessionFromUrl?: string
  onTablesRestored?: (tables: string[]) => void
  updateHistoryTitle: (sessionId: string, title: string) => void
  refreshAgentSessionsFromServer: () => void | Promise<void>
  setItemLoading: (sessionId: string, loading: boolean) => void
  setSubmitStatus: (status: 'ready' | 'submitted' | 'streaming') => void
}

export function useAgentSessionLoader({
  sessionFromUrl,
  onTablesRestored,
  updateHistoryTitle,
  refreshAgentSessionsFromServer,
  setItemLoading,
  setSubmitStatus,
}: AgentSessionLoaderOptions) {
  const navigate = useNavigate()
  const esRef = useRef<EventSource | null>(null)
  const { buildHandlers } = useAgentStreamHandlers()

  const resetSession = useAgentStore((s) => s.resetSession)
  const setSessionId = useAgentStore((s) => s.setSessionId)
  const setRunsFromReports = useAgentStore((s) => s.setRunsFromReports)
  const setActiveRunId = useAgentStore((s) => s.setActiveRunId)

  useEffect(() => {
    if (!sessionFromUrl) {
      esRef.current?.close()
      esRef.current = null
      resetSession()
      return
    }

    const storeSnap = useAgentStore.getState()
    const savedTables = storeSnap.sessionTables[sessionFromUrl]
    if (savedTables?.length) {
      onTablesRestored?.(savedTables)
    }

    const runsMatchSession =
      storeSnap.runs.length > 0 &&
      storeSnap.sessionId === sessionFromUrl &&
      storeSnap.runs.every((r: AgentRun) => r.sessionId === sessionFromUrl)

    let cancelled = false

    const attachStreamIfActive = () => {
      if (cancelled || esRef.current) return

      const { runs, isCancelled } = useAgentStore.getState()
      const activeRun = [...runs]
        .reverse()
        .find(
          (r) =>
            r.sessionId === sessionFromUrl &&
            !isCancelled(r.runId) &&
            ['starting', 'thinking', 'running', 'awaiting_approval'].includes(r.phase)
        )

      if (activeRun) {
        setActiveRunId(activeRun.runId)
        setSubmitStatus('streaming')
        esRef.current = streamRun(
          activeRun.runId,
          buildHandlers({
            runId: activeRun.runId,
            sessionId: sessionFromUrl,
            onTitleUpdated: updateHistoryTitle,
            setSubmitStatus,
            setItemLoading,
            refreshSessions: refreshAgentSessionsFromServer,
          })
        )
      } else {
        setItemLoading(sessionFromUrl, false)
        setSubmitStatus('ready')
      }
    }

    if (runsMatchSession) {
      attachStreamIfActive()
      return () => {
        cancelled = true
        esRef.current?.close()
        esRef.current = null
      }
    }

    esRef.current?.close()
    esRef.current = null

    void (async () => {
      try {
        const sessionData = await getSessionRuns(sessionFromUrl)
        if (cancelled) return

        setSessionId(sessionFromUrl)

        if (sessionData.runs.length === 0) {
          applyForkMergeOrClear(sessionFromUrl, setRunsFromReports)
          return
        }

        const { isCancelled } = useAgentStore.getState()
        const activeSessionRuns = sessionData.runs.filter(
          (r) => !isCancelled(r.run_id)
        )

        if (activeSessionRuns.length === 0) {
          applyForkMergeOrClear(sessionFromUrl, setRunsFromReports)
          setItemLoading(sessionFromUrl, false)
          setSubmitStatus('ready')
          return
        }

        const reportPromises = activeSessionRuns.map((r) =>
          getRunReport(r.run_id).then((report) =>
            mapReportToAgentRun(r.run_id, sessionFromUrl, report)
          )
        )
        const loadedRuns = await Promise.all(reportPromises)
        if (cancelled) return

        setRunsFromReports(mergeForkPrefixRuns(loadedRuns))

        const lastRun = loadedRuns[loadedRuns.length - 1]
        const lastIsCancelled = lastRun ? isCancelled(lastRun.runId) : false
        const lastIsActive =
          lastRun &&
          !lastIsCancelled &&
          lastRun.phase !== 'done' &&
          lastRun.phase !== 'error' &&
          lastRun.phase !== 'stopped'

        if (lastIsActive) {
          setActiveRunId(lastRun.runId)
          setSubmitStatus('streaming')
          esRef.current = streamRun(
            lastRun.runId,
            buildHandlers({
              runId: lastRun.runId,
              sessionId: sessionFromUrl,
              onTitleUpdated: updateHistoryTitle,
              setSubmitStatus,
              setItemLoading,
              refreshSessions: refreshAgentSessionsFromServer,
            })
          )
        } else {
          setItemLoading(sessionFromUrl, false)
          setSubmitStatus('ready')
        }
      } catch {
        if (!cancelled) {
          toast.error('This session is no longer available.')
          navigate({ to: '/agents', search: {} })
        }
      }
    })()

    return () => {
      cancelled = true
      esRef.current?.close()
      esRef.current = null
    }
  }, [
    sessionFromUrl,
    onTablesRestored,
    updateHistoryTitle,
    refreshAgentSessionsFromServer,
    navigate,
    setSessionId,
    setRunsFromReports,
    setItemLoading,
    setActiveRunId,
    setSubmitStatus,
    buildHandlers,
    resetSession,
  ])

  return { esRef }
}

function applyForkMergeOrClear(
  sessionFromUrl: string,
  setRunsFromReports: (runs: AgentRun[]) => void
) {
  const prevRuns = useAgentStore.getState().runs
  const forkMerge =
    prevRuns.some((r) => r.sessionId !== sessionFromUrl) &&
    prevRuns.some((r) => r.sessionId === sessionFromUrl)
  setRunsFromReports(forkMerge ? prevRuns : [])
}

function mergeForkPrefixRuns(loadedRuns: AgentRun[]): AgentRun[] {
  const sessionFromUrl = loadedRuns[0]?.sessionId
  if (!sessionFromUrl) return loadedRuns

  const prevRuns = useAgentStore.getState().runs
  const shouldMergeForkPrefix =
    prevRuns.some((r) => r.sessionId !== sessionFromUrl) &&
    prevRuns.some((r) => r.sessionId === sessionFromUrl)

  if (!shouldMergeForkPrefix) return loadedRuns

  const preserved = prevRuns.filter((r) => r.sessionId !== sessionFromUrl)
  const seen = new Set(preserved.map((r) => r.runId))
  const merged = [...preserved]
  for (const r of loadedRuns) {
    if (!seen.has(r.runId)) {
      merged.push(r)
      seen.add(r.runId)
    }
  }
  return merged
}
