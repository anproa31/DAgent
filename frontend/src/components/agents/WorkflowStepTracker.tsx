import {
  Brain,
  Search,
  Code2,
  Play,
  FileText,
  Lightbulb,
  BarChart3,
  Sparkles,
  Check,
  Loader2,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export type StepStatus = 'active' | 'completed'

export interface VisibleStep {
  /** Backend agent name (or synthetic key like `_starting`). */
  agent: string
  label: string
  icon: typeof Brain
  status: StepStatus
}

/**
 * Visual metadata for each known backend agent. Anything not listed falls back
 * to a generic icon + a prettified label, so the tracker still renders sanely
 * if the backend adds new agents.
 */
const AGENT_META: Record<string, { label: string; icon: typeof Brain }> = {
  orchestrator: { label: 'Understand', icon: Brain },
  router: { label: 'Understand', icon: Brain },
  planner: { label: 'Understand', icon: Brain },
  sql: { label: 'Code Gen', icon: Code2 },
  sql_agent: { label: 'Code Gen', icon: Code2 },
  code: { label: 'Code Gen', icon: Code2 },
  code_executor: { label: 'Execute', icon: Play },
  executor: { label: 'Execute', icon: Play },
  python_executor: { label: 'Execute', icon: Play },
  eda: { label: 'Analyze', icon: Search },
  data_explorer: { label: 'Analyze', icon: Search },
  insight: { label: 'Insight', icon: Lightbulb },
  viz: { label: 'Visualize', icon: BarChart3 },
  viz_agent: { label: 'Visualize', icon: BarChart3 },
  final_report: { label: 'Report', icon: FileText },
  reporter: { label: 'Report', icon: FileText },
}

function prettify(agent: string): string {
  if (!agent) return 'Step'
  return agent
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}

function metaFor(agent: string) {
  return AGENT_META[agent] ?? { label: prettify(agent), icon: Sparkles }
}

/**
 * Derive the list of steps that are visible right now in the UI from the
 * backend signals.
 *
 * The list grows over time as new agents run — earlier (historical) agents
 * become `completed` and the active one is marked `active`. Future steps are
 * intentionally hidden until their agent actually starts, matching the
 * "show this step, another show later" UX requirement.
 */
export function deriveVisibleSteps(
  currentAgent: string,
  agentSteps: string[],
  phase: string
): VisibleStep[] {
  if (phase === 'idle') return []

  // Collapse consecutive duplicates so a single agent visit does not produce
  // multiple visible steps when the backend emits repeated entries.
  const history = (Array.isArray(agentSteps) ? agentSteps : []).filter(Boolean)
  const ordered: string[] = []
  for (const a of history) {
    if (ordered[ordered.length - 1] !== a) ordered.push(a)
  }
  if (currentAgent && ordered[ordered.length - 1] !== currentAgent) {
    ordered.push(currentAgent)
  }

  // Nothing has happened yet — show a single neutral placeholder so the
  // tracker area is never visually empty during the initial "Starting…" gap.
  if (ordered.length === 0) {
    return [
      { agent: '_starting', label: 'Starting…', icon: Brain, status: 'active' },
    ]
  }

  return ordered.map((agent, i) => {
    const isLast = i === ordered.length - 1
    const isTerminal = phase === 'done' || phase === 'error' || phase === 'stopped'
    const status: StepStatus = isTerminal ? 'completed' : isLast ? 'active' : 'completed'
    const meta = metaFor(agent)
    return { agent, label: meta.label, icon: meta.icon, status }
  })
}

interface WorkflowStepTrackerProps {
  steps: VisibleStep[]
  className?: string
}

export function WorkflowStepTracker({ steps, className }: WorkflowStepTrackerProps) {
  if (!steps.length) return null

  return (
    <div
      className={cn(
        'flex items-start justify-center gap-0 py-6 px-6 overflow-x-auto',
        className
      )}
    >
      {steps.map((step, index) => {
        const Icon = step.icon
        const isLast = index === steps.length - 1

        return (
          <div
            key={`${step.agent}-${index}`}
            className='flex items-start animate-in fade-in-0 slide-in-from-bottom-1 duration-300'
          >
            <div className='flex flex-col items-center'>
              {/* Reserve vertical space so every column aligns; badge sits above the icon with clear separation */}
              <div className='mb-3 flex min-h-[30px] w-full flex-col items-center justify-end'>
                {step.status === 'active' ? (
                  <span className='inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-[10px] font-medium text-primary whitespace-nowrap'>
                    <Loader2 className='h-2.5 w-2.5 animate-spin' />
                    Running
                  </span>
                ) : null}
              </div>

              <div
                className={cn(
                  'relative flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all duration-300',
                  step.status === 'active' &&
                    'border-primary bg-primary/10 text-primary shadow-[0_0_0_4px] shadow-primary/15',
                  step.status === 'completed' && 'border-green-500 bg-green-500/10 text-green-600'
                )}
              >
                {step.status === 'active' && (
                  <span className='absolute inset-0 rounded-full border-2 border-primary animate-ping opacity-30' />
                )}
                {step.status === 'completed' ? (
                  <Check className='h-4.5 w-4.5' strokeWidth={2.5} />
                ) : (
                  <Icon className='h-4.5 w-4.5' />
                )}
              </div>

              <span
                className={cn(
                  'mt-3 text-[11px] font-medium transition-colors whitespace-nowrap',
                  step.status === 'active' && 'text-primary font-semibold',
                  step.status === 'completed' && 'text-green-600'
                )}
              >
                {step.label}
              </span>
            </div>

            {!isLast && (
              <div
                className={cn(
                  'h-[2px] w-10 mx-2 mt-[52px] shrink-0 transition-colors duration-300',
                  // Connector reflects completion of the step on its left.
                  step.status === 'completed' ? 'bg-green-500/50' : 'bg-primary/30'
                )}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
