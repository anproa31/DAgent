import { useMemo, useCallback } from 'react'
import { IconDatabase, IconPlus, IconBrain } from '@tabler/icons-react'
import { useTableList } from '@/hooks/use-table-list'
import { DATASOURCE_TYPE_LABELS } from '@/api/datasources'
import { type SidebarData } from '@/components/layout/types'
import {
  useSharedAnalysisHistory,
  type AnalysisHistoryItem,
} from '@/context/analysis-history-context'
import { useNavigate, useLocation } from '@tanstack/react-router'
import { toast } from 'sonner'
import Bars from '@/components/ui/shadcn-io/spinner/Bars'

export const useSidebarData = (): {
  data: SidebarData | null
  isLoading: boolean
  error: Error | null
} => {
  const { data: tables, isLoading, error } = useTableList()
  const { history, removeFromHistory } = useSharedAnalysisHistory()
  const navigate = useNavigate()
  const location = useLocation()

  const handleDelete = useCallback(
    (deletedId: string) => {
      removeFromHistory(deletedId)
      toast.success('Conversation deleted')
      if (location.pathname === '/agents') {
        const params = new URLSearchParams(location.search)
        if (params.get('session') === deletedId) {
          navigate({ to: '/agents', search: {} })
        }
      }
    },
    [removeFromHistory, navigate, location.pathname, location.search]
  )

  const sidebarData = useMemo((): SidebarData | null => {
    if (!tables) return null

    const hasUserDatabaseUrl = import.meta.env.USER_DATABASE_URL || ""

    return {
      navGroups: [
      {
        title: '',
        items: [
        {
          title: 'Database',
          icon: IconDatabase,
          items: [
          ...(hasUserDatabaseUrl == ""
            ? [
              {
              title: 'New Table',
              action: 'openModal' as const,
              icon: IconPlus,
              },
            ]
            : []),
          ...tables.map((table) => ({
            title: table.name,
            url: `/table/${table.name}` as any,
            badge: DATASOURCE_TYPE_LABELS[table.datasourceType] ?? table.datasourceType,
          })),
          ],
        },
        {
          title: 'Analysis',
          icon: IconBrain,
          items: [
          {
            title: 'New Analysis',
            url: '/agents' as any,
            search: {} as Record<string, unknown>,
            icon: IconPlus,
          },
          ...history
            .filter((item: AnalysisHistoryItem) => item.kind === 'agent')
            .map((item: AnalysisHistoryItem) => ({
              title: item.query,
              url: '/agents' as any,
              search: { session: item.id } as Record<string, unknown>,
              id: item.id,
              onDelete: (id: string) => handleDelete(id),
              ...(item.isLoading ? { icon: Bars } : {}),
            })),
          ...(history.filter((i: AnalysisHistoryItem) => i.kind === 'agent').length === 0
            ? [{ title: 'No analyses yet', url: '#' as any }]
            : []),
          ],
        },
        ],
      },
      ],
    }
  }, [tables, history, handleDelete])

  return {
    data: sidebarData,
    isLoading,
    error,
  }
}
