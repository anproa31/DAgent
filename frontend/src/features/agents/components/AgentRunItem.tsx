import { useState } from 'react'
import { Pencil, Check, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { WorkflowStepTracker, deriveVisibleSteps } from '@/components/agents/WorkflowStepTracker'
import { AnswerBlock, StreamingAnswerBlock } from '@/components/agents/MessageStream'
import { ReportContent } from '@/features/analysis-report/components/report-content'
import type { ActionStep } from '@/types/report'
import type { ReportContent as ReportContentType } from '@/hooks/use-analysis'
import type { AgentRun } from '@/stores/agentStore'

export interface AgentRunItemProps {
  run: AgentRun
  runIndex: number
  onShowSidePanel: (c: {
    type: 'code' | 'table' | 'step'
    content: string
    stepData?: ActionStep
  }) => void
  onEditPrompt: (params: { index: number; query: string }) => Promise<void> | void
  onBeginEditPrompt?: () => void
  canEdit: boolean
}

export function AgentRunItem({
  run,
  runIndex,
  onShowSidePanel,
  onEditPrompt,
  onBeginEditPrompt,
  canEdit,
}: AgentRunItemProps) {
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

  const answerStatus = showReport
    ? ('done' as const)
    : isActive &&
        (['final_report', 'viz'].includes(run.currentAgent) ||
          run.streamingAnswer.length > 0)
      ? ('generating' as const)
      : ('idle' as const)

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
    if (!trimmed) {
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

      {isActive && visibleSteps.length > 0 && (
        <WorkflowStepTracker steps={visibleSteps} className='mb-4' />
      )}

      <div className='space-y-3'>
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
