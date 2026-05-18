import axios from 'axios'
import {
  useQuery,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query'

const API_BASE_URL = import.meta.env.VITE_SERVER_URL || 'http://localhost:8000'

export interface TableDataResponse {
  table_name: string
  columns: string[]
  data: Record<string, any>[]
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

const fetchTableData = async (
  tableName: string,
  params: TableDataParams = {}
): Promise<TableDataResponse> => {
  const response = await axios.get<TableDataResponse>(
    `${API_BASE_URL}/api/table-data/${encodeURIComponent(tableName)}`,
    {
      params,
    }
  )
  return response.data
}

// Delete a DuckDB view (compat shim that removes the parent datasource).
const deleteTable = async (tableName: string): Promise<void> => {
  const response = await axios.delete(
    `${API_BASE_URL}/api/delete-table/${encodeURIComponent(tableName)}`
  )
  return response.data
}

export const useTableData = (
  tableName: string,
  params: TableDataParams = {}
) => {
  return useQuery({
    queryKey: ['tableData', tableName, params],
    queryFn: () => fetchTableData(tableName, params),
    staleTime: 2 * 60 * 1000, // Cache for 2 minutes
    refetchOnWindowFocus: false,
    enabled: !!tableName, // Only run query if tableName exists
  })
}

// Hook for infinite scroll
export const useInfiniteTableData = (
  tableName: string,
  baseParams: Omit<TableDataParams, 'offset'> = {}
) => {
  return useInfiniteQuery({
    queryKey: ['infiniteTableData', tableName, baseParams],
    queryFn: ({ pageParam = 0 }) =>
      fetchTableData(tableName, { ...baseParams, offset: pageParam }),
    getNextPageParam: (lastPage, allPages) => {
      // Check if there is a next page
      const totalFetched = allPages.reduce(
        (sum, page) => sum + page.preview_rows,
        0
      )
      return totalFetched < lastPage.total_rows ? totalFetched : undefined
    },
    staleTime: 2 * 60 * 1000,
    refetchOnWindowFocus: false,
    enabled: !!tableName,
    initialPageParam: 0,
  })
}

// Hook for table deletion
export const useDeleteTable = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteTable,
    onSuccess: (_, tableName: string) => {
      queryClient.invalidateQueries({ queryKey: ['tableList'] })
      queryClient.invalidateQueries({ queryKey: ['datasources'] })
      queryClient.removeQueries({ queryKey: ['tableData', tableName] })
      queryClient.removeQueries({ queryKey: ['infiniteTableData', tableName] })
    },
  })
}
