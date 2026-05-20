import { FileSpreadsheet, Server } from 'lucide-react'
import type { ConnectionType } from '@/features/datasources/types'

export const FILE_ACCEPT =
  '.csv,.xlsx,.xls,.parquet,.db,.sqlite,.sqlite3,.duckdb'

export const CONNECTION_OPTIONS: {
  id: ConnectionType
  title: string
  description: string
  icon: typeof FileSpreadsheet
}[] = [
  {
    id: 'files',
    title: 'Files',
    description: 'CSV, Excel, Parquet, SQLite, DuckDB',
    icon: FileSpreadsheet,
  },
  {
    id: 'database',
    title: 'Live database',
    description: 'Connect PostgreSQL, MySQL, or a DuckDB file',
    icon: Server,
  },
]
