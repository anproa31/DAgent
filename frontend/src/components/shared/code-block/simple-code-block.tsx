import { cn } from '@/lib/utils'

interface SimpleCodeBlockProps {
  code: string
  language?: string
  className?: string
}

export function SimpleCodeBlock({
  code,
  language = 'text',
  className,
}: SimpleCodeBlockProps) {
  return (
    <div
      className={cn(
        'overflow-hidden rounded-md bg-zinc-950 dark:bg-zinc-900',
        className
      )}
    >
      <div className='flex items-center justify-between border-b border-zinc-800 px-3 py-1.5'>
        <span className='font-mono text-[11px] text-zinc-400'>{language}</span>
      </div>
      <pre className='overflow-x-auto p-3 text-sm'>
        <code className='font-mono leading-relaxed break-words whitespace-pre-wrap text-zinc-100'>
          {code}
        </code>
      </pre>
    </div>
  )
}
