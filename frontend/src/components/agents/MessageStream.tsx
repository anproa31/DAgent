import { useState } from 'react'
import { ChevronDown, Search, Code2, Terminal, FileCheck, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible'
import { AIResponse } from '@/components/ui/kibo-ui/response'

type StreamBlockStatus = 'idle' | 'generating' | 'done'

interface StreamBlockProps {
  label: string
  icon: typeof Search
  status: StreamBlockStatus
  defaultOpen?: boolean
  children: React.ReactNode
  className?: string
}

function StreamBlock({ label, icon: Icon, status, defaultOpen = true, children, className }: StreamBlockProps) {
  const [open, setOpen] = useState(defaultOpen)

  const statusLabel = status === 'generating' ? ` (Generating)` : ''

  return (
    <Collapsible open={open} onOpenChange={setOpen} className={cn('rounded-lg border overflow-hidden', className)}>
      <CollapsibleTrigger className='flex w-full items-center justify-between bg-muted/50 px-4 py-2.5 text-sm font-medium hover:bg-muted/80 transition-colors'>
        <div className='flex items-center gap-2'>
          <Icon className='h-4 w-4 text-muted-foreground' />
          <span>{label}{statusLabel}</span>
          {status === 'generating' && (
            <Loader2 className='h-3.5 w-3.5 animate-spin text-primary' />
          )}
        </div>
        <ChevronDown className={cn('h-4 w-4 text-muted-foreground transition-transform duration-200', open && 'rotate-180')} />
      </CollapsibleTrigger>
      <CollapsibleContent className='px-4 py-3'>
        {children}
      </CollapsibleContent>
    </Collapsible>
  )
}

interface AnalyzeBlockProps {
  content: string
  status: StreamBlockStatus
}

export function AnalyzeBlock({ content, status }: AnalyzeBlockProps) {
  if (!content && status === 'idle') return null

  return (
    <StreamBlock label='Analyze' icon={Search} status={status}>
      <div className='text-sm text-muted-foreground space-y-1 leading-relaxed'>
        <AIResponse>{content}</AIResponse>
      </div>
    </StreamBlock>
  )
}

interface CodeBlockStreamProps {
  code: string
  language?: string
  status: StreamBlockStatus
}

export function CodeBlockStream({ code, language = 'python', status }: CodeBlockStreamProps) {
  if (!code && status === 'idle') return null

  return (
    <StreamBlock label='Code' icon={Code2} status={status}>
      <div className='rounded-md bg-zinc-950 dark:bg-zinc-900 overflow-hidden'>
        <div className='flex items-center justify-between px-3 py-1.5 border-b border-zinc-800'>
          <span className='text-[11px] font-mono text-zinc-400'>{language}</span>
        </div>
        <pre className='p-3 overflow-x-auto text-sm'>
          <code className='font-mono text-zinc-100 leading-relaxed whitespace-pre-wrap'>{code}</code>
        </pre>
      </div>
    </StreamBlock>
  )
}

interface ConsoleOutputBlockProps {
  output: string
  status: StreamBlockStatus
}

export function ConsoleOutputBlock({ output, status }: ConsoleOutputBlockProps) {
  if (!output && status === 'idle') return null

  return (
    <StreamBlock label='Execute' icon={Terminal} status={status}>
      <div className='rounded-md bg-zinc-950 dark:bg-zinc-900 p-3 overflow-x-auto'>
        <pre className='font-mono text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed'>{output}</pre>
      </div>
    </StreamBlock>
  )
}

interface AnswerBlockProps {
  children: React.ReactNode
  status: StreamBlockStatus
}

export function AnswerBlock({ children, status }: AnswerBlockProps) {
  if (status === 'idle') return null

  return (
    <StreamBlock label='Answer' icon={FileCheck} status={status} defaultOpen>
      {children}
    </StreamBlock>
  )
}

interface StreamingAnswerBlockProps {
  content: string
  status: StreamBlockStatus
}

/**
 * Live, token-by-token markdown rendering of the answer while it is still
 * being produced by the backend. Renders nothing until the first chunk
 * arrives so it does not flash an empty block.
 */
export function StreamingAnswerBlock({ content, status }: StreamingAnswerBlockProps) {
  if (!content) return null

  return (
    <StreamBlock label='Answer' icon={FileCheck} status={status} defaultOpen>
      <div className='text-sm leading-relaxed'>
        <AIResponse>{content}</AIResponse>
      </div>
    </StreamBlock>
  )
}
