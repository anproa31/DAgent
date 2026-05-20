import { CONNECTION_OPTIONS } from '@/features/datasources/lib/constants'
import type { ConnectionType } from '@/features/datasources/types'
import { WizardStepShell } from '@/features/datasources/components/wizard/wizard-step-shell'

interface ConnectionTypeSelectionProps {
  onSelect: (type: ConnectionType) => void
}

export function ConnectionTypeSelection({ onSelect }: ConnectionTypeSelectionProps) {
  return (
    <WizardStepShell stepKey='selection' className='py-2'>
      <div className='grid grid-cols-2 gap-4'>
        {CONNECTION_OPTIONS.map((option) => (
          <button
            key={option.id}
            type='button'
            className='group flex flex-col items-start gap-3 rounded-lg border bg-card p-6 text-left transition-colors hover:border-primary hover:bg-accent'
            onClick={() => onSelect(option.id)}
          >
            <div className='rounded-md bg-primary/10 p-2 text-primary'>
              <option.icon className='h-6 w-6' />
            </div>
            <div>
              <h3 className='text-base font-semibold'>{option.title}</h3>
              <p className='text-sm text-muted-foreground'>{option.description}</p>
            </div>
          </button>
        ))}
      </div>
      <div className='mt-4 rounded-md border border-dashed bg-muted/30 px-4 py-3 text-sm text-muted-foreground'>
        <strong className='text-foreground'>Heads up:</strong> Files are read
        directly from disk; databases are attached live. Schema is introspected
        once at registration and the sandbox queries everything through DuckDB.
      </div>
    </WizardStepShell>
  )
}
