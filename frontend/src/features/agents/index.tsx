import { type FormEventHandler, useState, useEffect, useRef, useCallback } from 'react'
import { getRouteApi, useNavigate } from '@tanstack/react-router'
import { useSettings } from '@/context/settings-context'
import { useTableList } from '@/hooks/use-table-list'
import { useModelListByMode, type ModelInfo, type ActionStep, type ReportContent as ReportContentType } from '@/hooks/use-analysis'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ThemeSwitch } from '@/components/theme-switch'
import { Setting } from '@/components/setting'
import { WorkflowStepTracker, deriveVisibleSteps } from '@/components/agents/WorkflowStepTracker'
import { AnalyzeBlock, CodeBlockStream, AnswerBlock, StreamingAnswerBlock } from '@/components/agents/MessageStream'
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
import { Textarea } from '@/components/ui/textarea'
import { Mic, Pencil, Check, X } from 'lucide-react'
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
    streamingAnswer: '',
    content: report.content ?? [],
    insights: report.insights ?? '',
    error: report.error ?? '',
  }
}

function AgentRunItem({
  run,
  runIndex,
  onShowSidePanel,
  onEditPrompt,
  onBeginEditPrompt,
  canEdit,
}: {
  run: AgentRun
  runIndex: number
  onShowSidePanel: (c: { type: 'code' | 'table' | 'step'; content: string; stepData?: ActionStep }) => void
  onEditPrompt: (params: { index: number; query: string }) => Promise<void> | void
  /** Called before opening the edit UI — stops streaming so the chat is idle while editing. */
  onBeginEditPrompt?: () => void
  canEdit: boolean
}) {
  const isActive =
    run.phase !== 'idle' &&
    run.phase !== 'done' &&
    run.phase !== 'error' &&
    run.phase !== 'stopped'
  const showReport = run.phase === 'done' && run.content.length > 0
  const showError = run.phase === 'error'

  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(run.query)

  const visibleSteps = deriveVisibleSteps(run.currentAgent, run.agentSteps, run.phase)

  const analyzeStatus =
    isActive && ['orchestrator', 'eda', 'insight'].includes(run.currentAgent)
      ? ('generating' as const)
      : run.thinkingMessage || run.phase === 'done' || run.phase === 'stopped'
        ? ('done' as const)
        : ('idle' as const)

  const codeStatus =
    isActive && ['sql', 'code_executor'].includes(run.currentAgent)
      ? ('generating' as const)
      : run.phase === 'done' || run.phase === 'stopped'
        ? ('done' as const)
        : ('idle' as const)

  const answerStatus = showReport
    ? 'done' as const
    : isActive && (['final_report', 'viz'].includes(run.currentAgent) || run.streamingAnswer.length > 0)
      ? 'generating' as const
      : 'idle' as const

  const startEditing = () => {
    onBeginEditPrompt?.()
    setEditValue(run.query)
    setIsEditing(true)
  }

  const cancelEditing = () => {
    setIsEditing(false)
    setEditValue(run.query)
  }

  const submitEdit = async () => {
    const trimmed = editValue.trim()
    if (!trimmed || trimmed === run.query) {
      cancelEditing()
      return
    }
    setIsEditing(false)
    await onEditPrompt({ index: runIndex, query: trimmed })
  }

  const handleEditKeyDown = async (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      await submitEdit()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      cancelEditing()
    }
  }

  return (
    <div className='max-w-3xl mx-auto px-4 pt-2'>
      {/* User query bubble */}
      <div className='group flex justify-end mb-4 gap-2'>
        {canEdit && !isEditing && (
          <Button
            variant='ghost'
            size='icon'
            onClick={startEditing}
            className='self-center h-8 w-8 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity'
            aria-label='Edit prompt'
            title='Edit prompt'
          >
            <Pencil className='h-3.5 w-3.5' />
          </Button>
        )}

        {isEditing ? (
          <div className='w-full max-w-[80%]'>
            <Textarea
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={handleEditKeyDown}
              autoFocus
              rows={Math.min(8, Math.max(2, editValue.split('\n').length))}
              className='w-full text-sm resize-none rounded-2xl rounded-br-md border-border focus-visible:ring-1 focus-visible:ring-primary/50'
              aria-label='Edit prompt'
            />
            <div className='mt-1.5 flex items-center justify-end gap-2'>
              <p className='text-[11px] text-muted-foreground mr-auto'>
                Enter to send · Shift+Enter for new line · Esc to cancel
              </p>
              <Button
                variant='outline'
                size='sm'
                className='h-7 gap-1 text-xs'
                onClick={cancelEditing}
              >
                <X className='h-3 w-3' /> Cancel
              </Button>
              <Button
                size='sm'
                className='h-7 gap-1 text-xs'
                onClick={submitEdit}
                disabled={!editValue.trim()}
              >
                <Check className='h-3 w-3' /> Save & regenerate
              </Button>
            </div>
          </div>
        ) : (
          <div className='bg-primary text-primary-foreground rounded-2xl rounded-br-md px-4 py-2.5 max-w-[80%]'>
            <p className='text-sm whitespace-pre-wrap break-words'>{run.query}</p>
          </div>
        )}
      </div>

      {/* Workflow step tracker per run — reveals each step the orchestrator
          actually runs, as it runs (no fixed pipeline). */}
      {isActive && visibleSteps.length > 0 && (
        <WorkflowStepTracker steps={visibleSteps} className='mb-4' />
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

        {/* Live token/chunk streaming of the final answer while running */}
        {isActive && run.streamingAnswer && (
          <StreamingAnswerBlock content={run.streamingAnswer} status='generating' />
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
  const { addToHistory, setItemLoading, replaceAgentHistorySession } = useSharedAnalysisHistory()

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
    preferredModel,
    setPreferredModel,
    setSessionId,
    resetSession,
    addRun,
    setPhase,
    setThinking,
    handleAgentUpdate,
    handleSqlGenerated,
    handleAnswerChunk,
    handleDone,
    handleError,
    cancelRun,
    truncateRunsAfter,
    setRunsFromReports,
    setActiveRunId,
    setSessionTables,
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

    const storeSnap = useAgentStore.getState()

    const savedTables = storeSnap.sessionTables[sessionFromUrl]
    if (savedTables?.length) {
      setSelectedTables(savedTables)
    }

    const runsMatchSession =
      storeSnap.runs.length > 0 &&
      storeSnap.sessionId === sessionFromUrl &&
      storeSnap.runs.every((r: AgentRun) => r.sessionId === sessionFromUrl)

    if (runsMatchSession) {
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
          const prevRuns = useAgentStore.getState().runs
          const forkMerge =
            prevRuns.some((r: AgentRun) => r.sessionId !== sessionFromUrl) &&
            prevRuns.some((r: AgentRun) => r.sessionId === sessionFromUrl)
          setRunsFromReports(forkMerge ? prevRuns : [])
          return
        }

        // Filter out runs the user previously cancelled — never reattach SSE to them.
        const { isCancelled } = useAgentStore.getState()
        const activeSessionRuns = sessionData.runs.filter((r) => !isCancelled(r.run_id))

        if (activeSessionRuns.length === 0) {
          const prevRuns = useAgentStore.getState().runs
          const forkMerge =
            prevRuns.some((r: AgentRun) => r.sessionId !== sessionFromUrl) &&
            prevRuns.some((r: AgentRun) => r.sessionId === sessionFromUrl)
          setRunsFromReports(forkMerge ? prevRuns : [])
          setItemLoading(sessionFromUrl, false)
          setSubmitStatus('ready')
          return
        }

        const reportPromises = activeSessionRuns.map((r) =>
          getRunReport(r.run_id).then((report) => mapReportToAgentRun(r.run_id, sessionFromUrl, report))
        )
        const loadedRuns = await Promise.all(reportPromises)
        if (cancelled) return

        const prevRuns = useAgentStore.getState().runs
        const shouldMergeForkPrefix =
          prevRuns.some((r: AgentRun) => r.sessionId !== sessionFromUrl) &&
          prevRuns.some((r: AgentRun) => r.sessionId === sessionFromUrl)

        let mergedRuns = loadedRuns
        if (shouldMergeForkPrefix) {
          const preserved = prevRuns.filter((r: AgentRun) => r.sessionId !== sessionFromUrl)
          const seen = new Set(preserved.map((r: AgentRun) => r.runId))
          mergedRuns = [...preserved]
          for (const r of loadedRuns) {
            if (!seen.has(r.runId)) {
              mergedRuns.push(r)
              seen.add(r.runId)
            }
          }
        }

        setRunsFromReports(mergedRuns)

        const lastRun = loadedRuns[loadedRuns.length - 1]
        const lastIsCancelled = lastRun ? isCancelled(lastRun.runId) : false
        if (lastRun && !lastIsCancelled && lastRun.phase !== 'done' && lastRun.phase !== 'error' && lastRun.phase !== 'stopped') {
          setActiveRunId(lastRun.runId)
          setSubmitStatus('streaming')
          const es = streamRun(lastRun.runId, {
            onThinking: (d) => setThinking(lastRun.runId, d.message, d.agent),
            onAgentUpdate: (d) => handleAgentUpdate(lastRun.runId, d),
            onSqlGenerated: (d) => handleSqlGenerated(lastRun.runId, d),
            onAnswerChunk: (d) => handleAnswerChunk(lastRun.runId, d),
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

  useEffect(() => {
    if (tables?.length && selectedTables.length === 0) {
      const storeSnap = useAgentStore.getState()
      const saved = sessionFromUrl
        ? storeSnap.sessionTables[sessionFromUrl]
        : undefined
      setSelectedTables(saved?.length ? saved : tables.map((t) => t.name))
    }
  }, [tables])

  /**
   * Resolve the run id the stop controls should target.
   * Falls back to the latest still-active run when `activeRunId` was cleared
   * (e.g. after an SSE close).
   */
  const resolveActiveRunId = useCallback((): string | null => {
    const { activeRunId, runs } = useAgentStore.getState()
    if (activeRunId) return activeRunId
    return (
      [...runs]
        .reverse()
        .find((r: AgentRun) =>
          ['starting', 'thinking', 'running', 'awaiting_approval'].includes(r.phase)
        )?.runId ?? null
    )
  }, [])

  /** Stop button: silently close the stream and drop the in-flight run from the chat. */
  const handleStop = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    setSubmitStatus('ready')

    const targetRunId = resolveActiveRunId()
    if (targetRunId) cancelRun(targetRunId, { dropRun: true })

    const sid = sessionFromUrl ?? useAgentStore.getState().sessionId
    if (sid) setItemLoading(sid, false)
  }, [sessionFromUrl, setItemLoading, cancelRun, resolveActiveRunId])

  /**
   * Stop-for-edit: close the stream and clear in-flight generation but keep
   * the run object so the inline edit textarea stays mounted in its bubble.
   */
  const handleStopForEdit = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    setSubmitStatus('ready')

    const targetRunId = resolveActiveRunId()
    if (targetRunId) cancelRun(targetRunId, { dropRun: false })

    const sid = sessionFromUrl ?? useAgentStore.getState().sessionId
    if (sid) setItemLoading(sid, false)
  }, [sessionFromUrl, setItemLoading, cancelRun, resolveActiveRunId])

  // Shared start-run helper used by both the composer submit and the
  // edit-previous-prompt flow. Truncating older runs is handled by the
  // caller before invoking this.
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

        if (opts?.replaceHistorySessionId) {
          const sessionRes = await createSession()
          currentSessionId = sessionRes.session_id
          setSessionId(currentSessionId)
          replaceAgentHistorySession(
            opts.replaceHistorySessionId,
            currentSessionId,
            trimmed
          )
        } else {
          currentSessionId = sessionId ?? ''
          if (!currentSessionId) {
            const sessionRes = await createSession()
            currentSessionId = sessionRes.session_id
            setSessionId(currentSessionId)
          }
        }

        const { run_id, error: startError } = await startRun(currentSessionId, {
          query: trimmed,
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

        setSessionTables(currentSessionId, selectedTables)
        addRun(run_id, currentSessionId, trimmed)

        if (!opts?.replaceHistorySessionId) {
          addToHistory(currentSessionId, trimmed, 'agent')
        }

        if (!sessionFromUrl || sessionFromUrl !== currentSessionId) {
          navigate({ to: '/agents', search: { session: currentSessionId } })
        }

        setSubmitStatus('streaming')
        scrollToLatest()

        const es = streamRun(run_id, {
          onThinking: (d) => setThinking(run_id, d.message, d.agent),
          onAgentUpdate: (d) => handleAgentUpdate(run_id, d),
          onSqlGenerated: (d) => handleSqlGenerated(run_id, d),
          onAnswerChunk: (d) => handleAnswerChunk(run_id, d),
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
      handleAnswerChunk,
      handleDone,
      handleError,
      navigate,
      addToHistory,
      replaceAgentHistorySession,
      setItemLoading,
      setSessionId,
      setSessionTables,
      scrollToLatest,
    ]
  )

  const handleSubmit: FormEventHandler<HTMLFormElement> = useCallback(
    async (e) => {
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
      truncateRunsAfter(index)

      const previousSessionId = sessionFromUrl ?? sessionId ?? ''
      await runQuery(
        trimmed,
        previousSessionId
          ? { replaceHistorySessionId: previousSessionId }
          : undefined
      )
    },
    [runQuery, truncateRunsAfter, sessionFromUrl, sessionId]
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
          <AIInputModelSelect onValueChange={handleModelChange} value={model}>
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
