import { Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { DATASOURCE_TYPE_LABELS, type DatasourceRecord } from '@/services/api/datasources'
import { DatasourceTypeIcon } from '@/features/datasources/lib/datasource-type-icon'

export interface ExistingDatasourceListProps {
  datasources: DatasourceRecord[] | undefined
  isLoading: boolean
  onDelete: (datasource: DatasourceRecord) => void
  isDeleting: boolean
}

export function ExistingDatasourceList({
  datasources,
  isLoading,
  onDelete,
  isDeleting,
}: ExistingDatasourceListProps) {
  if (isLoading) {
    return (
      <p className='text-sm text-muted-foreground'>Loading datasources...</p>
    )
  }
  if (!datasources?.length) {
    return (
      <p className='text-sm text-muted-foreground'>
        No datasources registered yet. Add one in the <strong>Add new</strong>{' '}
        tab.
      </p>
    )
  }
  return (
    <ScrollArea className='h-72 rounded-md border'>
      <div className='divide-y'>
        {datasources.map((ds) => (
          <div
            key={ds.id}
            className='flex items-start justify-between gap-3 px-3 py-2.5'
          >
            <div className='flex flex-1 items-start gap-2 min-w-0'>
              <div className='mt-0.5'>
                <DatasourceTypeIcon type={ds.type} />
              </div>
              <div className='min-w-0 flex-1'>
                <div className='flex items-center gap-2'>
                  <span className='truncate text-sm font-medium'>{ds.name}</span>
                  <Badge variant='secondary' className='shrink-0 text-[10px]'>
                    {DATASOURCE_TYPE_LABELS[ds.type] ?? ds.type}
                  </Badge>
                </div>
                <div className='mt-1 flex flex-wrap gap-1'>
                  {ds.view_names.slice(0, 6).map((view) => (
                    <span
                      key={view}
                      className='rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]'
                    >
                      {view}
                    </span>
                  ))}
                  {ds.view_names.length > 6 && (
                    <span className='text-[10px] text-muted-foreground'>
                      +{ds.view_names.length - 6} more
                    </span>
                  )}
                </div>
                {ds.error && (
                  <p className='mt-1 text-xs text-destructive line-clamp-2'>
                    {ds.error}
                  </p>
                )}
              </div>
            </div>
            <Button
              variant='ghost'
              size='icon'
              className='h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive'
              onClick={() => onDelete(ds)}
              disabled={isDeleting}
              title='Remove datasource'
            >
              <Trash2 className='h-3.5 w-3.5' />
            </Button>
          </div>
        ))}
      </div>
    </ScrollArea>
  )
}
