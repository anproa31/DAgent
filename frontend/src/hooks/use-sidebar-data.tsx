import { useMemo, useCallback } from 'react'
import { IconDatabase, IconClock, IconPin } from '@tabler/icons-react'
import { deleteSession } from '@/api/agentApi'
import { useTableList } from '@/hooks/use-table-list'
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
  const { data: tables, isLoading: tablesLoading, error: tablesError } = useTableList()
  const { history, pinnedIds, isPinned, togglePin, removeFromHistory } = useSharedAnalysisHistory()
  const navigate = useNavigate()
  const location = useLocation()

  const handleDelete = useCallback(
    (deletedId: string) => {
      const item = history.find((h) => h.id === deletedId)
      void (async () => {
        if (item?.kind === 'agent') {
          try {
            await deleteSession(deletedId)
          } catch {
            toast.error('Could not delete conversation on server')
            return
          }
        }
        removeFromHistory(deletedId)
        toast.success('Conversation deleted')
        if (location.pathname === '/agents') {
          const params = new URLSearchParams(location.search)
          if (params.get('session') === deletedId) {
            navigate({ to: '/agents', search: {} })
          }
        }
      })()
    },
    [removeFromHistory, navigate, location.pathname, location.search, history]
  )

  const sidebarData = useMemo((): SidebarData | null => {
    if (!tables) return null

    const agentHistory = history.filter(
      (item: AnalysisHistoryItem) => item.kind === 'agent'
    )

    const toNavItem = (item: AnalysisHistoryItem) => ({
      title: item.query,
      url: '/agents' as const,
      search: { session: item.id } as Record<string, unknown>,
      id: item.id,
      onDelete: (id: string) => handleDelete(id),
      onPinToggle: (id: string) => togglePin(id),
      isPinned: isPinned(item.id),
      ...(item.isLoading ? { icon: Bars } : {}),
    })

    const pinnedSet = new Set(pinnedIds)
    const pinnedItems = agentHistory
      .filter((item) => pinnedSet.has(item.id))
      .map(toNavItem)
    const historyItems = agentHistory.map(toNavItem)

    return {
      navGroups: [
        {
          title: '',
          items: [
            {
              title: 'All Datasources',
              icon: IconDatabase,
              url: '/datasources',
            },
            {
              title: 'Pinned',
              icon: IconPin,
              items: [
                ...pinnedItems,
                ...(pinnedItems.length === 0
                  ? [{ title: 'No pinned conversations', url: '/agents' as const, placeholder: true }]
                  : []),
              ],
            },
            {
              title: 'History',
              icon: IconClock,
              items: [
                ...historyItems,
                ...(historyItems.length === 0
                  ? [{ title: 'No analyses yet', url: '/agents' as const, placeholder: true }]
                  : []),
              ],
            },
          ],
        },
      ],
    }
  }, [tables, history, pinnedIds, isPinned, togglePin, handleDelete])

  return {
    data: sidebarData,
    isLoading: tablesLoading,
    error: tablesError,
  }
}
