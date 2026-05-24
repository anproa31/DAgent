import { useState, useEffect, useRef, useCallback } from 'react'
import { getRouteApi, useNavigate } from '@tanstack/react-router'
import { useSettings } from '@/context/settings-context'
import { useTableList } from '@/hooks/use-table-list'
import { useModelListByMode, type ModelInfo } from '@/hooks/use-analysis'
import { useKbDocuments, useSkills } from '@/hooks/use-memory'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { SQLApprovalModal } from '@/components/agents/SQLApprovalModal'
import { PythonApprovalModal } from '@/components/agents/PythonApprovalModal'
import { WebDatasourceApprovalModal } from '@/components/agents/WebDatasourceApprovalModal'
import { SidePanel, type SidePanelContent } from '@/features/analysis-report/components/side-panel'
import { toast } from 'sonner'
import {
  createSession,
  startRun,
  streamRun,
  approveSQL,
  rejectSQL,
  generateTitle,
  stopRun,
} from '@/services/api/agent'
import { useSharedAnalysisHistory } from '@/context/analysis-history-context'
import { useAgentStore, type AgentRun } from '@/stores/agentStore'
import { AnalysisPresets } from '@/features/agents/analysis-presets'
import { AgentRunItem } from '@/features/agents/components/AgentRunItem'
import { AgentComposer } from '@/features/agents/components/AgentComposer'
import { useAgentSessionLoader } from '@/features/agents/hooks/use-agent-session-loader'
import { useAgentStreamHandlers } from '@/features/agents/hooks/use-agent-stream-handlers'

const agentsRouteApi = getRouteApi('/_authenticated/agents')

export default function AgentsPage() {
  const { baseUrl, apiKey, embeddingBaseUrl, embeddingModel } = useSettings()
  const { data: tables } = useTableList()
  const { data: modelData } = useModelListByMode(false)
  const { data: kbDocuments } = useKbDocuments()
  const { data: skills } = useSkills()
  const { session: sessionFromUrl } = agentsRouteApi.useSearch()
  const navigate = useNavigate()
  const {
    addToHistory,
    setItemLoading,
    replaceAgentHistorySession,
    updateHistoryTitle,
    refreshAgentSessionsFromServer,
  } = useSharedAnalysisHistory()

  const [query, setQuery] = useState('')
  const [model, setModel] = useState('')
  const [selectedTables, setSelectedTables] = useState<string[]>([])
  const [selectedKb, setSelectedKb] = useState<string[]>([])
  const [selectedSkills, setSelectedSkills] = useState<string[]>([])
  const [submitStatus, setSubmitStatus] = useState<'ready' | 'submitted' | 'streaming'>('ready')
  const [sidePanelContent, setSidePanelContent] = useState<SidePanelContent | null>(null)

  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const latestItemRef = useRef<HTMLDivElement>(null)

  const {
    sessionId,
    runs,
    preferredModel,
    setPreferredModel,
    setSessionId,
    addRun,
    setPhase,
    cancelRun,
    truncateRunsAfter,
    setSessionTables,
    updatePendingSql,
  } = useAgentStore()

  const { buildHandlers } = useAgentStreamHandlers()
  const { esRef } = useAgentSessionLoader({
    sessionFromUrl,
    onTablesRestored: setSelectedTables,
    updateHistoryTitle,
    refreshAgentSessionsFromServer,
    setItemLoading,
    setSubmitStatus,
  })

  const approvalRun = runs.find((r: AgentRun) => r.phase === 'awaiting_approval') ?? null

  const scrollToLatest = useCallback(() => {
    setTimeout(() => {
      if (latestItemRef.current && scrollContainerRef.current) {
        const itemTop = latestItemRef.current.offsetTop
        scrollContainerRef.current.scrollTo({ top: itemTop, behavior: 'smooth' })
      }
    }, 300)
  }, [])

  const scheduleSessionTitleUpdate = useCallback(
    (sessionIdForTitle: string, queryText: string) => {
      void generateTitle({
        query: queryText,
        model,
        base_url: baseUrl,
        api_key: apiKey,
      }).then((title) => {
        updateHistoryTitle(sessionIdForTitle, title)
      })
    },
    [model, baseUrl, apiKey, updateHistoryTitle]
  )

  useEffect(() => {
    if (!modelData?.models?.length) return
    const available = modelData.models
    const currentIsValid = model && available.some((m: ModelInfo) => m.id === model)
    if (currentIsValid) return

    const preferredIsValid =
      preferredModel && available.some((m: ModelInfo) => m.id === preferredModel)
    setModel(preferredIsValid ? preferredModel : available[0].id)
  }, [modelData, model, preferredModel])

  const handleModelChange = useCallback(
    (next: string) => {
      setModel(next)
      setPreferredModel(next)
    },
    [setPreferredModel]
  )

  const handleApplyPreset = useCallback(
    ({ prompt, tables: presetTables }: { prompt: string; tables: string[] }) => {
      setQuery(prompt)
      setSelectedTables(presetTables)
    },
    []
  )

  useEffect(() => {
    if (tables?.length && selectedTables.length === 0) {
      const storeSnap = useAgentStore.getState()
      const saved = sessionFromUrl
        ? storeSnap.sessionTables[sessionFromUrl]
        : undefined
      setSelectedTables(saved?.length ? saved : tables.map((t) => t.name))
    }
  }, [tables, sessionFromUrl, selectedTables.length])

  useEffect(() => {
    setSidePanelContent(null)
  }, [sessionFromUrl])

  useEffect(() => {
    if (!sidePanelContent || !('runId' in sidePanelContent)) return
    const runExists = runs.some((r) => r.runId === sidePanelContent.runId)
    if (!runExists) setSidePanelContent(null)
  }, [runs, sidePanelContent])

  const resolveActiveRunId = useCallback((): string | null => {
    const { activeRunId, runs: storeRuns } = useAgentStore.getState()
    if (activeRunId) return activeRunId
    return (
      [...storeRuns]
        .reverse()
        .find((r: AgentRun) =>
          ['starting', 'thinking', 'running', 'awaiting_approval'].includes(r.phase)
        )?.runId ?? null
    )
  }, [])

  const handleStop = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    setSubmitStatus('ready')
    const targetRunId = resolveActiveRunId()
    if (targetRunId) cancelRun(targetRunId, { dropRun: true })
    const sid = sessionFromUrl ?? useAgentStore.getState().sessionId
    if (sid) setItemLoading(sid, false)
  }, [sessionFromUrl, setItemLoading, cancelRun, resolveActiveRunId, esRef])

  const handleStopForEdit = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    setSubmitStatus('ready')
    const targetRunId = resolveActiveRunId()
    if (targetRunId) cancelRun(targetRunId, { dropRun: false })
    const sid = sessionFromUrl ?? useAgentStore.getState().sessionId
    if (sid) setItemLoading(sid, false)
  }, [sessionFromUrl, setItemLoading, cancelRun, resolveActiveRunId, esRef])

  const runQuery = useCallback(
    async (
      rawQuery: string,
      opts?: { replaceHistorySessionId?: string }
    ) => {
      const trimmed = rawQuery.trim()
      if (!trimmed) return
      if (!tables?.length) {
        toast.error('Connect at least one table first.')
        return
      }

      esRef.current?.close()
      esRef.current = null
      setSubmitStatus('submitted')

      try {
        let currentSessionId: string
        let createdNewSession = false

        if (opts?.replaceHistorySessionId) {
          const sessionRes = await createSession()
          currentSessionId = sessionRes.session_id
          setSessionId(currentSessionId)
          createdNewSession = true
        } else {
          currentSessionId = sessionId ?? ''
          if (!currentSessionId) {
            const sessionRes = await createSession()
            currentSessionId = sessionRes.session_id
            setSessionId(currentSessionId)
            createdNewSession = true
          }
        }

        const { run_id, error: startError } = await startRun(currentSessionId, {
          query: trimmed,
          tables: selectedTables,
          model,
          base_url: baseUrl,
          api_key: apiKey,
          kb_documents: selectedKb,
          skill_ids: selectedSkills,
          embedding_base_url: embeddingBaseUrl,
          embedding_model: embeddingModel,
        })

        if (startError || !run_id) {
          toast.error(startError || 'Failed to start run')
          setSubmitStatus('ready')
          return
        }

        setSessionTables(currentSessionId, selectedTables)
        addRun(run_id, currentSessionId, trimmed)

        if (createdNewSession) {
          setSidePanelContent(null)
          if (opts?.replaceHistorySessionId) {
            replaceAgentHistorySession(
              opts.replaceHistorySessionId,
              currentSessionId,
              trimmed
            )
          } else {
            addToHistory(currentSessionId, trimmed, 'agent')
          }
          scheduleSessionTitleUpdate(currentSessionId, trimmed)
        }

        if (!sessionFromUrl || sessionFromUrl !== currentSessionId) {
          navigate({ to: '/agents', search: { session: currentSessionId } })
        }

        setSubmitStatus('streaming')
        scrollToLatest()

        esRef.current = streamRun(
          run_id,
          buildHandlers({
            runId: run_id,
            sessionId: currentSessionId,
            onTitleUpdated: updateHistoryTitle,
            setSubmitStatus,
            setItemLoading,
            refreshSessions: refreshAgentSessionsFromServer,
          })
        )
      } catch {
        toast.error('Failed to start analysis')
        setSubmitStatus('ready')
      }
    },
    [
      tables,
      sessionId,
      selectedTables,
      selectedKb,
      selectedSkills,
      model,
      baseUrl,
      apiKey,
      embeddingBaseUrl,
      embeddingModel,
      sessionFromUrl,
      addRun,
      navigate,
      addToHistory,
      replaceAgentHistorySession,
      updateHistoryTitle,
      refreshAgentSessionsFromServer,
      scheduleSessionTitleUpdate,
      setItemLoading,
      setSessionId,
      setSessionTables,
      scrollToLatest,
      buildHandlers,
      esRef,
    ]
  )

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault()
      if (!query.trim()) return
      const text = query.trim()
      setQuery('')
      await runQuery(text)
    },
    [query, runQuery]
  )

  const handleEditPrompt = useCallback(
    async ({ index, query: edited }: { index: number; query: string }) => {
      const trimmed = edited.trim()
      if (!trimmed) return

      esRef.current?.close()
      esRef.current = null
      setSubmitStatus('ready')

      const runsToStop = runs.slice(index)
      await Promise.all(runsToStop.map((r) => stopRun(r.runId).catch(() => {})))
      truncateRunsAfter(index)

      const previousSessionId = sessionFromUrl ?? sessionId ?? ''
      await runQuery(
        trimmed,
        previousSessionId
          ? { replaceHistorySessionId: previousSessionId }
          : undefined
      )
    },
    [runs, runQuery, truncateRunsAfter, sessionFromUrl, sessionId, esRef]
  )

  const handleApproveSQL = useCallback(
    async (editedSql: string) => {
      if (!approvalRun) return
      updatePendingSql(approvalRun.runId, editedSql)
      setPhase(approvalRun.runId, 'running')
      try {
        await approveSQL(approvalRun.runId, editedSql)
      } catch {
        toast.error('Failed to send approval')
      }
    },
    [approvalRun, setPhase, updatePendingSql]
  )

  const handleRejectSQL = useCallback(
    async (reason: string, sql: string) => {
      if (!approvalRun) return
      setPhase(approvalRun.runId, 'running')
      try {
        await rejectSQL(approvalRun.runId, reason, sql)
      } catch {
        toast.error('Failed to send rejection')
      }
    },
    [approvalRun, setPhase]
  )

  const handleApprovePython = useCallback(
    async (editedCode: string) => {
      if (!approvalRun) return
      setPhase(approvalRun.runId, 'running')
      try {
        await approveSQL(approvalRun.runId, undefined, { code: editedCode })
      } catch {
        toast.error('Failed to send approval')
      }
    },
    [approvalRun, setPhase]
  )

  const handleRejectPython = useCallback(
    async (reason: string, code: string) => {
      if (!approvalRun) return
      setPhase(approvalRun.runId, 'running')
      try {
        await rejectSQL(approvalRun.runId, reason, undefined, undefined, code)
      } catch {
        toast.error('Failed to send rejection')
      }
    },
    [approvalRun, setPhase]
  )

  const handleRejectWebDatasource = useCallback(
    async (reason: string) => {
      if (!approvalRun) return
      setPhase(approvalRun.runId, 'running')
      try {
        await rejectSQL(approvalRun.runId, reason)
      } catch {
        toast.error('Failed to send rejection')
      }
    },
    [approvalRun, setPhase]
  )

  const handleApproveWebDatasource = useCallback(
    async (selectedUrls: string[], name?: string) => {
      if (!approvalRun) return
      setPhase(approvalRun.runId, 'running')
      try {
        await approveSQL(approvalRun.runId, undefined, {
          selected_urls: selectedUrls,
          name,
        })
      } catch {
        toast.error('Failed to send approval')
      }
    },
    [approvalRun, setPhase]
  )

  const hasActiveRun = runs.some(
    (r) =>
      r.sessionId === (sessionFromUrl ?? sessionId) &&
      ['starting', 'thinking', 'running', 'awaiting_approval'].includes(r.phase)
  )
  const isRunning = submitStatus !== 'ready' || hasActiveRun
  const models = modelData?.models ?? []
  const tableOptions = (tables ?? []).map((t) => ({ value: t.name, label: t.name }))
  const kbOptions = (kbDocuments ?? []).map((d) => ({ value: d, label: d }))
  const skillOptions = (skills ?? []).map((s) => ({ value: s.skill_id, label: s.name }))
  const canSubmit = !!query.trim() && !!model

  const composer = (
    <AgentComposer
      query={query}
      onQueryChange={setQuery}
      model={model}
      onModelChange={handleModelChange}
      models={models}
      tableOptions={tableOptions}
      selectedTables={selectedTables}
      onSelectedTablesChange={setSelectedTables}
      kbOptions={kbOptions}
      selectedKb={selectedKb}
      onSelectedKbChange={setSelectedKb}
      skillOptions={skillOptions}
      selectedSkills={selectedSkills}
      onSelectedSkillsChange={setSelectedSkills}
      isRunning={isRunning}
      canSubmit={canSubmit}
      onSubmit={handleSubmit}
      onStop={handleStop}
    />
  )

  return (
    <>
      <Header fixed>
        <div className='flex flex-col justify-center'>
          <span className='font-semibold text-sm leading-tight'>Assistant</span>
          <span className='text-[11px] text-muted-foreground leading-tight'>
            The center stages focused on chat, streaming analysis, and quick actions.
          </span>
        </div>
      </Header>

      <Main
        className={`relative ${runs.length > 0 ? 'flex min-h-0 p-0 h-[calc(100vh-60px)] overflow-hidden' : ''} ${sidePanelContent ? 'flex-row' : ''}`}
      >
        {runs.length === 0 ? (
          <div className='mx-auto max-w-4xl flex flex-col items-center pt-[calc(50vh-200px)] px-4'>
            <div className='mb-6 text-center'>
              <h1 className='text-4xl font-bold tracking-tight'>Assistant</h1>
              <p className='text-muted-foreground text-lg mt-2'>
                Ask a business question and let multiple AI agents collaborate to analyze your data.
              </p>
            </div>
            <div className='w-full max-w-3xl'>
              <AnalysisPresets
                availableTableNames={(tables ?? []).map((t) => t.name)}
                onApply={handleApplyPreset}
                disabled={isRunning}
              />
              {composer}
            </div>
          </div>
        ) : (
          <>
            <div className='relative flex min-h-0 min-w-0 flex-1 flex-col'>
              <div ref={scrollContainerRef} className='min-h-0 flex-1 overflow-auto pb-24'>
                <div className='space-y-6 mb-[100px] pt-4'>
                  {runs.map((run, index) => {
                    const isLast = index === runs.length - 1
                    return (
                      <div key={run.runId} ref={isLast ? latestItemRef : undefined}>
                        <AgentRunItem
                          run={run}
                          runIndex={index}
                          onShowSidePanel={(c) => setSidePanelContent(c)}
                          onEditPrompt={handleEditPrompt}
                          onBeginEditPrompt={handleStopForEdit}
                          canEdit
                        />
                      </div>
                    )
                  })}
                </div>
              </div>

              <div className='sticky bottom-5 w-full shrink-0 flex justify-center px-4'>
                <div className='w-full max-w-3xl'>{composer}</div>
              </div>
            </div>

            {sidePanelContent && (
              <div className='flex h-full w-[min(50%,560px)] min-w-[320px] shrink-0 flex-col overflow-hidden border-l bg-muted/30'>
                <SidePanel
                  type={sidePanelContent.type}
                  content={'content' in sidePanelContent ? sidePanelContent.content : ''}
                  stepData={
                    sidePanelContent.type === 'step' ? sidePanelContent.stepData : undefined
                  }
                  runId={'runId' in sidePanelContent ? sidePanelContent.runId : undefined}
                  executionId={
                    sidePanelContent.type === 'execution'
                      ? sidePanelContent.executionId
                      : undefined
                  }
                  onClose={() => setSidePanelContent(null)}
                />
              </div>
            )}
          </>
        )}
      </Main>

      <SQLApprovalModal
        open={!!approvalRun && approvalRun.approvalKind === 'sql'}
        sql={approvalRun?.pendingSql ?? ''}
        explanation={approvalRun?.pendingSqlExplanation ?? ''}
        onApprove={handleApproveSQL}
        onReject={handleRejectSQL}
      />

      <PythonApprovalModal
        open={!!approvalRun && approvalRun.approvalKind === 'python'}
        code={approvalRun?.pendingPythonCode ?? ''}
        risk={approvalRun?.pendingPythonRisk ?? ''}
        onApprove={handleApprovePython}
        onReject={handleRejectPython}
      />

      <WebDatasourceApprovalModal
        open={!!approvalRun && approvalRun.approvalKind === 'web_datasource'}
        proposal={approvalRun?.pendingWebProposal ?? null}
        onApprove={handleApproveWebDatasource}
        onReject={handleRejectWebDatasource}
      />
    </>
  )
}
