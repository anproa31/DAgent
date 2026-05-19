import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'

import { listSessions } from '@/api/agentApi'

export type AnalysisHistoryKind = 'standard' | 'agent'

export interface AnalysisHistoryItem {
  id: string
  query: string
  timestamp: number
  isLoading: boolean
  /** standard = space/report flow; agent = multi-agent runs */
  kind: AnalysisHistoryKind
}

interface AnalysisHistoryContextType {
  history: AnalysisHistoryItem[]
  addToHistory: (id: string, query: string, kind?: AnalysisHistoryKind) => void
  /** Same sidebar row: swap agent session id (e.g. after edit → fork new backend session). */
  replaceAgentHistorySession: (
    previousSessionId: string,
    nextSessionId: string,
    query: string
  ) => void
  /** Update sidebar label when LLM title is ready (local + storage). */
  updateHistoryTitle: (id: string, title: string) => void
  /** Merge persisted agent session titles from the backend (fallback after run completes). */
  refreshAgentSessionsFromServer: () => Promise<void>
  removeFromHistory: (id: string) => void
  clearHistory: () => void
  setItemLoading: (id: string, isLoading: boolean) => void
}

const AnalysisHistoryCtx = createContext<AnalysisHistoryContextType| null>(null)

export const AnalysisHistoryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const value = useAnalysisHistory()
  return <AnalysisHistoryCtx.Provider value={value}>{children}</AnalysisHistoryCtx.Provider>
}
/**
 *  Unify `history` across the global scope. 
*/
export const useSharedAnalysisHistory = () => {
  const ctx = useContext(AnalysisHistoryCtx)
  if (!ctx) throw new Error('useSharedAnalysisHistory must be used within Provider')
  return ctx
}

const STORAGE_KEY = 'analysis_history'
const MAX_HISTORY_ITEMS = 1000

function mergeAgentSessionsFromServer(
  base: AnalysisHistoryItem[],
  sessions: { session_id: string; title: string; updated_at: string }[]
): AnalysisHistoryItem[] {
  const standard = base.filter((x) => x.kind === 'standard')
  const localAgents = base.filter((x) => x.kind === 'agent')
  const serverList = sessions ?? []
  const fromServer = serverList.map((s) => {
    const loc = localAgents.find((l) => l.id === s.session_id)
    return {
      id: s.session_id,
      query: s.title || 'Analysis',
      timestamp: new Date(s.updated_at).getTime(),
      isLoading: loc?.isLoading ?? false,
      kind: 'agent' as AnalysisHistoryKind,
    }
  })
  const serverIds = new Set(fromServer.map((s) => s.id))
  const strayAgents = localAgents.filter((l) => !serverIds.has(l.id))
  const agentMerged = [...fromServer, ...strayAgents].sort(
    (a, b) => b.timestamp - a.timestamp
  )
  return [...agentMerged, ...standard]
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, MAX_HISTORY_ITEMS)
}

const useAnalysisHistory = () => {
  const [history, setHistory] = useState<AnalysisHistoryItem[]>([])

  // Hydrate from localStorage, then merge persisted agent sessions from the backend
  useEffect(() => {
    let cancelled = false
    let initial: AnalysisHistoryItem[] = []
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        initial = (JSON.parse(stored) as AnalysisHistoryItem[]).map((item) => ({
          ...item,
          kind: item.kind ?? 'standard',
        }))
      }
    } catch (error) {
      console.error('Failed to load analysis history:', error)
    }
    setHistory(initial)

    void (async () => {
      try {
        const { sessions } = await listSessions()
        if (cancelled) return
        setHistory((prev) => {
          const base = prev.length > 0 ? prev : initial
          const merged = mergeAgentSessionsFromServer(base, sessions ?? [])
          try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(merged))
          } catch (e) {
            console.error('Failed to save analysis history:', e)
          }
          return merged
        })
      } catch {
        /* agent service unavailable — keep local snapshots only */
      }
    })()

    return () => {
      cancelled = true
    }
  }, [])

  // Save history to localStorage
  const saveToStorage = useCallback((newHistory: AnalysisHistoryItem[]) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newHistory))
    } catch (error) {
      console.error('Failed to save analysis history:', error)
    }
  }, [])

  // Add new analysis to history
  const addToHistory = useCallback((id: string, query: string, kind: AnalysisHistoryKind = 'standard') => {
    const newItem: AnalysisHistoryItem = {
      id,
      query,
      timestamp: Date.now(),
      isLoading: true,
      kind,
    }

      setHistory((prevHistory) => {
        // Remove item with the same ID (avoid duplicates)
        const filteredHistory = prevHistory.filter((item) => item.id !== id)

        // Prepend new item and remove oldest if over limit
        const newHistory = [newItem, ...filteredHistory].slice(
          0,
          MAX_HISTORY_ITEMS
        )

        // Save to storage first
        saveToStorage(newHistory)

        // Debug log
        console.log('Analysis history updated:', {
          newItem,
          previousCount: prevHistory.length,
          newCount: newHistory.length,
        })

        return newHistory
      })

  }, [saveToStorage])

  const updateHistoryTitle = useCallback(
    (id: string, title: string) => {
      const trimmed = title.trim()
      if (!id?.trim() || !trimmed) return
      setHistory((prevHistory) => {
        const newHistory = prevHistory.map((item) =>
          item.id === id ? { ...item, query: trimmed } : item
        )
        saveToStorage(newHistory)
        return newHistory
      })
    },
    [saveToStorage]
  )

  const refreshAgentSessionsFromServer = useCallback(async () => {
    try {
      const { sessions } = await listSessions()
      setHistory((prev) => {
        const merged = mergeAgentSessionsFromServer(prev, sessions ?? [])
        saveToStorage(merged)
        return merged
      })
    } catch {
      /* agent service unavailable */
    }
  }, [saveToStorage])

  const replaceAgentHistorySession = useCallback(
    (previousSessionId: string, nextSessionId: string, query: string) => {
      if (!previousSessionId?.trim() || !nextSessionId?.trim()) return
      setHistory((prevHistory) => {
        const withoutDupNext = prevHistory.filter(
          (item) => !(item.kind === 'agent' && item.id === nextSessionId)
        )
        let replaced = false
        const mapped = withoutDupNext.map((item) => {
          if (item.kind === 'agent' && item.id === previousSessionId) {
            replaced = true
            return {
              ...item,
              id: nextSessionId,
              query,
              timestamp: Date.now(),
              isLoading: true,
            }
          }
          return item
        })
        const newHistory = (
          replaced
            ? mapped
            : [
                {
                  id: nextSessionId,
                  query,
                  timestamp: Date.now(),
                  isLoading: true,
                  kind: 'agent' as AnalysisHistoryKind,
                },
                ...mapped,
              ]
        ).slice(0, MAX_HISTORY_ITEMS)
        saveToStorage(newHistory)
        return newHistory
      })
    },
    [saveToStorage]
  )

  // Remove a specific item from history
  const removeFromHistory = useCallback(
    (id: string) => {
      setHistory((prevHistory) => {
        const newHistory = prevHistory.filter((item) => item.id !== id)
        saveToStorage(newHistory)
        return newHistory
      })
    },
    [saveToStorage]
  )

  // Clear history
  const clearHistory = useCallback(() => {
    setHistory([])
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch (error) {
      console.error('Failed to clear analysis history:', error)
    }
  }, [saveToStorage])

  // Update boolean value controlling the loader icon
  const setItemLoading = useCallback((id: string, isLoading: boolean) => {
    setHistory(prev => {
      const newHistory = prev.map(item =>
        item.id === id
        ? {...item, isLoading: isLoading}
        : item
      )
      saveToStorage(newHistory)
      return newHistory
    })
  }, [saveToStorage])

  return {
    history,
    setItemLoading,
    addToHistory,
    replaceAgentHistorySession,
    updateHistoryTitle,
    refreshAgentSessionsFromServer,
    removeFromHistory,
    clearHistory,
  }
}
