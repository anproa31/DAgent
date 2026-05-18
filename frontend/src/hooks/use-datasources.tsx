import {
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query'
import {
  type CreateDatabaseDatasourcePayload,
  type DatasourceRecord,
  connectDatabaseDatasource,
  deleteDatasource,
  listDatasources,
  uploadDatasourceFiles,
} from '@/api/datasources'

const DATASOURCES_KEY = ['datasources'] as const

const invalidateAfterMutation = (queryClient: ReturnType<typeof useQueryClient>) => {
  queryClient.invalidateQueries({ queryKey: DATASOURCES_KEY })
  queryClient.invalidateQueries({ queryKey: ['tableList'] })
  queryClient.invalidateQueries({ queryKey: ['tableData'] })
  queryClient.invalidateQueries({ queryKey: ['infiniteTableData'] })
}

export const useDatasources = () =>
  useQuery({
    queryKey: DATASOURCES_KEY,
    queryFn: listDatasources,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

export const useUploadDatasourceFiles = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: uploadDatasourceFiles,
    onSuccess: () => invalidateAfterMutation(queryClient),
  })
}

export const useConnectDatabaseDatasource = () => {
  const queryClient = useQueryClient()
  return useMutation<DatasourceRecord, Error, CreateDatabaseDatasourcePayload>({
    mutationFn: connectDatabaseDatasource,
    onSuccess: () => invalidateAfterMutation(queryClient),
  })
}

export const useDeleteDatasource = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteDatasource,
    onSuccess: () => invalidateAfterMutation(queryClient),
  })
}
