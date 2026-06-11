import type { HTMLAttributes, ReactNode } from 'react'
import { memo } from 'react'
import ReactMarkdown, { type Options } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'
import { SimpleCodeBlock } from '@/components/shared/code-block/simple-code-block'

const IMPACT_LEVEL_PATTERN = /\*\*\[Impact Level:[^\]]+\]\*\*/i

function extractTextFromChildren(children: ReactNode): string {
  if (typeof children === 'string') return children
  if (typeof children === 'number') return String(children)
  if (Array.isArray(children)) {
    return children.map(extractTextFromChildren).join('')
  }
  if (children && typeof children === 'object' && 'props' in children) {
    return extractTextFromChildren(
      (children as { props: { children?: ReactNode } }).props.children
    )
  }
  return ''
}

function normalizeImpactLevelSpacing(markdown: string): string {
  return markdown.replace(
    /(^|\n)(\*\*\[Impact Level:[^\]]+\]\*\*)/gi,
    (_match, prefix, marker) => `${prefix === '' ? '' : '\n'}\n\n${marker}`
  )
}

function normalizeActionSpacing(markdown: string): string {
  return markdown.replace(/\s*(\*\*Action:?\*\*)/gi, '  \n$1')
}

export type AIResponseProps = HTMLAttributes<HTMLDivElement> & {
  options?: Options
  children: Options['children']
}
const components: Options['components'] = {
  table: ({ node, children, className, ...props }) => (
    <div className='my-4 inline-block max-w-full overflow-x-auto rounded-lg border bg-card'>
      <table className={cn('w-max caption-bottom text-sm', className)} {...props}>
        {children}
      </table>
    </div>
  ),
  thead: ({ node, children, className, ...props }) => (
    <thead className={cn('bg-muted/50 border-b', className)} {...props}>
      {children}
    </thead>
  ),
  tbody: ({ node, children, className, ...props }) => (
    <tbody className={cn('[&>tr:last-child]:border-0', className)} {...props}>
      {children}
    </tbody>
  ),
  tr: ({ node, children, className, ...props }) => (
    <tr className={cn('border-b transition-colors hover:bg-muted/50', className)} {...props}>
      {children}
    </tr>
  ),
  th: ({ node, children, className, ...props }) => (
    <th className={cn('px-3 py-2 text-left text-xs font-medium text-muted-foreground whitespace-nowrap', className)} {...props}>
      {children}
    </th>
  ),
  td: ({ node, children, className, ...props }) => (
    <td className={cn('px-3 py-2 whitespace-nowrap', className)} {...props}>
      {children}
    </td>
  ),
  ol: ({ node, children, className, ...props }) => (
    <ol className={cn('ml-4 list-outside list-decimal', className)} {...props}>
      {children}
    </ol>
  ),
  li: ({ node, children, className, ...props }) => (
    <li className={cn('py-1', className)} {...props}>
      {children}
    </li>
  ),
  ul: ({ node, children, className, ...props }) => (
    <ul className={cn('ml-4 list-outside list-decimal', className)} {...props}>
      {children}
    </ul>
  ),
  p: ({ node, children, className, ...props }) => {
    const isImpactLevel = IMPACT_LEVEL_PATTERN.test(
      extractTextFromChildren(children)
    )

    return (
      <p
        className={cn(
          'leading-relaxed',
          isImpactLevel ? 'not-first:mt-6 mb-1' : 'mb-4',
          className
        )}
        {...props}
      >
        {children}
      </p>
    )
  },
  strong: ({ node, children, className, ...props }) => (
    <span className={cn('font-semibold', className)} {...props}>
      {children}
    </span>
  ),
  a: ({ node, children, className, ...props }) => (
    <a
      className={cn('text-primary font-medium underline', className)}
      rel='noreferrer'
      target='_blank'
      {...props}
    >
      {children}
    </a>
  ),
  h1: ({ node, children, className, ...props }) => (
    <h1
      className={cn('mt-6 mb-2 text-3xl font-semibold', className)}
      {...props}
    >
      {children}
    </h1>
  ),
  h2: ({ node, children, className, ...props }) => (
    <h2
      className={cn('mt-6 mb-2 text-2xl font-semibold', className)}
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ node, children, className, ...props }) => (
    <h3 className={cn('mt-6 mb-2 text-xl font-semibold', className)} {...props}>
      {children}
    </h3>
  ),
  h4: ({ node, children, className, ...props }) => (
    <h4 className={cn('mt-6 mb-2 text-lg font-semibold', className)} {...props}>
      {children}
    </h4>
  ),
  h5: ({ node, children, className, ...props }) => (
    <h5
      className={cn('mt-6 mb-2 text-base font-semibold', className)}
      {...props}
    >
      {children}
    </h5>
  ),
  h6: ({ node, children, className, ...props }) => (
    <h6 className={cn('mt-6 mb-2 text-sm font-semibold', className)} {...props}>
      {children}
    </h6>
  ),
  pre: ({ node, className, children }) => {
    let language = 'text'
    if (typeof node?.properties?.className === 'string') {
      language = node.properties.className.replace('language-', '')
    }
    const childrenIsCode =
      typeof children === 'object' &&
      children !== null &&
      'type' in children &&
      children.type === 'code'
    if (!childrenIsCode) {
      return <pre>{children}</pre>
    }

    const code = (children.props as { children: string }).children

    return (
      <SimpleCodeBlock
        className={cn('mb-4 h-auto', className)}
        code={code}
        language={language}
      />
    )
  },
}
export const AIResponse = memo(
  ({ className, options, children, ...props }: AIResponseProps) => {
    const markdown =
      typeof children === 'string'
        ? normalizeActionSpacing(normalizeImpactLevelSpacing(children))
        : children

    return (
      <div
        className={cn(
          'size-full [&>*:first-child]:mt-0 [&>*:last-child]:mb-0',
          className
        )}
        {...props}
      >
        <ReactMarkdown
          components={components}
          remarkPlugins={[remarkGfm]}
          {...options}
        >
          {markdown}
        </ReactMarkdown>
      </div>
    )
  },
  (prevProps, nextProps) => prevProps.children === nextProps.children
)
