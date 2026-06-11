import { ThemeSwitch } from '@/components/theme-switch'
import { Setting } from '@/components/setting'
import { LanguageSwitch } from '@/components/language-switch'
import { SidebarFooter, useSidebar } from '@/components/ui/sidebar'
import { cn } from '@/lib/utils'

export function SidebarFooterActions() {
  const { state, isMobile } = useSidebar()
  const isCollapsed = state === 'collapsed' && !isMobile

  return (
    <SidebarFooter className='mt-auto shrink-0 border-t'>
      <div
        className={cn(
          'flex w-full items-center p-2',
          isCollapsed
            ? 'min-h-28 flex-col justify-between gap-2'
            : 'flex-row justify-between gap-1'
        )}
      >
        {isCollapsed ? (
          <>
            <div className='flex flex-col items-center gap-2'>
              <ThemeSwitch />
              <Setting />
            </div>
            <LanguageSwitch />
          </>
        ) : (
          <>
            <LanguageSwitch />
            <ThemeSwitch />
            <Setting />
          </>
        )}
      </div>
    </SidebarFooter>
  )
}
