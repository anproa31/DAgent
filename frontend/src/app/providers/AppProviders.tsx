import { StrictMode, type ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { AnalysisHistoryProvider } from '@/context/analysis-history-context'
import { SettingsProvider } from '@/context/settings-context'
import { ThemeProvider } from '@/context/theme-context'
import { FontProvider } from '@/context/font-context'
import type { AppRouter } from '@/app/router'
import type { QueryClient } from '@tanstack/react-query'

interface AppProvidersProps {
  queryClient: QueryClient
  router: AppRouter
  children?: ReactNode
}

export function AppProviders({ queryClient, router, children }: AppProvidersProps) {
  return (
    <StrictMode>
      <AnalysisHistoryProvider>
        <SettingsProvider>
          <QueryClientProvider client={queryClient}>
            <ThemeProvider defaultTheme='light' storageKey='vite-ui-theme'>
              <FontProvider>
                {children ?? <RouterProvider router={router} />}
              </FontProvider>
            </ThemeProvider>
          </QueryClientProvider>
        </SettingsProvider>
      </AnalysisHistoryProvider>
    </StrictMode>
  )
}
