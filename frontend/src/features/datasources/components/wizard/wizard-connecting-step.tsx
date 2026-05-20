import { Progress } from '@/components/ui/progress'
import { WizardStepShell } from '@/features/datasources/components/wizard/wizard-step-shell'
import type { ConnectionType } from '@/features/datasources/types'

interface WizardConnectingStepProps {
  connectionType: ConnectionType | null
  progress: number
}

export function WizardConnectingStep({
  connectionType,
  progress,
}: WizardConnectingStepProps) {
  return (
    <WizardStepShell stepKey='connecting' className='space-y-6 py-8 text-center'>
      <div className='space-y-4'>
        <div className='border-primary mx-auto h-8 w-8 animate-spin rounded-full border-4 border-t-transparent' />
        <h3 className='text-xl font-semibold'>
          {connectionType === 'files'
            ? 'Introspecting files...'
            : 'Connecting & introspecting schema...'}
        </h3>
        <p className='text-muted-foreground text-sm'>
          DuckDB is scanning columns and building previews.
        </p>
      </div>
      <div className='space-y-2'>
        <Progress value={progress} className='w-full' />
        <p className='text-muted-foreground text-sm'>{progress}%</p>
      </div>
    </WizardStepShell>
  )
}
