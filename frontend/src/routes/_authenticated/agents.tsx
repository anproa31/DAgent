import { createFileRoute } from '@tanstack/react-router'
import AgentsPage from '@/features/agents'

export const Route = createFileRoute('/_authenticated/agents')({
  validateSearch: (search: Record<string, unknown>): { session?: string } => ({
    session:
      typeof search.session === 'string' && search.session.length > 0
        ? search.session
        : undefined,
  }),
  component: AgentsPage,
})
