import { useMemo, useCallback } from 'react'
import { IconDatabase, IconClock, IconPin, IconBook2, IconWand } from '@tabler/icons-react'
import { deleteSession } from '@/api/agentApi'
import { useTableList } from '@/hooks/use-table-list'
import { type SidebarData } from '@/components/layout/types'
import {
  useSharedAnalysisHistory,
  type AnalysisHistoryItem,
} from '@/context/analysis-history-context'
import { useNavigate, useLocation } from '@tanstack/react-router'
import { toast } from 'sonner'
import { SidebarLoadingSpinner } from '@/components/shared/spinner/sidebar-loading-spinner'
import { useLocale, useTranslation } from '@/context/locale-context'

export const useSidebarData = (): {
  data: SidebarData | null
  isLoading: boolean
  error: Error | null
} => {
  const { data: tables, isLoading: tablesLoading, error: tablesError } = useTableList()
  const {
    history,
    pinnedIds,
    isPinned,
    togglePin,
    removeFromHistory,
    refreshAgentSessionsFromServer,
  } = useSharedAnalysisHistory()
  const navigate = useNavigate()
  const location = useLocation()
  const { locale } = useLocale()
  const { t } = useTranslation()

  const handleDelete = useCallback(
    (deletedId: string) => {
      const item = history.find((h) => h.id === deletedId)
      const isAgent = item?.kind === 'agent'

      // Optimistic: drop from the sidebar and leave the open session immediately so the
      // UI updates in real time, regardless of backend latency.
      removeFromHistory(deletedId)
      toast.success(t('toast.conversationDeleted'))
      if (location.pathname === '/agents') {
        const params = new URLSearchParams(location.search)
        if (params.get('session') === deletedId) {
          navigate({ to: '/agents', search: {} })
        }
      }

      if (!isAgent) return

      // Persist the soft-delete in the background; on failure resync from the server
      // (the row still exists there) so the conversation reappears.
      void deleteSession(deletedId).catch(() => {
        toast.error(t('toast.couldNotDeleteConversation'))
        void refreshAgentSessionsFromServer()
      })
    },
    [
      removeFromHistory,
      refreshAgentSessionsFromServer,
      navigate,
      location.pathname,
      location.search,
      history,
      t,
    ]
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
      ...(item.isLoading ? { icon: SidebarLoadingSpinner } : {}),
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
              title: t('nav.allDatasources'),
              icon: IconDatabase,
              url: '/datasources',
            },
            {
              title: t('nav.knowledgeBase'),
              icon: IconBook2,
              url: '/knowledge-base',
            },
            {
              title: t('nav.skills'),
              icon: IconWand,
              url: '/skills',
            },
            {
              id: 'pinned',
              title: t('nav.pinned'),
              icon: IconPin,
              items: [
                ...pinnedItems,
                ...(pinnedItems.length === 0
                  ? [{ title: t('nav.noPinned'), url: '/agents' as const, placeholder: true }]
                  : []),
              ],
            },
            {
              id: 'history',
              title: t('nav.history'),
              icon: IconClock,
              items: [
                ...historyItems,
                ...(historyItems.length === 0
                  ? [{ title: t('nav.noHistory'), url: '/agents' as const, placeholder: true }]
                  : []),
              ],
            },
          ],
        },
      ],
    }
  }, [tables, history, pinnedIds, isPinned, togglePin, handleDelete, locale, t])

  return {
    data: sidebarData,
    isLoading: tablesLoading,
    error: tablesError,
  }
}
