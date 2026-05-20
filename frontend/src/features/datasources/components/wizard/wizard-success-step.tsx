import { CheckCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { DATASOURCE_TYPE_LABELS, type DatasourceRecord } from '@/services/api/datasources'
import { DatasourceTypeIcon } from '@/features/datasources/lib/datasource-type-icon'
import { WizardStepShell } from '@/features/datasources/components/wizard/wizard-step-shell'

interface WizardSuccessStepProps {
  createdRecords: DatasourceRecord[]
  createdViewsCount: number
  onAddAnother: () => void
  onDone: () => void
}

export function WizardSuccessStep({
  createdRecords,
  createdViewsCount,
  onAddAnother,
  onDone,
}: WizardSuccessStepProps) {
  return (
    <WizardStepShell stepKey='success' className='space-y-5 py-6 text-center'>
      <div className='space-y-2'>
        <CheckCircle className='mx-auto h-14 w-14 text-green-500' />
        <h3 className='text-xl font-semibold text-green-600'>
          Registered{' '}
          {createdRecords.length === 1
            ? '1 datasource'
            : `${createdRecords.length} datasources`}
        </h3>
        <p className='text-muted-foreground text-sm'>
          {createdViewsCount}{' '}
          {createdViewsCount === 1 ? 'view' : 'views'} are now queryable.
        </p>
      </div>

      <div className='mx-auto max-w-md space-y-3 text-left'>
        {createdRecords.map((record) => (
          <div
            key={record.id}
            className='rounded-md border bg-muted/30 p-3'
          >
            <div className='flex items-center gap-2'>
              <DatasourceTypeIcon type={record.type} />
              <span className='font-medium'>{record.name}</span>
              <Badge variant='secondary' className='ml-auto text-[10px]'>
                {DATASOURCE_TYPE_LABELS[record.type] ?? record.type}
              </Badge>
            </div>
            <div className='mt-2 flex flex-wrap gap-1'>
              {record.view_names.map((view) => (
                <span
                  key={view}
                  className='rounded bg-background px-1.5 py-0.5 font-mono text-[10px]'
                >
                  {view}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className='flex justify-center gap-3'>
        <Button variant='outline' onClick={onAddAnother}>
          Add another
        </Button>
        <Button onClick={onDone}>Done</Button>
      </div>
    </WizardStepShell>
  )
}
