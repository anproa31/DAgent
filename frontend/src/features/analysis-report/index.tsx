import { useParams } from '@tanstack/react-router'
import { useState, useEffect, useRef, useCallback } from 'react'
import Split from 'react-split'
import { Main } from '@/components/layout/main'
import { Header } from '@/components/layout/header'
import { ThemeSwitch } from '@/components/theme-switch'
import { Setting } from '@/components/setting'
import { LoaderCircle, AlertCircle, Pencil, Copy, Check } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useReport, useGetSpace, type ActionStep } from '@/hooks/use-analysis'
import { ReportContent } from './components/report-content'
import { SidePanel } from './components/side-panel'
import { motion, AnimatePresence } from 'framer-motion'
import FollowupInput from './components/followup-input'
import { useSharedAnalysisHistory } from '@/context/analysis-history-context'
import { useStartAnalysis, useModelListByMode, useStopAnalysis, type ModelInfo } from '@/hooks/use-analysis'
import { useQueryClient } from '@tanstack/react-query'
import { useTableList } from '@/hooks/use-table-list'
import { toast } from 'sonner'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'
// Type definitions
interface SidePanelContentType {
  type: 'code' | 'table' | 'step'
  content: string
  stepData?: ActionStep
}


// Component for displaying an individual analysis report
function AnalysisReportItem({ 
  analysisId, 
  onShowSidePanel,
  itemRef,
  setIsProcessing,
  analysisIndex,
  onEditSubmit,
  isGlobalSubmitting,
  onStop,
}: { 
  analysisId: string
  onShowSidePanel: (content: SidePanelContentType) => void 
  itemRef?: React.RefObject<HTMLDivElement | null>
  setIsProcessing?: React.Dispatch<React.SetStateAction<boolean>>
  analysisIndex: number
  onEditSubmit: (params: { query: string; index: number }) => Promise<void>
  isGlobalSubmitting: boolean
  onStop?: () => void
}) {
  const { data: report, isLoading, error } = useReport(analysisId)

  setIsProcessing?.(isLoading || !report?.done)

  const isStopped = report?.error === "Generation stopped by user."

  // Added: copy state management
  const [copyState, setCopyState] = useState<'idle' | 'success' | 'error'>('idle')
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState('')
  const editTextareaRef = useRef<HTMLTextAreaElement | null>(null)

  const adjustEditTextareaHeight = useCallback(() => {
    const textarea = editTextareaRef.current
    if (!textarea) return
    const minHeight = 56
    const maxHeight = 320
    textarea.style.height = `${minHeight}px`
    const newHeight = Math.max(
      minHeight,
      Math.min(textarea.scrollHeight, maxHeight)
    )
    textarea.style.height = `${newHeight}px`
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
  }, [])

  // Auto-enter edit mode when the user stops generation
  useEffect(() => {
    if (isStopped && report) {
      setEditValue(report.query || '')
      setIsEditing(true)
      setTimeout(() => {
        editTextareaRef.current?.focus()
        adjustEditTextareaHeight()
      }, 50)
    }
  }, [isStopped, report, adjustEditTextareaHeight])

  useEffect(() => {
    if (isEditing) adjustEditTextareaHeight()
  }, [isEditing, editValue, adjustEditTextareaHeight])

  // Start editing — stop generation first if still running
  const startEditing = () => {
    if (!report) return
    if (!report.done) onStop?.()
    setEditValue(report.query || '')
    setIsEditing(true)
    setTimeout(() => {
      editTextareaRef.current?.focus()
      adjustEditTextareaHeight()
    }, 0)
  }

  // Cancel editing
  const cancelEditing = () => {
    setIsEditing(false)
    setEditValue('')
  }

  const handleEditKeyDown = async (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!editValue.trim()) {
        cancelEditing()
        return
      }
      await onEditSubmit({ query: editValue.trim(), index: analysisIndex })
      setIsEditing(false)
    } else if (e.key === 'Escape') {
      e.preventDefault()
      // Don't allow escaping edit mode when stopped — keep the textarea open
      if (!isStopped) cancelEditing()
    }
  }

  const onRedoClick = () => {
    if (report) {
      onEditSubmit({ query: report.query, index: analysisIndex })
    }
  }

  const handleCopy = async (query: string) => {
    if (!query) return
    try {
      await navigator.clipboard.writeText(query)
      setCopyState('success')
    } catch {
      setCopyState('error')
    } finally {
      // Reset after a certain time
      setTimeout(() => setCopyState('idle'), 1800)
    }
  }

  const copyMessage =
    copyState === 'idle'
      ? 'copy to clipboard'
      : copyState === 'success'
      ? 'copied'
      : 'copy failed'

  if (error) {
    return (
      <div className='max-w-3xl mx-auto p-4'>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Failed to retrieve report for analysis ID {analysisId}.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  if (isLoading || !report) {
    return (
      <div className='max-w-3xl mx-auto p-4'>
        <h2 className='text-3xl font-bold'>Analysis Starting...</h2>
        <div className='my-5 flex gap-2'>
          <LoaderCircle className='animate-spin' size={20} />
          <p>Loading model...</p>
        </div>
      </div>
    )
  }

  if (report.error && !isStopped) {
    return (
      <div className='max-w-3xl mx-auto p-4'>
        <h2 className='text-3xl font-bold'>{report.query || 'Data Analysis'}</h2>
        <Alert variant="destructive" className="my-4">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {report.error}
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div ref={itemRef} className='max-w-3xl mx-auto p-4'>
      <div className="group flex flex-row gap-3 relative mb-6 w-auto">
        {isEditing ? (
          <div className="flex-1">
            <textarea
              ref={editTextareaRef}
              value={editValue}
              onBlur={isStopped ? undefined : cancelEditing}
              onKeyDown={handleEditKeyDown}
              onChange={(e) => setEditValue(e.target.value)}
              className="w-full resize-none overflow-hidden rounded-md border border-border bg-background px-3 py-3 text-2xl font-bold leading-normal focus:outline-none focus:ring-2 focus:ring-primary"
              rows={1}
              aria-label="Edit"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              {isStopped
                ? 'Generation was stopped. Edit your prompt and press Enter to retry.'
                : 'Enter to confirm / Esc or focus out to cancel / Shift+Enter for new line'}
            </p>
          </div>
        ) : (
          <>
            <motion.h2 
              className="text-3xl font-bold pr-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              {report.query}
            </motion.h2>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant='link'
                    onClick={() => handleCopy(report.query)}
                    aria-label="Copy"
                    className="rounded-md mt-3
                      opacity-0 group-hover:opacity-100 transition-opacity
                      hover:bg-accent hover:text-accent-foreground
                      text-muted-foreground p-1"
                    title={copyMessage}
                    disabled={isGlobalSubmitting}
                  >
                    {copyState === 'success' ? (<Check className="w-4 h-4" />) : (<Copy className="w-4 h-4" />)}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top">
                  <p className="text-xs">{copyMessage}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <Button
                    variant='link'
              onClick={startEditing}
              aria-label="Edit"
              className="rounded-md mt-3
                 opacity-0 group-hover:opacity-100 transition-opacity
                 hover:bg-accent hover:text-accent-foreground
                 text-muted-foreground p-1 disabled:opacity-0"
              disabled={isGlobalSubmitting}
            >
              <Pencil className="w-4 h-4" />
            </Button>
          </>
        )}
      </div>
      
      <AnimatePresence mode="wait">
        {report.progress !== "" && (
          <motion.div 
            key={report.progress}
            className='my-5 flex gap-2'
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <LoaderCircle className='animate-spin' size={20} />
            <p>{report.progress || 'Analyzing...'}</p>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        key={`${report.content}-${report.python_code}-${JSON.stringify(report.steps)}`}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <ReportContent 
          content={report.content}
          pythonCode={report.python_code}
          steps={report.steps}
          onShowSidePanel={onShowSidePanel}
          handleRedoClick={onRedoClick}
        />
      </motion.div>
    </div>
  )
}

export default function AnalysisReport() {
  const { reportId } = useParams({ from: '/_authenticated/report/$reportId' })
  const spaceId = reportId // Treat URL parameter as spaceId
  const { data: space, isLoading: spaceLoading, error: spaceError, refetch: refetchSpace } = useGetSpace(spaceId)
  const [sidePanelContent, setSidePanelContent] = useState<SidePanelContentType | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [isProcessing, setIsProcessing] = useState(false)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const latestItemRef = useRef<HTMLDivElement>(null)
  const [scrollPosition, setScrollPosition] = useState(0)
  // Manage follow-up input state at the parent level
  const [followupText, setFollowupText] = useState<string>('')
  const [followupModel, setFollowupModel] = useState<string>('')
  const [followupSelectedTables, setFollowupSelectedTables] = useState<string[]>([])
  const { setItemLoading } = useSharedAnalysisHistory()
  const startFollowupMutation = useStartAnalysis()
  const stopAnalysisMutation = useStopAnalysis()
  const queryClient = useQueryClient()
  const { data: tables, error: tablesError } = useTableList()
  const { data: modelData } = useModelListByMode(false)
  const [followupStatus, setFollowupStatus] = useState<'submitted' | 'streaming' | 'ready' | 'error'>('ready')

  useEffect(()=>{
      setItemLoading(reportId, isProcessing)
  },[isProcessing, reportId, setItemLoading])

  // Initialize model list
  useEffect(() => {
    if (modelData?.models && modelData.models.length > 0) {
      const exists = modelData.models.find((m: ModelInfo) => m.id === followupModel)
      if (!exists) {
        setFollowupModel(modelData.models[0].id)
      }
    }
  }, [modelData, followupModel])

  // Initialize select-all for tables
  useEffect(() => {
    if (tables && tables.length > 0 && followupSelectedTables.length === 0) {
      setFollowupSelectedTables(tables.map(t => t.name))
    }
  }, [tables])

  // Update input status based on processing state
  useEffect(() => {
    if (isProcessing) setFollowupStatus('streaming')
    else setFollowupStatus('ready')
  }, [isProcessing])

  // Stop the currently running analysis
  const handleStop = async () => {
    const latestAnalysisId = space?.analysis_ids?.[space.analysis_ids.length - 1]
    if (!latestAnalysisId) return
    await stopAnalysisMutation.mutateAsync(latestAnalysisId)
    queryClient.invalidateQueries({ queryKey: ['report', latestAnalysisId] })
  }

  // Handle updates when a follow-up analysis is added
  const handleFollowupSubmitted = () => {
    // Re-fetch space data to get the new analysis ID
    refetchSpace()
    setRefreshKey(prev => prev + 1)
    
    // Scroll to the latest query after a short delay
    setTimeout(() => {
      scrollToLatest()
    }, 500)
  }

  // Follow-up submission handler (previously inside child component)
  const handleFollowupSubmit = async ({ text }: { text: string }) => {
    if (!text.trim()) return
    if (!tables || tables.length === 0 || tablesError) {
      toast.error('At least one table must be connected to start the follow-up analysis.')
      return
    }
    if (followupSelectedTables.length === 0) {
      toast.error('Please select at least one table.')
      return
    }
    setFollowupStatus('submitted')
    try {
      const result = await startFollowupMutation.mutateAsync({
        space_id: spaceId,
        query: text.trim(),
        tables: followupSelectedTables,
        mode: 'agentic',
        model: followupModel,
        index: -1,
      })
      if (result.error) {
        toast.error(result.error)
        setFollowupStatus('error')
      } else {
        setFollowupText('')
        setFollowupStatus('ready')
        handleFollowupSubmitted()
      }
  } catch (_err) {
      toast.error('Failed to start analysis')
      setFollowupStatus('error')
      setTimeout(() => setFollowupStatus('ready'), 3000)
    }
  }

  // Submit edit of existing query (with index specified)
  const handleEditSubmit = async ({ query, index }: { query: string; index: number }) => {
    if (!query.trim()) return
    if (!tables || tables.length === 0 || tablesError) {
      toast.error('You need one or more tables.')
      return
    }
    setFollowupStatus('submitted')
    try {
      await startFollowupMutation.mutateAsync({
        space_id: spaceId,
        query: query.trim(),
        tables: followupSelectedTables.length ? followupSelectedTables : (tables?.map(t=>t.name) ?? []),
        mode: 'agentic',
        model: followupModel,
        index: index,
      })
      handleFollowupSubmitted()
      setFollowupStatus('ready')
    } catch (_err) {
      toast.error('Failed to start analysis')
      setFollowupStatus('error')
      setTimeout(() => setFollowupStatus('ready'), 3000)
    }
  }

  // Smooth scroll to the latest query
  const scrollToLatest = () => {
    if (latestItemRef.current && scrollContainerRef.current) {
      // Calculate so the top of the latest item aligns with the top of the screen
      const itemTop = latestItemRef.current.offsetTop
      scrollContainerRef.current.scrollTo({
        top: itemTop,
        behavior: 'smooth'
      })
    }
  }

  // Save scroll position
  const saveScrollPosition = () => {
    if (scrollContainerRef.current) {
      setScrollPosition(scrollContainerRef.current.scrollTop);
    }
  };

  // Restore scroll position
  const restoreScrollPosition = () => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        top: scrollPosition,
        behavior: 'auto',
      });
    }
  };

  // Scroll to latest query on initial page load
  useEffect(() => {
    if (space && space.analysis_ids && space.analysis_ids.length > 1) {
      // If there are multiple analyses, scroll with a short delay
      setTimeout(() => {
        scrollToLatest()
      }, 1000)
    }
  }, [space?.analysis_ids?.length])

  useEffect(() => {
    restoreScrollPosition();
  }, [sidePanelContent]);

  // Common header
  const headerElement = (
    <Header>
      <div className='ml-auto flex items-center space-x-4'>
  <ThemeSwitch />
  <Setting />
      </div>
    </Header>
  )

  // Determine main content
  let mainContent: React.ReactNode

  if (spaceError) {
    mainContent = (
      <div className='max-w-3xl mx-auto p-4'>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Missing or invalid analysis report.
          </AlertDescription>
        </Alert>
      </div>
    )
  } else if (spaceLoading || !space) {
    mainContent = (
      <div className='max-w-3xl mx-auto p-4'>
        <h1 className='text-4xl font-bold'>Loading space...</h1>
        <div className='my-5 flex gap-2'>
          <LoaderCircle className='animate-spin' size={20} />
          <p>Loading data...</p>
        </div>
      </div>
    )
  } else {
    // Display analysis results within the space
    const analysisIds = space.analysis_ids || []
    
    if (analysisIds.length === 0) {
      mainContent = (
        <div className='max-w-3xl mx-auto p-4'>
          <h1 className='text-4xl font-bold'>Lost Analysis</h1>
          <p className='text-muted-foreground'>There are no analysis results in this space yet. This will happen once you restarted app.</p>
        </div>
      )
    } else {
      // Layout containing multiple analysis results
      const analysisReports = (
        <div className="relative h-full">
          <div 
            ref={scrollContainerRef}
            className="h-full overflow-auto pb-24" 
            onScroll={saveScrollPosition} // Save position on scroll event
          >
            {/* Reserve space for follow-up input area */}
            <div className="space-y-8 mb-[100px]">
              {analysisIds.map((analysisId, index) => {
                const isLast = index === analysisIds.length - 1
                return (
                  <div key={`${analysisId}-${refreshKey}`} className="">
                    <AnalysisReportItem
                      analysisId={analysisId}
                      onShowSidePanel={setSidePanelContent}
                      itemRef={isLast ? latestItemRef : undefined}
                      setIsProcessing={isLast ? setIsProcessing : undefined}
                      analysisIndex={index}
                      onEditSubmit={handleEditSubmit}
                      isGlobalSubmitting={followupStatus === 'submitted'}
                      onStop={isLast ? handleStop : undefined}
                    />
                  </div>
                )
              })}
            </div>
          </div>
          {/* Follow-up input area - sticky to parent container */}
          <FollowupInput 
            text={followupText}
            onTextChange={setFollowupText}
            model={followupModel}
            onModelChange={setFollowupModel}
            models={modelData?.models || []}
            selectedTables={followupSelectedTables}
            onSelectedTablesChange={setFollowupSelectedTables}
            tables={tables}
            tablesError={tablesError}
            status={followupStatus}
            isprocessing={isProcessing}
            onSubmit={handleFollowupSubmit}
            onStop={handleStop}
          />
        </div>
      )

      mainContent = sidePanelContent ? (
        <Split
          sizes={[65, 35]}
          minSize={[500, 400]}
          className="flex h-full"
        >
          <div className="h-full overflow-hidden"> {/* Removed overflow-auto, managed inside analysisReports */}
            {analysisReports}
          </div>
          <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden border-l bg-background">
            <AnimatePresence>
              {sidePanelContent && (
                <motion.div
                  key={sidePanelContent.type + sidePanelContent.content}
                  className="flex h-full min-h-0 min-w-0 flex-1 flex-col"
                  initial={{ opacity: 0, x: 50 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.1 }}
                >
                  <SidePanel
                    type={sidePanelContent.type}
                    content={sidePanelContent.content}
                    stepData={sidePanelContent.stepData}
                    onClose={() => setSidePanelContent(null)}
                    inSplitView={true}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </Split>
      ) : (
        <div className="h-full overflow-hidden"> {/* Removed overflow-auto, managed inside analysisReports */}
          {analysisReports}
        </div>
      )
    }
  }

  return (
    <>
      {headerElement}
      <Main className={`relative ${space && space.analysis_ids.length > 0 ? "p-0 h-[calc(100vh-60px)]" : ""}`}>
        {mainContent}
      </Main>
    </>
  )
}