import { CheckCircle2, Circle, Loader2, AlertCircle, CircleSlash } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { RunPhase } from '@/stores/agentStore'

const AGENT_LABELS: Record<string, string> = {
  orchestrator: 'Orchestrator',
  sql: 'SQL Agent',
  code_executor: 'Code Executor',
  eda: 'EDA Agent',
  insight: 'Insight Agent',
  viz: 'Visualization Agent',
  final_report: 'Report Compiler',
}

const PHASE_LABELS: Record<RunPhase, string> = {
  idle: 'Idle',
  starting: 'Starting…',
  thinking: 'Thinking…',
  running: 'Running',
  awaiting_approval: 'Awaiting SQL Approval',
  done: 'Complete',
  error: 'Error',
  stopped: 'Stopped',
}

interface AgentProgressPanelProps {
  phase: RunPhase
  currentAgent: string
  agentSteps: string[]
  thinkingMessage?: string
  className?: string
}

export function AgentProgressPanel({
  phase,
  currentAgent,
  agentSteps,
  thinkingMessage,
  className,
}: AgentProgressPanelProps) {
  if (phase === 'idle') return null

  return (
    <div
      className={cn(
        'rounded-xl border bg-card p-4 space-y-3 text-sm',
        className
      )}
    >
      {/* Status row */}
      <div className='flex items-center gap-2'>
        <PhaseIcon phase={phase} />
        <span className='font-medium'>{PHASE_LABELS[phase]}</span>
        {currentAgent && phase !== 'done' && phase !== 'error' && phase !== 'stopped' && (
          <Badge variant='secondary' className='text-xs'>
            {AGENT_LABELS[currentAgent] ?? currentAgent}
          </Badge>
        )}
      </div>

      {/* Thinking message */}
      {thinkingMessage && phase === 'thinking' && (
        <p className='text-muted-foreground text-xs pl-6 flex items-center gap-2'>
          <Loader2 className='h-3.5 w-3.5 animate-spin text-primary shrink-0' />
          <span>{thinkingMessage}</span>
        </p>
      )}

      {/* Agent steps */}
      {agentSteps.length > 0 && (
        <ol className='space-y-1 pl-2'>
          {agentSteps.map((step, i) => {
            const isActive = step === currentAgent && phase === 'running'
            const isDone = i < agentSteps.length - 1 || phase === 'done' || phase === 'stopped'
            return (
              <li key={i} className='flex items-center gap-2'>
                {isActive ? (
                  <Loader2 className='h-3.5 w-3.5 animate-spin text-primary shrink-0' />
                ) : isDone ? (
                  <CheckCircle2 className='h-3.5 w-3.5 text-green-500 shrink-0' />
                ) : (
                  <Circle className='h-3.5 w-3.5 text-muted-foreground shrink-0' />
                )}
                <span
                  className={cn(
                    'text-xs',
                    isActive && 'text-foreground font-medium',
                    isDone && !isActive && 'text-muted-foreground',
                    !isDone && !isActive && 'text-muted-foreground/60'
                  )}
                >
                  {AGENT_LABELS[step] ?? step}
                </span>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}

function PhaseIcon({ phase }: { phase: RunPhase }) {
  switch (phase) {
    case 'done':
      return <CheckCircle2 className='h-4 w-4 text-green-500 shrink-0' />
    case 'error':
      return <AlertCircle className='h-4 w-4 text-destructive shrink-0' />
    case 'stopped':
      return <CircleSlash className='h-4 w-4 text-muted-foreground shrink-0' />
    case 'awaiting_approval':
      return <AlertCircle className='h-4 w-4 text-amber-500 shrink-0' />
    default:
      return <Loader2 className='h-4 w-4 animate-spin text-primary shrink-0' />
  }
}
