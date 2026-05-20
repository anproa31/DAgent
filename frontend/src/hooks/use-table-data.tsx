import {
  useQuery,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query'
import {
  fetchTableData,
  deleteTable,
  type TableDataParams,
} from '@/services/api/tables'

export type { TableDataResponse, TableDataParams } from '@/services/api/tables'

export const useTableData = (
  tableName: string,
  params: TableDataParams = {}
) => {
  return useQuery({
    queryKey: ['tableData', tableName, params],
    queryFn: () => fetchTableData(tableName, params),
    staleTime: 2 * 60 * 1000,
    refetchOnWindowFocus: false,
    enabled: !!tableName,
  })
}

export const useInfiniteTableData = (
  tableName: string,
  baseParams: Omit<TableDataParams, 'offset'> = {}
) => {
  return useInfiniteQuery({
    queryKey: ['infiniteTableData', tableName, baseParams],
    queryFn: ({ pageParam = 0 }) =>
      fetchTableData(tableName, { ...baseParams, offset: pageParam }),
    getNextPageParam: (lastPage, allPages) => {
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
