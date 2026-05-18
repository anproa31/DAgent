import { type FormEventHandler, useState, useEffect, useRef, useCallback } from 'react'
import { getRouteApi, useNavigate } from '@tanstack/react-router'
import { useSettings } from '@/context/settings-context'
import { useTableList } from '@/hooks/use-table-list'
import { useModelListByMode, type ModelInfo, type ActionStep, type ReportContent as ReportContentType } from '@/hooks/use-analysis'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ThemeSwitch } from '@/components/theme-switch'
import { Setting } from '@/components/setting'
import { AgentProgressPanel } from '@/components/agents/AgentProgressPanel'
import { SQLApprovalModal } from '@/components/agents/SQLApprovalModal'
import { ReportContent } from '@/features/analysis-report/components/report-content'
import { SidePanel } from '@/features/analysis-report/components/side-panel'
import {
  AIInput,
  AIInputModelSelect,
  AIInputModelSelectContent,
  AIInputModelSelectItem,
  AIInputModelSelectTrigger,
  AIInputModelSelectValue,
  AIInputSubmit,
  AIInputTextarea,
  AIInputToolbar,
  AIInputTools,
  AIInputMultiSelectTable,
} from '@/components/ui/kibo-ui/ai-input'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { BrainCircuit } from 'lucide-react'
import {
  createSession,
  startRun,
  streamRun,
  approveSQL,
  rejectSQL,
  getRunReport,
  getSessionRuns,
} from '@/api/agentApi'
import type { RunReport } from '@/api/agentApi'
import { useSharedAnalysisHistory } from '@/context/analysis-history-context'
import { useAgentStore, type AgentRun, type RunPhase } from '@/stores/agentStore'

const agentsRouteApi = getRouteApi('/_authenticated/agents')

function mapReportToAgentRun(runId: string, sessionId: string, report: RunReport): AgentRun {
  let phase: RunPhase = 'running'
  if (report.done) {
    phase = report.error ? 'error' : 'done'
  } else if (report.pending_approval) {
    phase = 'awaiting_approval'
  }
  return {
    runId,
    sessionId,
    query: report.query,
    phase,
    currentAgent: report.current_agent || '',
    agentSteps: report.agent_steps ?? [],
    thinkingMessage: '',
    pendingSql: report.sql_draft ?? '',
    pendingSqlExplanation: report.sql_explanation ?? '',
    content: report.content ?? [],
    insights: report.insights ?? '',
    error: report.error ?? '',
  }
}

function AgentRunItem({
  run,
  onShowSidePanel,
}: {
  run: AgentRun
  onShowSidePanel: (c: { type: 'code' | 'table' | 'step'; content: string; stepData?: ActionStep }) => void
}) {
  const showProgress = run.phase !== 'idle' && run.phase !== 'done'
  const showReport = run.phase === 'done' && run.content.length > 0
  const showError = run.phase === 'error'

  return (
    <div className='max-w-3xl mx-auto p-4'>
      <p className='text-xs text-muted-foreground font-medium uppercase tracking-wide mb-2'>
        {run.query}
      </p>

      {showProgress && (
        <AgentProgressPanel
          phase={run.phase}
          currentAgent={run.currentAgent}
          agentSteps={run.agentSteps}
          thinkingMessage={run.thinkingMessage}
        />
      )}

      {showReport && (
        <ReportContent
          content={run.content as ReportContentType[]}
          onShowSidePanel={onShowSidePanel}
          handleRedoClick={() => {}}
        />
      )}

      {showError && (
        <div className='rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive'>
          {run.error}
        </div>
      )}
    </div>
  )
}

export default function AgentsPage() {
  const { baseUrl, apiKey } = useSettings()
  const { data: tables } = useTableList()
  const { data: modelData } = useModelListByMode(false)
  const { session: sessionFromUrl } = agentsRouteApi.useSearch()
  const navigate = useNavigate()
  const { addToHistory, setItemLoading } = useSharedAnalysisHistory()

  const [query, setQuery] = useState('')
  const [model, setModel] = useState('')
  const [selectedTables, setSelectedTables] = useState<string[]>([])
  const [submitStatus, setSubmitStatus] = useState<'ready' | 'submitted' | 'streaming'>('ready')

  const [sidePanelContent, setSidePanelContent] = useState<{
    type: 'code' | 'table' | 'step'
    content: string
    stepData?: ActionStep
  } | null>(null)

  const esRef = useRef<EventSource | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const latestItemRef = useRef<HTMLDivElement>(null)

  const {
    sessionId,
    runs,
    setSessionId,
    resetSession,
    addRun,
    setPhase,
    setThinking,
    handleAgentUpdate,
    handleSqlGenerated,
    handleDone,
    handleError,
    setRunsFromReports,
    setActiveRunId,
  } = useAgentStore()

  const approvalRun = runs.find((r: AgentRun) => r.phase === 'awaiting_approval') ?? null

  const scrollToLatest = useCallback(() => {
    setTimeout(() => {
      if (latestItemRef.current && scrollContainerRef.current) {
        const itemTop = latestItemRef.current.offsetTop
        scrollContainerRef.current.scrollTo({ top: itemTop, behavior: 'smooth' })
      }
    }, 300)
  }, [])

  // Load session from URL (deep-link / sidebar click)
  useEffect(() => {
    if (!sessionFromUrl) {
      esRef.current?.close()
      esRef.current = null
      resetSession()
      return
    }

    if (useAgentStore.getState().sessionId === sessionFromUrl && useAgentStore.getState().runs.length > 0) {
      return
    }

    let cancelled = false
    esRef.current?.close()
    esRef.current = null

    void (async () => {
      try {
        const sessionData = await getSessionRuns(sessionFromUrl)
        if (cancelled) return

        setSessionId(sessionFromUrl)

        if (sessionData.runs.length === 0) {
          setRunsFromReports([])
          return
        }

        // Load all run reports
        const reportPromises = sessionData.runs.map((r) =>
          getRunReport(r.run_id).then((report) => mapReportToAgentRun(r.run_id, sessionFromUrl, report))
        )
        const loadedRuns = await Promise.all(reportPromises)
        if (cancelled) return

        setRunsFromReports(loadedRuns)

        // If the last run is still in-progress, stream it
        const lastRun = loadedRuns[loadedRuns.length - 1]
        if (lastRun && lastRun.phase !== 'done' && lastRun.phase !== 'error') {
          setActiveRunId(lastRun.runId)
          setSubmitStatus('streaming')
          const es = streamRun(lastRun.runId, {
            onThinking: (d) => setThinking(lastRun.runId, d.message, d.agent),
            onAgentUpdate: (d) => handleAgentUpdate(lastRun.runId, d),
            onSqlGenerated: (d) => handleSqlGenerated(lastRun.runId, d),
            onDone: (d) => {
              handleDone(lastRun.runId, d)
              setItemLoading(sessionFromUrl, false)
              setSubmitStatus('ready')
            },
            onError: (d) => {
              handleError(lastRun.runId, d.message)
              toast.error(d.message)
              setItemLoading(sessionFromUrl, false)
              setSubmitStatus('ready')
            },
            onClose: () => {
              setSubmitStatus('ready')
              setItemLoading(sessionFromUrl, false)
            },
          })
          esRef.current = es
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
    }
  }, [sessionFromUrl])

  // Default model
  useEffect(() => {
    if (modelData?.models?.length && !model) {
      setModel(modelData.models[0].id)
    }
  }, [modelData, model])

  // Default tables
  useEffect(() => {
    if (tables?.length && selectedTables.length === 0) {
      setSelectedTables(tables.map((t) => t.name))
    }
  }, [tables])

  const handleSubmit: FormEventHandler<HTMLFormElement> = useCallback(
    async (e) => {
      e.preventDefault()
      if (!query.trim()) return
      if (!tables?.length) {
        toast.error('Connect at least one table first.')
        return
      }

      // Close any open SSE stream
      esRef.current?.close()
      setSubmitStatus('submitted')

      try {
        // If no session yet, create one
        let currentSessionId = sessionId
        if (!currentSessionId) {
          const sessionRes = await createSession()
          currentSessionId = sessionRes.session_id
          setSessionId(currentSessionId)
        }

        const { run_id, error: startError } = await startRun(currentSessionId, {
          query: query.trim(),
          tables: selectedTables,
          model,
          base_url: baseUrl,
          api_key: apiKey,
        })

        if (startError || !run_id) {
          toast.error(startError || 'Failed to start run')
          setSubmitStatus('ready')
          return
        }

        addRun(run_id, currentSessionId, query.trim())
        setQuery('')

        // Add/update sidebar history using session ID (not run ID)
        addToHistory(currentSessionId, query.trim(), 'agent')

        // Navigate with session param if not already there
        if (!sessionFromUrl || sessionFromUrl !== currentSessionId) {
          navigate({ to: '/agents', search: { session: currentSessionId } })
        }

        setSubmitStatus('streaming')
        scrollToLatest()

        // Open SSE stream
        const es = streamRun(run_id, {
          onThinking: (d) => setThinking(run_id, d.message, d.agent),
          onAgentUpdate: (d) => handleAgentUpdate(run_id, d),
          onSqlGenerated: (d) => handleSqlGenerated(run_id, d),
          onDone: (d) => {
            handleDone(run_id, d)
            setItemLoading(currentSessionId!, false)
            setSubmitStatus('ready')
          },
          onError: (d) => {
            handleError(run_id, d.message)
            toast.error(d.message)
            setItemLoading(currentSessionId!, false)
            setSubmitStatus('ready')
          },
          onClose: () => {
            setItemLoading(currentSessionId!, false)
            setSubmitStatus('ready')
          },
        })
        esRef.current = es
      } catch {
        toast.error('Failed to start analysis')
        setSubmitStatus('ready')
      }
    },
    [
      query,
      tables,
      sessionId,
      selectedTables,
      model,
      baseUrl,
      apiKey,
      sessionFromUrl,
      addRun,
      setThinking,
      handleAgentUpdate,
      handleSqlGenerated,
      handleDone,
      handleError,
      navigate,
      addToHistory,
      setItemLoading,
      setSessionId,
      scrollToLatest,
    ]
  )

  const handleApproveSQL = useCallback(
    async (editedSql: string) => {
      if (!approvalRun) return
      setPhase(approvalRun.runId, 'running')
      try {
        await approveSQL(approvalRun.runId, editedSql)
      } catch {
        toast.error('Failed to send approval')
      }
    },
    [approvalRun, setPhase]
  )

  const handleRejectSQL = useCallback(
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

  const isRunning = submitStatus !== 'ready'

  return (
    <>
      <Header fixed>
        <div className='flex items-center gap-2 ml-2'>
          <BrainCircuit className='h-5 w-5 text-primary' />
          <span className='font-semibold text-sm'>Multi-Agent Analytics</span>
          <Badge variant='secondary' className='text-xs'>Beta</Badge>
        </div>
        <div className='ml-auto flex items-center space-x-4'>
          <ThemeSwitch />
          <Setting />
        </div>
      </Header>

      <Main className={`relative ${runs.length > 0 ? 'p-0 h-[calc(100vh-60px)]' : ''}`}>
        {runs.length === 0 ? (
          /* Empty state — centered input like new-analysis page */
          <div className='mx-auto max-w-4xl flex flex-col items-center pt-[calc(50vh-200px)] px-4'>
            <div className='mb-6 text-center'>
              <h1 className='text-4xl font-bold tracking-tight'>Multi-Agent Analytics</h1>
              <p className='text-muted-foreground text-lg mt-2'>
                Ask a business question and let multiple AI agents collaborate to analyze your data.
              </p>
            </div>
            <div className='w-full max-w-3xl'>
              <AIInput onSubmit={handleSubmit}>
                <AIInputTextarea
                  onChange={(e) => setQuery(e.target.value)}
                  value={query}
                  placeholder='Ask a business question… e.g. "Which products had the highest revenue growth last month?"'
                  disabled={isRunning}
                />
                <AIInputToolbar>
                  <AIInputTools>
                    <AIInputModelSelect onValueChange={setModel} value={model}>
                      <AIInputModelSelectTrigger>
                        <AIInputModelSelectValue placeholder='Select a model'>
                          {model && modelData?.models?.find((m: ModelInfo) => m.id === model)?.name}
                        </AIInputModelSelectValue>
                      </AIInputModelSelectTrigger>
                      <AIInputModelSelectContent className='z-50'>
                        {modelData?.models?.map((m: ModelInfo) => (
                          <AIInputModelSelectItem key={m.id} value={m.id}>
                            {m.name}
                          </AIInputModelSelectItem>
                        ))}
                      </AIInputModelSelectContent>
                    </AIInputModelSelect>
                    <AIInputMultiSelectTable
                      options={(tables ?? []).map((t) => ({ value: t.name, label: t.name }))}
                      selected={selectedTables}
                      onSelectedChange={setSelectedTables}
                      placeholder='Select tables'
                    />
                  </AIInputTools>
                  <AIInputSubmit
                    disabled={!query.trim() || !model || !tables?.length || isRunning}
                    status={isRunning ? 'streaming' : 'ready'}
                  />
                </AIInputToolbar>
              </AIInput>
            </div>
          </div>
        ) : (
          /* Conversation view — all runs stacked with follow-up input at bottom */
          <div className='relative h-full'>
            <div
              ref={scrollContainerRef}
              className='h-full overflow-auto pb-24'
            >
              <div className='space-y-8 mb-[100px]'>
                {runs.map((run, index) => {
                  const isLast = index === runs.length - 1
                  return (
                    <div key={run.runId} ref={isLast ? latestItemRef : undefined}>
                      <AgentRunItem
                        run={run}
                        onShowSidePanel={(c) => setSidePanelContent(c)}
                      />
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Follow-up input — always at bottom */}
            <div className='sticky bottom-5 w-full flex justify-center px-4'>
              <div className='w-full max-w-3xl'>
                <AIInput onSubmit={handleSubmit} className='shadow-lg dark:shadow-accent-foreground/10 border border-border'>
                  <AIInputTextarea
                    onChange={(e) => setQuery(e.target.value)}
                    value={query}
                    placeholder='Ask a follow-up question…'
                    disabled={isRunning}
                  />
                  <AIInputToolbar>
                    <AIInputTools>
                      <AIInputModelSelect onValueChange={setModel} value={model}>
                        <AIInputModelSelectTrigger>
                          <AIInputModelSelectValue placeholder='Select a model'>
                            {model && modelData?.models?.find((m: ModelInfo) => m.id === model)?.name}
                          </AIInputModelSelectValue>
                        </AIInputModelSelectTrigger>
                        <AIInputModelSelectContent className='z-50'>
                          {modelData?.models?.map((m: ModelInfo) => (
                            <AIInputModelSelectItem key={m.id} value={m.id}>
                              {m.name}
                            </AIInputModelSelectItem>
                          ))}
                        </AIInputModelSelectContent>
                      </AIInputModelSelect>
                      <AIInputMultiSelectTable
                        options={(tables ?? []).map((t) => ({ value: t.name, label: t.name }))}
                        selected={selectedTables}
                        onSelectedChange={setSelectedTables}
                        placeholder='Select tables'
                      />
                    </AIInputTools>
                    <AIInputSubmit
                      disabled={!query.trim() || !model || !tables?.length || isRunning}
                      status={isRunning ? 'streaming' : 'ready'}
                    />
                  </AIInputToolbar>
                </AIInput>
              </div>
            </div>
          </div>
        )}
      </Main>

      {/* HITL SQL Approval modal */}
      <SQLApprovalModal
        open={!!approvalRun}
        sql={approvalRun?.pendingSql ?? ''}
        explanation={approvalRun?.pendingSqlExplanation ?? ''}
        onApprove={handleApproveSQL}
        onReject={handleRejectSQL}
      />

      {/* Side panel for code/table detail */}
      {sidePanelContent && (
        <div className='fixed inset-y-0 right-0 w-[480px] z-40 shadow-xl'>
          <SidePanel
            type={sidePanelContent.type}
            content={sidePanelContent.content}
            stepData={sidePanelContent.stepData}
            onClose={() => setSidePanelContent(null)}
          />
        </div>
      )}
    </>
  )
}
