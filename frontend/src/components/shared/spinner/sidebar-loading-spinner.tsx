import { cn } from '@/lib/utils'
import { Spinner } from '@/components/shared/spinner'

/** Compact bars spinner for sidebar history loading rows. */
export function SidebarLoadingSpinner({ className }: { className?: string }) {
  return <Spinner variant='bars' className={cn('size-4', className)} />
}
