import { useEffect, useMemo } from 'react'
import { AnimatePresence } from 'framer-motion'
import { ConnectionTypeSelection } from '@/features/datasources/components/wizard/connection-type-selection'
import { FileUploadStep } from '@/features/datasources/components/wizard/file-upload-step'
import { DatabaseConnectStep } from '@/features/datasources/components/wizard/database-connect-step'
import { WizardConnectingStep } from '@/features/datasources/components/wizard/wizard-connecting-step'
import { WizardSuccessStep } from '@/features/datasources/components/wizard/wizard-success-step'
import { WizardErrorStep } from '@/features/datasources/components/wizard/wizard-error-step'
import { useDatasourceWizard } from '@/features/datasources/hooks/use-datasource-wizard'
import { useFileUploadFlow } from '@/features/datasources/hooks/use-file-upload-flow'
import { useDatabaseConnectForm } from '@/features/datasources/hooks/use-database-connect-form'
import type { DatasourceRecord } from '@/services/api/datasources'

interface AddDatasourceWizardProps {
  wizard: ReturnType<typeof useDatasourceWizard>
  onDone: () => void
  onAddAnother: () => void
}

export function AddDatasourceWizard({
  wizard,
  onDone,
  onAddAnother,
}: AddDatasourceWizardProps) {
  const {
    step,
    setStep,
    connectionType,
    progress,
    createdRecords,
    setCreatedRecords,
    errorMessage,
    errorDetails,
    setError,
    startProgress,
    selectConnectionType,
  } = wizard

  const onFlowSuccess = (records: DatasourceRecord[]) => {
    setCreatedRecords(records)
    setTimeout(() => setStep('success'), 300)
  }

  const fileFlow = useFileUploadFlow({
    startProgress,
    onSuccess: onFlowSuccess,
    onError: setError,
  })

  const dbForm = useDatabaseConnectForm({
    startProgress,
    onSuccess: onFlowSuccess,
    onError: setError,
  })

  const isProcessing = fileFlow.isUploading || dbForm.isConnecting

  useEffect(() => {
    if (step === 'selection' && connectionType === null) {
      fileFlow.resetFiles()
      dbForm.resetForm()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset side effects when wizard returns to start
  }, [step, connectionType])

  const createdViewsCount = useMemo(
    () => createdRecords.flatMap((r) => r.view_names).length,
    [createdRecords]
  )

  return (
    <AnimatePresence mode='wait'>
      {step === 'selection' && (
        <ConnectionTypeSelection onSelect={selectConnectionType} />
      )}

      {step === 'input' && connectionType === 'files' && (
        <FileUploadStep
          flow={fileFlow}
          isProcessing={isProcessing}
          onBack={() => setStep('selection')}
        />
      )}

      {step === 'input' && connectionType === 'database' && (
        <DatabaseConnectStep
          form={dbForm}
          isProcessing={isProcessing}
          onBack={() => setStep('selection')}
        />
      )}

      {step === 'connecting' && (
        <WizardConnectingStep
          connectionType={connectionType}
          progress={progress}
        />
      )}

      {step === 'success' && (
        <WizardSuccessStep
          createdRecords={createdRecords}
          createdViewsCount={createdViewsCount}
          onAddAnother={onAddAnother}
          onDone={onDone}
        />
      )}

      {step === 'error' && (
        <WizardErrorStep
          errorMessage={errorMessage}
          errorDetails={errorDetails}
          onBackToStart={() => setStep('selection')}
          onRetry={() => setStep('input')}
        />
      )}
    </AnimatePresence>
  )
}
