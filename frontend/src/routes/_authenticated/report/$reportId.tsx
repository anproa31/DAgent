import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/report/$reportId')({
  beforeLoad: () => {
    throw redirect({ to: '/agents' })
  },
  component: () => null,
})
