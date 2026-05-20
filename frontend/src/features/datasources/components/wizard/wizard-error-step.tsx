import { AlertCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { WizardStepShell } from '@/features/datasources/components/wizard/wizard-step-shell'

interface WizardErrorStepProps {
  errorMessage: string
  errorDetails: string
  onBackToStart: () => void
  onRetry: () => void
}

export function WizardErrorStep({
  errorMessage,
  errorDetails,
  onBackToStart,
  onRetry,
}: WizardErrorStepProps) {
  return (
    <WizardStepShell stepKey='error' className='space-y-5 py-6 text-center'>
      <div className='space-y-3'>
        <AlertCircle className='mx-auto h-14 w-14 text-red-500' />
        <h3 className='text-xl font-semibold text-red-600'>Registration failed</h3>
        <div className='mx-auto max-w-md text-left'>
          <div className='rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200'>
            {errorMessage}
          </div>
          {errorDetails && (
            <details className='mt-3'>
              <summary className='text-muted-foreground cursor-pointer text-xs font-medium'>
                Details
              </summary>
              <pre className='bg-muted text-muted-foreground mt-2 max-h-32 overflow-y-auto rounded-md p-3 text-xs'>
                {errorDetails}
              </pre>
            </details>
          )}
        </div>
      </div>
      <div className='flex justify-center gap-3'>
        <Button variant='outline' onClick={onBackToStart}>
          Back to start
        </Button>
        <Button onClick={onRetry} className='flex items-center gap-2'>
          <RefreshCw className='h-4 w-4' />
          Retry
        </Button>
      </div>
    </WizardStepShell>
  )
}
