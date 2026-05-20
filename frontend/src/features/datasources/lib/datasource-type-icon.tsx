import {
  Database,
  FileSpreadsheet,
  FileText,
  Layers,
  Server,
} from 'lucide-react'

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

export function DatasourceTypeIcon({ type }: { type: string }) {
  const Icon = DATASOURCE_TYPE_ICONS[type] ?? Database
  return <Icon className='h-4 w-4 text-muted-foreground' />
}
