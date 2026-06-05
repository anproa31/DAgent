import logo from '@/assets/olazc9.svg'
import { cn } from '@/lib/utils'
import { AIResponse } from '@/components/shared/kibo-ui/response'
import type { ThinkingSegment } from '@/services/api/agent'

const AGENT_LABELS: Record<string, string> = {
  planner: 'Reasoning',
  sql: 'SQL generation',
  python: 'Python generation',
  eda: 'Exploratory analysis',
  insight: 'Insights',
  final_report: 'Report',
}

function agentLabel(agent: string): string {
  return AGENT_LABELS[agent] ?? agent.replace(/_/g, ' ')
}

function ThinkingDots() {
  return (
    <span className='inline-flex'>
      <span className='animate-[thinking-dot_1.4s_ease-in-out_infinite]'>.</span>
      <span className='animate-[thinking-dot_1.4s_ease-in-out_0.2s_infinite]'>.</span>
      <span className='animate-[thinking-dot_1.4s_ease-in-out_0.4s_infinite]'>.</span>
    </span>
  )
}

interface ThinkingCollapsibleProps {
  segments: ThinkingSegment[]
  isActive: boolean
  className?: string
}

export function ThinkingCollapsible({
  segments,
  isActive,
  className,
}: ThinkingCollapsibleProps) {
  if (!isActive) return null

  return (
    <div className={cn('group mb-4', className)}>
      <div className='text-muted-foreground flex cursor-default items-center gap-2 text-sm'>
        <img
          src={logo}
          alt=''
          aria-hidden
          className='h-4 w-4 shrink-0 animate-spin dark:invert'
        />
        <span>
          Thinking
          <ThinkingDots />
        </span>
      </div>

      <div
        className={cn(
          'grid transition-[grid-template-rows,opacity,margin] duration-200 ease-out',
          'grid-rows-[0fr] opacity-0',
          'group-hover:mt-2 group-hover:grid-rows-[1fr] group-hover:opacity-100'
        )}
      >
        <div className='overflow-hidden'>
          <div className='border-border/40 bg-muted/20 max-h-[200px] overflow-y-auto rounded-md border px-3 py-2'>
            {segments.length === 0 ? (
              <p className='text-muted-foreground text-xs'>Waiting for reasoning…</p>
            ) : (
              <div className='space-y-2'>
                {segments.map((seg) => (
                  <div key={seg.id} className='space-y-0.5'>
                    <span className='text-muted-foreground text-[10px] font-medium uppercase tracking-wide'>
                      {agentLabel(seg.agent)}
                    </span>
                    <div className='text-foreground/90 text-xs leading-relaxed'>
                      <AIResponse>{seg.text}</AIResponse>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
