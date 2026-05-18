import { useMemo, useCallback } from 'react'
import { IconDatabase, IconPlus, IconClock, IconBrain } from '@tabler/icons-react'
import { useTableList } from '@/hooks/use-table-list'
import { DATASOURCE_TYPE_LABELS } from '@/api/datasources'
import { type SidebarData } from '@/components/layout/types'
import {
  useSharedAnalysisHistory,
  type AnalysisHistoryItem,
  type AnalysisHistoryKind,
} from '@/context/analysis-history-context'
import { useDeleteSpace } from '@/hooks/use-analysis'
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
  const deleteSpaceMutation = useDeleteSpace()
  const navigate = useNavigate()
  const location = useLocation()

  const handleDelete = useCallback(
    (deletedId: string, kind: AnalysisHistoryKind) => {
      if (kind === 'standard') {
        deleteSpaceMutation.mutate(deletedId, {
          onError: () => {
            // Space may not exist on backend (e.g. server restarted), that's fine
          },
        })
      }
      removeFromHistory(deletedId)
      toast.success('Conversation deleted')
      if (location.pathname === `/report/${deletedId}`) {
        navigate({ to: '/' })
      }
      if (location.pathname === '/agents') {
        const params = new URLSearchParams(location.search)
        if (params.get('session') === deletedId) {
          navigate({ to: '/agents', search: {} })
        }
      }
    },
    [deleteSpaceMutation, removeFromHistory, navigate, location.pathname, location.search]
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
          title: 'Multi-Agent',
          icon: IconBrain,
          items: [
          {
            title: 'New Agent Analysis',
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
              onDelete: (id: string) => handleDelete(id, item.kind),
              ...(item.isLoading ? { icon: Bars } : {}),
            })),
          ...(history.filter((i: AnalysisHistoryItem) => i.kind === 'agent').length === 0
            ? [{ title: 'No agent analyses yet', url: '#' as any }]
            : []),
          ],
        },
        {
          title: 'Recent',
          icon: IconClock,
          items: [
          {
            title: 'New Analysis',
            url: '/' as any,
            icon: IconPlus,
          },
          ...history
            .filter((item: AnalysisHistoryItem) => item.kind === 'standard')
            .map((item: AnalysisHistoryItem) => ({
              title: item.query,
              url: `/report/${item.id}` as any,
              id: item.id,
              onDelete: (id: string) => handleDelete(id, item.kind),
              ...(item.isLoading ? { icon: Bars } : {}),
            })),
          ...(history.filter((i: AnalysisHistoryItem) => i.kind === 'standard').length === 0
            ? [{ title: 'No recent analyses', url: '#' as any }]
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
