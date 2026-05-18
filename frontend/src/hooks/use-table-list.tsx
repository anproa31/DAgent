import { useQuery } from '@tanstack/react-query'
import {
  type DatasourceRecord,
  type DatasourceType,
  listDatasources,
} from '@/api/datasources'

export interface TableInfo {
  /** DuckDB view / table name the sandbox exposes. */
  name: string
  /** Route to the table preview page. */
  url: string
  /** Parent datasource id. */
  datasourceId: string
  /** Parent datasource display name. */
  datasourceName: string
  /** Datasource type (csv, excel, sqlite, parquet, postgres, mysql, ...). */
  datasourceType: DatasourceType
}

/**
 * Flatten registered datasources into the per-view list the rest of the
 * frontend expects. Each `view_name` becomes a `TableInfo`, but we keep a
 * reference back to the owning datasource so the UI can group/label rows
 * by their original source.
 */
const flattenDatasources = (records: DatasourceRecord[]): TableInfo[] => {
  const tables: TableInfo[] = []
  for (const record of records) {
    for (const viewName of record.view_names) {
      tables.push({
        name: viewName,
        url: `/table/${viewName}`,
        datasourceId: record.id,
        datasourceName: record.name,
        datasourceType: record.type,
      })
    }
  }
  return tables
}

const fetchTableList = async (): Promise<TableInfo[]> => {
  const records = await listDatasources()
  return flattenDatasources(records)
}

export const useTableList = () => {
  return useQuery({
    queryKey: ['tableList'],
    queryFn: fetchTableList,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  })
}
