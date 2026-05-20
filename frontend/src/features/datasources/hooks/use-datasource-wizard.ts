import { useState, useCallback } from 'react'
import type { DatasourceRecord } from '@/services/api/datasources'
import type {
  ConnectionType,
  DatasourceModalTab,
  WizardStep,
} from '@/features/datasources/types'

export function useDatasourceWizard(onOpenChange: (open: boolean) => void) {
  const [tab, setTab] = useState<DatasourceModalTab>('add')
  const [step, setStep] = useState<WizardStep>('selection')
  const [connectionType, setConnectionType] = useState<ConnectionType | null>(
    null
  )
  const [progress, setProgress] = useState(0)
  const [createdRecords, setCreatedRecords] = useState<DatasourceRecord[]>([])
  const [errorMessage, setErrorMessage] = useState('')
  const [errorDetails, setErrorDetails] = useState('')

  const resetWizard = useCallback(() => {
    setStep('selection')
    setConnectionType(null)
    setProgress(0)
    setCreatedRecords([])
    setErrorMessage('')
    setErrorDetails('')
  }, [])

  const setError = useCallback((message: string, details: string) => {
    setErrorMessage(message)
    setErrorDetails(details)
    setStep('error')
  }, [])

  const handleClose = useCallback(
    (next: boolean) => {
      if (!next) {
        resetWizard()
        setTab('add')
      }
      onOpenChange(next)
    },
    [onOpenChange, resetWizard]
  )

  const startProgress = useCallback(() => {
    setProgress(0)
    setStep('connecting')
    const interval = setInterval(() => {
      setProgress((prev) => (prev >= 90 ? 90 : prev + 10))
    }, 250)
    return () => {
      clearInterval(interval)
      setProgress(100)
    }
  }, [])

  const selectConnectionType = useCallback((type: ConnectionType) => {
    setConnectionType(type)
    setStep('input')
  }, [])

  const handleTabChange = useCallback(
    (value: string) => {
      setTab(value as DatasourceModalTab)
      if (value === 'add') resetWizard()
    },
    [resetWizard]
  )

  return {
    tab,
    setTab,
    step,
    setStep,
    connectionType,
    progress,
    createdRecords,
    setCreatedRecords,
    errorMessage,
    errorDetails,
    resetWizard,
    setError,
    handleClose,
    startProgress,
    selectConnectionType,
    handleTabChange,
  }
}
