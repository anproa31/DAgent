import { type FormEventHandler, useState, useEffect, useRef, useCallback } from 'react'
import { getRouteApi, useNavigate } from '@tanstack/react-router'
import { useSettings } from '@/context/settings-context'
import { useTableList } from '@/hooks/use-table-list'
import { useModelListByMode, type ModelInfo, type ActionStep, type ReportContent as ReportContentType } from '@/hooks/use-analysis'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ThemeSwitch } from '@/components/theme-switch'
import { Setting } from '@/components/setting'
import { WorkflowStepTracker, deriveStepStates } from '@/components/agents/WorkflowStepTracker'
import { AnalyzeBlock, CodeBlockStream, AnswerBlock } from '@/components/agents/MessageStream'
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
import { Button } from '@/components/ui/button'
import { Mic } from 'lucide-react'
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
  const isActive = run.phase !== 'idle' && run.phase !== 'done' && run.phase !== 'error'
  const showReport = run.phase === 'done' && run.content.length > 0
  const showError = run.phase === 'error'

  const stepStates = deriveStepStates(run.currentAgent, run.agentSteps, run.phase)

  const analyzeStatus = isActive && ['orchestrator', 'eda', 'insight'].includes(run.currentAgent)
    ? 'generating' as const
    : run.thinkingMessage || run.phase === 'done' ? 'done' as const : 'idle' as const

  const codeStatus = isActive && ['sql', 'code_executor'].includes(run.currentAgent)
    ? 'generating' as const
    : run.phase === 'done' ? 'done' as const : 'idle' as const

  const answerStatus = showReport
    ? 'done' as const
    : isActive && ['final_report', 'viz'].includes(run.currentAgent)
      ? 'generating' as const
      : 'idle' as const

  return (
    <div className='max-w-3xl mx-auto px-4 pt-2'>
      {/* User query bubble */}
      <div className='flex justify-end mb-4'>
        <div className='bg-primary text-primary-foreground rounded-2xl rounded-br-md px-4 py-2.5 max-w-[80%]'>
          <p className='text-sm'>{run.query}</p>
        </div>
      </div>

      {/* Workflow step tracker per run */}
      {isActive && (
        <WorkflowStepTracker stepStates={stepStates} className='mb-4' />
      )}

      {/* Accordion-style streaming blocks */}
      <div className='space-y-3'>
        <AnalyzeBlock
          content={run.thinkingMessage || ''}
          status={analyzeStatus}
        />

        {run.pendingSql && (
          <CodeBlockStream
            code={run.pendingSql}
            language='sql'
            status={codeStatus}
          />
        )}

        {showReport && (
          <AnswerBlock status={answerStatus}>
            <ReportContent
              content={run.content as ReportContentType[]}
              onShowSidePanel={onShowSidePanel}
              handleRedoClick={() => {}}
            />
          </AnswerBlock>
        )}

        {showError && (
          <div className='rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive'>
            {run.error}
          </div>
        )}
      </div>
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

        const reportPromises = sessionData.runs.map((r) =>
          getRunReport(r.run_id).then((report) => mapReportToAgentRun(r.run_id, sessionFromUrl, report))
        )
        const loadedRuns = await Promise.all(reportPromises)
        if (cancelled) return

        setRunsFromReports(loadedRuns)

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

  useEffect(() => {
    if (modelData?.models?.length && !model) {
      setModel(modelData.models[0].id)
    }
  }, [modelData, model])

  useEffect(() => {
    if (tables?.length && selectedTables.length === 0) {
      setSelectedTables(tables.map((t) => t.name))
    }
  }, [tables])

  const handleStop = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    setSubmitStatus('ready')
  }, [])

  const handleSubmit: FormEventHandler<HTMLFormElement> = useCallback(
    async (e) => {
      e.preventDefault()
      if (!query.trim()) return
      if (!tables?.length) {
        toast.error('Connect at least one table first.')
        return
      }

      esRef.current?.close()
      setSubmitStatus('submitted')

      try {
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

        addToHistory(currentSessionId, query.trim(), 'agent')

        if (!sessionFromUrl || sessionFromUrl !== currentSessionId) {
          navigate({ to: '/agents', search: { session: currentSessionId } })
        }

        setSubmitStatus('streaming')
        scrollToLatest()

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

  const inputBlock = (
    <AIInput onSubmit={handleSubmit} className='shadow-lg dark:shadow-accent-foreground/10 border border-border'>
      <AIInputTextarea
        onChange={(e) => setQuery(e.target.value)}
        value={query}
        placeholder='Describe your analysis task'
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
          <Button
            type='button'
            variant='ghost'
            size='icon'
            className='text-muted-foreground hover:text-foreground h-8 w-8'
            title='Voice input'
          >
            <Mic className='h-4 w-4' />
          </Button>
        </AIInputTools>
        <AIInputSubmit
          disabled={!isRunning && (!query.trim() || !model || !tables?.length)}
          status={isRunning ? 'streaming' : 'ready'}
          onStop={handleStop}
        />
      </AIInputToolbar>
    </AIInput>
  )

  return (
    <>
      {/* Header: "Assistant" title per spec */}
      <Header fixed>
        <div className='flex flex-col justify-center ml-2'>
          <span className='font-semibold text-sm leading-tight'>Assistant</span>
          <span className='text-[11px] text-muted-foreground leading-tight'>
            The center stages focused on chat, streaming analysis, and quick actions.
          </span>
        </div>
        <div className='ml-auto flex items-center space-x-4'>
          <ThemeSwitch />
          <Setting />
        </div>
      </Header>

      <Main className={`relative ${runs.length > 0 ? 'p-0 h-[calc(100vh-60px)]' : ''}`}>
        {runs.length === 0 ? (
          <div className='mx-auto max-w-4xl flex flex-col items-center pt-[calc(50vh-200px)] px-4'>
            <div className='mb-6 text-center'>
              <h1 className='text-4xl font-bold tracking-tight'>Assistant</h1>
              <p className='text-muted-foreground text-lg mt-2'>
                Ask a business question and let multiple AI agents collaborate to analyze your data.
              </p>
            </div>
            <div className='w-full max-w-3xl'>
              {inputBlock}
            </div>
          </div>
        ) : (
          <div className='relative h-full'>
            <div
              ref={scrollContainerRef}
              className='h-full overflow-auto pb-24'
            >
              <div className='space-y-6 mb-[100px] pt-4'>
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

            {/* Fixed bottom input */}
            <div className='sticky bottom-5 w-full flex justify-center px-4'>
              <div className='w-full max-w-3xl'>
                {inputBlock}
              </div>
            </div>
          </div>
        )}
      </Main>

      <SQLApprovalModal
        open={!!approvalRun}
        sql={approvalRun?.pendingSql ?? ''}
        explanation={approvalRun?.pendingSqlExplanation ?? ''}
        onApprove={handleApproveSQL}
        onReject={handleRejectSQL}
      />

      {sidePanelContent && (
        <div className='fixed top-16 bottom-0 right-0 z-40 flex w-[480px] min-w-0 flex-col overflow-hidden border-l bg-background shadow-xl'>
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
