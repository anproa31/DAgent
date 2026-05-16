import { useMemo, useCallback } from 'react'
import { IconDatabase, IconPlus, IconClock } from '@tabler/icons-react'
import { useTableList } from '@/hooks/use-table-list'
import { type SidebarData } from '@/components/layout/types'
import { useSharedAnalysisHistory } from '@/context/analysis-history-context'
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

  const handleDelete = useCallback((id: string) => {
    // Attempt backend deletion (fire-and-forget, ignore 404s for local-only entries)
    deleteSpaceMutation.mutate(id, {
      onError: () => {
        // Space may not exist on backend (e.g. server restarted), that's fine
      },
    })
    // Always remove from local history
    removeFromHistory(id)
    toast.success('Conversation deleted')
    // Navigate to home if the user is currently viewing the deleted conversation
    if (location.pathname === `/report/${id}`) {
      navigate({ to: '/' })
    }
  }, [deleteSpaceMutation, removeFromHistory, navigate, location.pathname])

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
          })),
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
          ...history.map((item) => ({
            title: item.query,
            url: `/report/${item.id}` as any,
            id: item.id,
            onDelete: handleDelete,
            ...(item.isLoading ? { icon: Bars } : {}),
          })),
          ...(history.length === 0
            ? [
              {
              title: 'No recent analyses',
              url: '#' as any,
              },
            ]
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
