import type React from 'react'
import { useState, useCallback, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload,
  Database,
  FileSpreadsheet,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  FileText,
  Layers,
  Trash2,
  Server,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button, buttonVariants } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  DATABASE_TYPE_OPTIONS,
  DATASOURCE_TYPE_LABELS,
  type DatasourceDatabaseType,
  type DatasourceRecord,
} from '@/api/datasources'
import {
  useConnectDatabaseDatasource,
  useDatasources,
  useDeleteDatasource,
  useUploadDatasourceFiles,
} from '@/hooks/use-datasources'

type ConnectionType = 'files' | 'database' | null
type Step = 'selection' | 'input' | 'connecting' | 'success' | 'error'

interface DatabaseConnectionModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const FILE_ACCEPT = '.csv,.xlsx,.xls,.parquet,.db,.sqlite,.sqlite3,.duckdb'

const DATASOURCE_TYPE_ICONS: Record<string, typeof FileText> = {
  csv: FileText,
  excel: FileSpreadsheet,
  sqlite: Database,
  parquet: Layers,
  postgres: Server,
  mysql: Server,
  mssql: Server,
  duckdb: Database,
  clickhouse: Server,
}

const DatasourceTypeIcon = ({ type }: { type: string }) => {
  const Icon = DATASOURCE_TYPE_ICONS[type] ?? Database
  return <Icon className='h-4 w-4 text-muted-foreground' />
}

function ExistingDatasourceList({
  datasources,
  isLoading,
  onDelete,
  isDeleting,
}: {
  datasources: DatasourceRecord[] | undefined
  isLoading: boolean
  onDelete: (datasource: DatasourceRecord) => void
  isDeleting: boolean
}) {
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
                  <span className='truncate text-sm font-medium'>
                    {ds.name}
                  </span>
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

export function DatabaseConnectionModal({
  open,
  onOpenChange,
}: DatabaseConnectionModalProps) {
  const { data: datasources, isLoading: isDatasourcesLoading } = useDatasources()
  const uploadFilesMutation = useUploadDatasourceFiles()
  const connectDbMutation = useConnectDatabaseDatasource()
  const deleteMutation = useDeleteDatasource()

  const [tab, setTab] = useState<'manage' | 'add'>('add')
  const [step, setStep] = useState<Step>('selection')
  const [connectionType, setConnectionType] = useState<ConnectionType>(null)
  const [progress, setProgress] = useState(0)
  const [dragActive, setDragActive] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [createdRecords, setCreatedRecords] = useState<DatasourceRecord[]>([])
  const [errorMessage, setErrorMessage] = useState('')
  const [errorDetails, setErrorDetails] = useState('')
  const [pendingDelete, setPendingDelete] = useState<DatasourceRecord | null>(
    null,
  )

  // Database form state
  const [dbName, setDbName] = useState('')
  const [dbType, setDbType] = useState<DatasourceDatabaseType>('postgres')
  const [dbConnectionString, setDbConnectionString] = useState('')
  const [dbHost, setDbHost] = useState('')
  const [dbPort, setDbPort] = useState<string>('')
  const [dbDatabase, setDbDatabase] = useState('')
  const [dbUser, setDbUser] = useState('')
  const [dbPassword, setDbPassword] = useState('')
  const [dbUseConnectionString, setDbUseConnectionString] = useState(false)

  const selectedDbTypeOption = useMemo(
    () => DATABASE_TYPE_OPTIONS.find((o) => o.value === dbType),
    [dbType],
  )

  const connectionOptions = [
    {
      id: 'files' as ConnectionType,
      title: 'Files',
      description: 'CSV, Excel, Parquet, SQLite, DuckDB',
      icon: FileSpreadsheet,
    },
    {
      id: 'database' as ConnectionType,
      title: 'Live database',
      description: 'Connect PostgreSQL, MySQL, or a DuckDB file',
      icon: Server,
    },
  ]

  const handleOptionSelect = (type: ConnectionType) => {
    setConnectionType(type)
    setStep('input')
  }

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFiles = Array.from(e.dataTransfer.files)
      setFiles((prev) => [...prev, ...droppedFiles])
    }
  }, [])

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles((prev) => [...prev, ...Array.from(e.target.files!)])
    }
  }

  const resetWizard = () => {
    setStep('selection')
    setConnectionType(null)
    setProgress(0)
    setFiles([])
    setCreatedRecords([])
    setErrorMessage('')
    setErrorDetails('')
    setDbName('')
    setDbType('postgres')
    setDbConnectionString('')
    setDbHost('')
    setDbPort('')
    setDbDatabase('')
    setDbUser('')
    setDbPassword('')
    setDbUseConnectionString(false)
  }

  const handleClose = (next: boolean) => {
    if (!next) {
      resetWizard()
      setTab('add')
    }
    onOpenChange(next)
  }

  const startProgress = () => {
    setProgress(0)
    setStep('connecting')
    const interval = setInterval(() => {
      setProgress((prev) => (prev >= 90 ? 90 : prev + 10))
    }, 250)
    return () => {
      clearInterval(interval)
      setProgress(100)
    }
  }

  const handleUpload = async () => {
    if (files.length === 0) return
    const stop = startProgress()
    try {
      const result = await uploadFilesMutation.mutateAsync(files)
      stop()
      setCreatedRecords(result.datasources)
      setTimeout(() => setStep('success'), 300)
      toast.success(result.message || 'Files uploaded')
    } catch (error) {
      stop()
      const message =
        (error as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ||
        (error instanceof Error ? error.message : 'Upload failed')
      setErrorMessage(message)
      setErrorDetails(error instanceof Error ? error.stack ?? '' : '')
      setStep('error')
    }
  }

  const handleConnectDb = async () => {
    if (!dbName.trim()) {
      toast.error('Please enter a name for the connection')
      return
    }
    const stop = startProgress()
    try {
      const payload = dbUseConnectionString
        ? {
            name: dbName.trim(),
            type: dbType,
            connection_string: dbConnectionString.trim() || undefined,
          }
        : {
            name: dbName.trim(),
            type: dbType,
            host: dbHost.trim() || undefined,
            port: dbPort ? Number(dbPort) : undefined,
            database: dbDatabase.trim() || undefined,
            user: dbUser.trim() || undefined,
            password: dbPassword || undefined,
          }
      const record = await connectDbMutation.mutateAsync(payload)
      stop()
      setCreatedRecords([record])
      setTimeout(() => setStep('success'), 300)
      toast.success(`Connected to ${record.name}`)
    } catch (error) {
      stop()
      const message =
        (error as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ||
        (error instanceof Error ? error.message : 'Connection failed')
      setErrorMessage(message)
      setErrorDetails(error instanceof Error ? error.stack ?? '' : '')
      setStep('error')
    }
  }

  const handleConfirmDelete = async () => {
    if (!pendingDelete) return
    try {
      await deleteMutation.mutateAsync(pendingDelete.id)
      toast.success(`Removed ${pendingDelete.name}`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to remove')
    } finally {
      setPendingDelete(null)
    }
  }

  const createdViews = useMemo(
    () => createdRecords.flatMap((r) => r.view_names),
    [createdRecords],
  )

  const isProcessing =
    uploadFilesMutation.isPending || connectDbMutation.isPending

  const dbDefaultPort = selectedDbTypeOption?.defaultPort

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className='max-h-[85vh] min-w-3xl overflow-y-auto'>
        <DialogHeader>
          <DialogTitle className='text-center text-2xl font-bold'>
            Datasources{' '}
          </DialogTitle>
        </DialogHeader>

        <Tabs
          value={tab}
          onValueChange={(v) => {
            setTab(v as 'manage' | 'add')
            if (v === 'add') resetWizard()
          }}
          className='mt-2'
        >
          <TabsList className='grid w-full grid-cols-2'>
            <TabsTrigger value='add'>Add new</TabsTrigger>
            <TabsTrigger value='manage'>
              Registered{' '}
              <Badge variant='secondary' className='ml-2'>
                {datasources?.length ?? 0}
              </Badge>
            </TabsTrigger>
          </TabsList>

          <TabsContent value='manage' className='pt-4'>
            <ExistingDatasourceList
              datasources={datasources}
              isLoading={isDatasourcesLoading}
              onDelete={setPendingDelete}
              isDeleting={deleteMutation.isPending}
            />
          </TabsContent>

          <TabsContent value='add' className='pt-2'>
            <AnimatePresence mode='wait'>
              {step === 'selection' && (
                <motion.div
                  key='selection'
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  className='py-2'
                >
                  <div className='grid grid-cols-2 gap-4'>
                    {connectionOptions.map((option) => (
                      <button
                        key={option.id}
                        type='button'
                        className='group flex flex-col items-start gap-3 rounded-lg border bg-card p-6 text-left transition-colors hover:border-primary hover:bg-accent'
                        onClick={() => handleOptionSelect(option.id)}
                      >
                        <div className='rounded-md bg-primary/10 p-2 text-primary'>
                          <option.icon className='h-6 w-6' />
                        </div>
                        <div>
                          <h3 className='text-base font-semibold'>
                            {option.title}
                          </h3>
                          <p className='text-sm text-muted-foreground'>
                            {option.description}
                          </p>
                        </div>
                      </button>
                    ))}
                  </div>
                  <div className='mt-4 rounded-md border border-dashed bg-muted/30 px-4 py-3 text-sm text-muted-foreground'>
                    <strong className='text-foreground'>Heads up:</strong>{' '}
                    Files are read directly from disk; databases are attached
                    live. Schema is introspected once at registration and the
                    sandbox queries everything through DuckDB.
                  </div>
                </motion.div>
              )}

              {step === 'input' && connectionType === 'files' && (
                <motion.div
                  key='files-input'
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  className='py-4'
                >
                  <div
                    className={`rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
                      dragActive
                        ? 'border-primary bg-primary/5'
                        : 'border-muted-foreground/25'
                    }`}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                  >
                    <Upload className='text-muted-foreground mx-auto mb-3 h-12 w-12' />
                    <p className='mb-1 text-lg font-medium'>Drop files here</p>
                    <p className='text-muted-foreground mb-3 text-sm'>
                      CSV · Excel (.xlsx/.xls) · Parquet · SQLite (.db/.sqlite)
                      · DuckDB
                    </p>
                    <Input
                      type='file'
                      multiple
                      accept={FILE_ACCEPT}
                      onChange={handleFileInput}
                      className='hidden'
                      id='datasource-file-upload'
                    />
                    <Label
                      htmlFor='datasource-file-upload'
                      className={buttonVariants({
                        variant: 'outline',
                        className: 'cursor-pointer bg-transparent',
                      })}
                    >
                      Choose files
                    </Label>
                  </div>

                  {files.length > 0 && (
                    <div className='mt-4'>
                      <h4 className='mb-2 font-medium'>Selected files</h4>
                      <div className='space-y-2'>
                        {files.map((file, index) => (
                          <div
                            key={`${file.name}-${index}`}
                            className='bg-muted flex items-center justify-between rounded p-2'
                          >
                            <span className='truncate text-sm'>
                              {file.name}
                            </span>
                            <Button
                              variant='ghost'
                              size='sm'
                              onClick={() =>
                                setFiles(files.filter((_, i) => i !== index))
                              }
                            >
                              Remove
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className='mt-6 flex justify-between'>
                    <Button
                      variant='outline'
                      onClick={() => setStep('selection')}
                    >
                      Back
                    </Button>
                    <Button
                      onClick={handleUpload}
                      disabled={files.length === 0 || isProcessing}
                    >
                      {isProcessing
                        ? 'Registering...'
                        : `Register ${files.length || ''} file${files.length === 1 ? '' : 's'}`.trim()}
                    </Button>
                  </div>
                </motion.div>
              )}

              {step === 'input' && connectionType === 'database' && (
                <motion.div
                  key='database-input'
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  className='space-y-4 py-2'
                >
                  <div className='grid grid-cols-2 gap-3'>
                    <div>
                      <Label htmlFor='db-name'>Connection name</Label>
                      <Input
                        id='db-name'
                        className='mt-1'
                        placeholder='e.g. analytics_warehouse'
                        value={dbName}
                        onChange={(e) => setDbName(e.target.value)}
                      />
                    </div>
                    <div>
                      <Label htmlFor='db-type'>Database type</Label>
                      <Select
                        value={dbType}
                        onValueChange={(v) =>
                          setDbType(v as DatasourceDatabaseType)
                        }
                      >
                        <SelectTrigger id='db-type' className='mt-1 w-full'>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {DATABASE_TYPE_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className='flex items-center gap-2 text-sm'>
                    <input
                      id='use-conn-string'
                      type='checkbox'
                      checked={dbUseConnectionString}
                      onChange={(e) =>
                        setDbUseConnectionString(e.target.checked)
                      }
                      className='h-4 w-4 rounded border border-input'
                    />
                    <Label
                      htmlFor='use-conn-string'
                      className='cursor-pointer text-muted-foreground'
                    >
                      Use a connection string instead of structured fields
                    </Label>
                  </div>

                  {dbUseConnectionString ? (
                    <div>
                      <Label htmlFor='db-conn-string'>Connection URL</Label>
                      <Input
                        id='db-conn-string'
                        className='mt-1 font-mono text-xs'
                        placeholder={
                          dbType === 'postgres'
                            ? 'postgresql://user:pass@host:5432/db'
                            : dbType === 'mysql'
                              ? 'mysql://user:pass@host:3306/db'
                              : '/path/to/file.duckdb'
                        }
                        value={dbConnectionString}
                        onChange={(e) => setDbConnectionString(e.target.value)}
                      />
                      <p className='text-muted-foreground mt-1 text-xs'>
                        For DuckDB, this is the path to the file on the
                        sandbox container.
                      </p>
                    </div>
                  ) : (
                    <div className='grid grid-cols-2 gap-3'>
                      {dbType === 'duckdb' ? (
                        <div className='col-span-2'>
                          <Label htmlFor='duckdb-path'>DuckDB file path</Label>
                          <Input
                            id='duckdb-path'
                            className='mt-1 font-mono text-xs'
                            placeholder='/data/datasources/files/analytics.duckdb'
                            value={dbDatabase}
                            onChange={(e) => setDbDatabase(e.target.value)}
                          />
                        </div>
                      ) : (
                        <>
                          <div>
                            <Label htmlFor='db-host'>Host</Label>
                            <Input
                              id='db-host'
                              className='mt-1'
                              placeholder='localhost'
                              value={dbHost}
                              onChange={(e) => setDbHost(e.target.value)}
                            />
                          </div>
                          <div>
                            <Label htmlFor='db-port'>Port</Label>
                            <Input
                              id='db-port'
                              className='mt-1'
                              type='number'
                              placeholder={dbDefaultPort?.toString() ?? '5432'}
                              value={dbPort}
                              onChange={(e) => setDbPort(e.target.value)}
                            />
                          </div>
                          <div>
                            <Label htmlFor='db-database'>Database</Label>
                            <Input
                              id='db-database'
                              className='mt-1'
                              placeholder='mydb'
                              value={dbDatabase}
                              onChange={(e) => setDbDatabase(e.target.value)}
                            />
                          </div>
                          <div>
                            <Label htmlFor='db-user'>User</Label>
                            <Input
                              id='db-user'
                              className='mt-1'
                              placeholder='postgres'
                              value={dbUser}
                              onChange={(e) => setDbUser(e.target.value)}
                            />
                          </div>
                          <div className='col-span-2'>
                            <Label htmlFor='db-password'>Password</Label>
                            <Input
                              id='db-password'
                              className='mt-1'
                              type='password'
                              value={dbPassword}
                              onChange={(e) => setDbPassword(e.target.value)}
                            />
                          </div>
                        </>
                      )}
                    </div>
                  )}

                  <div className='rounded-md border border-blue-200 bg-blue-50 p-3 text-xs text-blue-700 dark:border-blue-900 dark:bg-blue-950/50 dark:text-blue-200'>
                    <strong>Note:</strong> The database is{' '}
                    <em>attached live</em> through DuckDB — your data stays in
                    place. Only schema metadata is cached.
                  </div>

                  <div className='flex justify-between'>
                    <Button
                      variant='outline'
                      onClick={() => setStep('selection')}
                    >
                      Back
                    </Button>
                    <Button
                      onClick={handleConnectDb}
                      disabled={!dbName.trim() || isProcessing}
                    >
                      {isProcessing ? 'Connecting...' : 'Connect'}
                    </Button>
                  </div>
                </motion.div>
              )}

              {step === 'connecting' && (
                <motion.div
                  key='connecting'
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  className='space-y-6 py-8 text-center'
                >
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
                    <p className='text-muted-foreground text-sm'>
                      {progress}%
                    </p>
                  </div>
                </motion.div>
              )}

              {step === 'success' && (
                <motion.div
                  key='success'
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  className='space-y-5 py-6 text-center'
                >
                  <div className='space-y-2'>
                    <CheckCircle className='mx-auto h-14 w-14 text-green-500' />
                    <h3 className='text-xl font-semibold text-green-600'>
                      Registered{' '}
                      {createdRecords.length === 1
                        ? '1 datasource'
                        : `${createdRecords.length} datasources`}
                    </h3>
                    <p className='text-muted-foreground text-sm'>
                      {createdViews.length}{' '}
                      {createdViews.length === 1 ? 'view' : 'views'} are now
                      queryable.
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
                          <Badge
                            variant='secondary'
                            className='ml-auto text-[10px]'
                          >
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
                    <Button
                      variant='outline'
                      onClick={() => {
                        resetWizard()
                        setTab('add')
                      }}
                    >
                      Add another
                    </Button>
                    <Button onClick={() => handleClose(false)}>Done</Button>
                  </div>
                </motion.div>
              )}

              {step === 'error' && (
                <motion.div
                  key='error'
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  className='space-y-5 py-6 text-center'
                >
                  <div className='space-y-3'>
                    <AlertCircle className='mx-auto h-14 w-14 text-red-500' />
                    <h3 className='text-xl font-semibold text-red-600'>
                      Registration failed
                    </h3>
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
                    <Button
                      variant='outline'
                      onClick={() => setStep('selection')}
                    >
                      Back to start
                    </Button>
                    <Button
                      onClick={() => setStep('input')}
                      className='flex items-center gap-2'
                    >
                      <RefreshCw className='h-4 w-4' />
                      Retry
                    </Button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </TabsContent>
        </Tabs>
      </DialogContent>

      <AlertDialog
        open={!!pendingDelete}
        onOpenChange={(o) => !o && setPendingDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove datasource?</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingDelete && (
                <>
                  <strong>{pendingDelete.name}</strong> (
                  {DATASOURCE_TYPE_LABELS[pendingDelete.type] ??
                    pendingDelete.type}
                  ) will be deregistered. Files uploaded to the registry are
                  removed from disk; remote connections are simply forgotten.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className='bg-destructive text-destructive-foreground hover:bg-destructive/90'
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Dialog>
  )
}
