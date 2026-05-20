import { serverClient } from '@/services/api/client'

export interface TableDataResponse {
  table_name: string
  columns: string[]
  data: Record<string, unknown>[]
  total_rows: number
  preview_rows: number
}

export interface TableDataParams {
  limit?: number
  offset?: number
  sort_column?: string
  sort_direction?: 'asc' | 'desc'
  filter_column?: string
  filter_value?: string
}

export const fetchTableData = async (
  tableName: string,
  params: TableDataParams = {}
): Promise<TableDataResponse> => {
  const res = await serverClient.get<TableDataResponse>(
    `/api/table-data/${encodeURIComponent(tableName)}`,
    { params }
  )
  return res.data
}

export const deleteTable = async (tableName: string): Promise<void> => {
  await serverClient.delete(`/api/delete-table/${encodeURIComponent(tableName)}`)
}
