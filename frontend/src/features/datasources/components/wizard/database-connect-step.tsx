import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DATABASE_TYPE_OPTIONS,
  type DatasourceDatabaseType,
} from '@/services/api/datasources'
import { WizardStepShell } from '@/features/datasources/components/wizard/wizard-step-shell'
import type { useDatabaseConnectForm } from '@/features/datasources/hooks/use-database-connect-form'

type DatabaseConnectForm = ReturnType<typeof useDatabaseConnectForm>

interface DatabaseConnectStepProps {
  form: DatabaseConnectForm
  isProcessing: boolean
  onBack: () => void
}

export function DatabaseConnectStep({
  form,
  isProcessing,
  onBack,
}: DatabaseConnectStepProps) {
  const {
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
    handleConnect,
  } = form

  return (
    <WizardStepShell stepKey='database-input' className='space-y-4 py-2'>
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
            onValueChange={(v) => setDbType(v as DatasourceDatabaseType)}
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
          onChange={(e) => setDbUseConnectionString(e.target.checked)}
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
            For DuckDB, this is the path to the file on the sandbox container.
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
        <strong>Note:</strong> The database is <em>attached live</em> through
        DuckDB — your data stays in place. Only schema metadata is cached.
      </div>

      <div className='flex justify-between'>
        <Button variant='outline' onClick={onBack}>
          Back
        </Button>
        <Button
          onClick={handleConnect}
          disabled={!dbName.trim() || isProcessing}
        >
          {isProcessing ? 'Connecting...' : 'Connect'}
        </Button>
      </div>
    </WizardStepShell>
  )
}
