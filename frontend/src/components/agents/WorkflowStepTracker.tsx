import { Brain, Search, Code2, Play, FileText, Check, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export type WorkflowStep = 'understand' | 'analyze' | 'code' | 'execute' | 'file'
export type StepState = 'idle' | 'active' | 'completed'

const STEPS: { key: WorkflowStep; label: string; icon: typeof Brain }[] = [
  { key: 'understand', label: 'Understand', icon: Brain },
  { key: 'analyze', label: 'Analyze', icon: Search },
  { key: 'code', label: 'Code', icon: Code2 },
  { key: 'execute', label: 'Execute', icon: Play },
  { key: 'file', label: 'File', icon: FileText },
]

interface WorkflowStepTrackerProps {
  stepStates: Record<WorkflowStep, StepState>
  className?: string
}

export function WorkflowStepTracker({ stepStates, className }: WorkflowStepTrackerProps) {
  return (
    <div className={cn('flex items-center justify-center gap-0 py-4 px-6', className)}>
      {STEPS.map((step, index) => {
        const state = stepStates[step.key]
        const Icon = step.icon
        const isLast = index === STEPS.length - 1

        return (
          <div key={step.key} className='flex items-center'>
            <div className='flex flex-col items-center gap-1.5 relative'>
              {state === 'active' && (
                <div className='absolute -top-7 left-1/2 -translate-x-1/2'>
                  <span className='inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-[10px] font-medium text-primary'>
                    <Loader2 className='h-2.5 w-2.5 animate-spin' />
                    Running
                  </span>
                </div>
              )}

              <div
                className={cn(
                  'relative flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all duration-300',
                  state === 'idle' && 'border-muted-foreground/30 bg-background text-muted-foreground/50',
                  state === 'active' && 'border-primary bg-primary/10 text-primary shadow-[0_0_0_4px] shadow-primary/15',
                  state === 'completed' && 'border-green-500 bg-green-500/10 text-green-600'
                )}
              >
                {state === 'active' && (
                  <span className='absolute inset-0 rounded-full border-2 border-primary animate-ping opacity-30' />
                )}
                {state === 'completed' ? (
                  <Check className='h-4.5 w-4.5' strokeWidth={2.5} />
                ) : (
                  <Icon className='h-4.5 w-4.5' />
                )}
              </div>

              <span
                className={cn(
                  'text-[11px] font-medium transition-colors',
                  state === 'idle' && 'text-muted-foreground/50',
                  state === 'active' && 'text-primary font-semibold',
                  state === 'completed' && 'text-green-600'
                )}
              >
                {step.label}
              </span>
            </div>

            {!isLast && (
              <div
                className={cn(
                  'h-[2px] w-10 mx-1.5 mt-[-18px] transition-colors duration-300',
                  stepStates[STEPS[index + 1].key] !== 'idle' || state === 'completed'
                    ? 'bg-green-500/50'
                    : state === 'active'
                      ? 'bg-primary/30'
                      : 'bg-muted-foreground/20'
                )}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

const AGENT_TO_STEP: Record<string, WorkflowStep> = {
  orchestrator: 'understand',
  sql: 'code',
  eda: 'analyze',
  code_executor: 'execute',
  insight: 'analyze',
  viz: 'file',
  final_report: 'file',
}

const STEP_ORDER: WorkflowStep[] = ['understand', 'analyze', 'code', 'execute', 'file']

export function deriveStepStates(
  currentAgent: string,
  agentSteps: string[],
  phase: string
): Record<WorkflowStep, StepState> {
  const states: Record<WorkflowStep, StepState> = {
    understand: 'idle',
    analyze: 'idle',
    code: 'idle',
    execute: 'idle',
    file: 'idle',
  }

  if (phase === 'idle') return states

  if (phase === 'done') {
    for (const key of STEP_ORDER) states[key] = 'completed'
    return states
  }

  const completedSteps = new Set<WorkflowStep>()
  for (const agent of agentSteps) {
    const mapped = AGENT_TO_STEP[agent]
    if (mapped) completedSteps.add(mapped)
  }

  const activeStep = AGENT_TO_STEP[currentAgent] ?? 'understand'

  const activeIndex = STEP_ORDER.indexOf(activeStep)
  for (let i = 0; i < STEP_ORDER.length; i++) {
    const step = STEP_ORDER[i]
    if (i < activeIndex || completedSteps.has(step)) {
      if (step !== activeStep) states[step] = 'completed'
    }
    if (step === activeStep) {
      states[step] = 'active'
      for (let j = 0; j < i; j++) {
        states[STEP_ORDER[j]] = 'completed'
      }
    }
  }

  if (phase === 'starting' || phase === 'thinking') {
    const startStep = AGENT_TO_STEP[currentAgent] || 'understand'
    states[startStep] = 'active'
  }

  return states
}
