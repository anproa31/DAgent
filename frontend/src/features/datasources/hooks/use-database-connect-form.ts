import { useState, useMemo, useCallback } from 'react'
import { toast } from 'sonner'
import {
  DATABASE_TYPE_OPTIONS,
  type CreateDatabaseDatasourcePayload,
  type DatasourceDatabaseType,
  type DatasourceRecord,
} from '@/services/api/datasources'
import { parseDatasourceError } from '@/features/datasources/lib/parse-datasource-error'
import { useConnectDatabaseDatasource } from '@/hooks/use-datasources'

interface UseDatabaseConnectFormOptions {
  startProgress: () => () => void
  onSuccess: (records: DatasourceRecord[]) => void
  onError: (message: string, details: string) => void
}

export function useDatabaseConnectForm({
  startProgress,
  onSuccess,
  onError,
}: UseDatabaseConnectFormOptions) {
  const connectMutation = useConnectDatabaseDatasource()

  const [dbName, setDbName] = useState('')
  const [dbType, setDbType] = useState<DatasourceDatabaseType>('postgres')
  const [dbConnectionString, setDbConnectionString] = useState('')
  const [dbHost, setDbHost] = useState('')
  const [dbPort, setDbPort] = useState('')
  const [dbDatabase, setDbDatabase] = useState('')
  const [dbUser, setDbUser] = useState('')
  const [dbPassword, setDbPassword] = useState('')
  const [dbUseConnectionString, setDbUseConnectionString] = useState(false)

  const dbDefaultPort = useMemo(
    () => DATABASE_TYPE_OPTIONS.find((o) => o.value === dbType)?.defaultPort,
    [dbType]
  )

  const resetForm = useCallback(() => {
    setDbName('')
    setDbType('postgres')
    setDbConnectionString('')
    setDbHost('')
    setDbPort('')
    setDbDatabase('')
    setDbUser('')
    setDbPassword('')
    setDbUseConnectionString(false)
  }, [])

  const buildPayload = (): CreateDatabaseDatasourcePayload => {
    if (dbUseConnectionString) {
      return {
        name: dbName.trim(),
        type: dbType,
        connection_string: dbConnectionString.trim() || undefined,
      }
    }
    return {
      name: dbName.trim(),
      type: dbType,
      host: dbHost.trim() || undefined,
      port: dbPort ? Number(dbPort) : undefined,
      database: dbDatabase.trim() || undefined,
      user: dbUser.trim() || undefined,
      password: dbPassword || undefined,
    }
  }

  const handleConnect = async () => {
    if (!dbName.trim()) {
      toast.error('Please enter a name for the connection')
      return
    }
    const stop = startProgress()
    try {
      const record = await connectMutation.mutateAsync(buildPayload())
      stop()
      onSuccess([record])
      toast.success(`Connected to ${record.name}`)
    } catch (error) {
      stop()
      const { message, details } = parseDatasourceError(
        error,
        'Connection failed'
      )
      onError(message, details)
    }
  }

  return {
    dbName,
    setDbName,
    dbType,
    setDbType,
    dbConnectionString,
    setDbConnectionString,
    dbHost,
    setDbHost,
    dbPort,
    setDbPort,
    dbDatabase,
    setDbDatabase,
    dbUser,
    setDbUser,
    dbPassword,
    setDbPassword,
    dbUseConnectionString,
    setDbUseConnectionString,
    dbDefaultPort,
    resetForm,
    handleConnect,
    isConnecting: connectMutation.isPending,
  }
}
