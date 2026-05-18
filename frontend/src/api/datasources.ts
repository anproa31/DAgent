import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_SERVER_URL || 'http://localhost:8000'

// ---------------------------------------------------------------------------
// Types (mirrored from app/src/models/datasource.py)
// ---------------------------------------------------------------------------

export type DatasourceKind = 'file' | 'database'

export type DatasourceFileType = 'csv' | 'excel' | 'sqlite' | 'parquet'

export type DatasourceDatabaseType =
  | 'postgres'
  | 'mysql'
  | 'mssql'
  | 'duckdb'
  | 'clickhouse'

export type DatasourceType = DatasourceFileType | DatasourceDatabaseType

export interface DatasourceTableInfo {
  name: string
  column_count: number
  row_count: number | null
  description?: string | null
}

export interface DatasourceRecord {
  id: string
  name: string
  kind: DatasourceKind
  type: DatasourceType
  config: Record<string, unknown>
  view_names: string[]
  tables: DatasourceTableInfo[]
  schema_markdown: string
  created_at: string
  error?: string | null
}

export interface DatasourceListResponse {
  datasources: DatasourceRecord[]
}

export interface CreateFileDatasourceResponse {
  datasources: DatasourceRecord[]
  message: string
}

export interface CreateDatabaseDatasourcePayload {
  name: string
  type: DatasourceDatabaseType
  host?: string
  port?: number
  database?: string
  user?: string
  password?: string
  connection_string?: string
  additional_properties?: Record<string, unknown>
}

export interface DeleteDatasourceResponse {
  success: boolean
  deleted_id: string
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const listDatasources = async (): Promise<DatasourceRecord[]> => {
  const res = await axios.get<DatasourceListResponse>(
    `${API_BASE_URL}/api/datasources`,
  )
  return res.data.datasources
}

export const uploadDatasourceFiles = async (
  files: File[],
): Promise<CreateFileDatasourceResponse> => {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f))
  const res = await axios.post<CreateFileDatasourceResponse>(
    `${API_BASE_URL}/api/datasources/upload`,
    formData,
  )
  return res.data
}

export const connectDatabaseDatasource = async (
  payload: CreateDatabaseDatasourcePayload,
): Promise<DatasourceRecord> => {
  const res = await axios.post<DatasourceRecord>(
    `${API_BASE_URL}/api/datasources/connect`,
    payload,
  )
  return res.data
}

export const deleteDatasource = async (
  datasourceId: string,
): Promise<DeleteDatasourceResponse> => {
  const res = await axios.delete<DeleteDatasourceResponse>(
    `${API_BASE_URL}/api/datasources/${datasourceId}`,
  )
  return res.data
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

export const DATASOURCE_TYPE_LABELS: Record<DatasourceType, string> = {
  csv: 'CSV',
  excel: 'Excel',
  sqlite: 'SQLite',
  parquet: 'Parquet',
  postgres: 'PostgreSQL',
  mysql: 'MySQL',
  mssql: 'SQL Server',
  duckdb: 'DuckDB',
  clickhouse: 'ClickHouse',
}

export const DATABASE_TYPE_OPTIONS: {
  value: DatasourceDatabaseType
  label: string
  defaultPort?: number
}[] = [
  { value: 'postgres', label: 'PostgreSQL', defaultPort: 5432 },
  { value: 'mysql', label: 'MySQL', defaultPort: 3306 },
  { value: 'duckdb', label: 'DuckDB (file)' },
]
