import logo from '@/assets/olazc9.svg'
import { SidebarHeader, SidebarTrigger, useSidebar } from '@/components/ui/sidebar'
import { cn } from '@/lib/utils'

export function SidebarHeaderBar() {
  const { state, isMobile } = useSidebar()
  const isCollapsed = state === 'collapsed' && !isMobile

  return (
    <SidebarHeader className='shrink-0'>
      <div
        className={cn(
          'flex w-full items-center py-2',
          isCollapsed
            ? 'flex-col justify-center gap-4 px-1 py-3'
            : 'flex-row justify-between gap-2 px-2'
        )}
      >
        <img
          src={logo}
          alt='data-analysis-agent logo'
          className={cn('shrink-0', isCollapsed ? 'h-6 w-6' : 'h-8 w-auto')}
        />
        <SidebarTrigger variant='outline' className='shrink-0' />
      </div>
    </SidebarHeader>
  )
}
