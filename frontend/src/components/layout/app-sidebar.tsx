import React from 'react'
import { useSidebarData } from '@/hooks/use-sidebar-data'
import { useTranslation } from '@/context/locale-context'
import {
  Sidebar,
  SidebarContent,
  SidebarRail,
} from '@/components/ui/sidebar'
import { NavGroup } from '@/components/layout/nav-group'
import { SidebarFooterActions } from '@/components/layout/sidebar-footer-actions'
import { SidebarHeaderBar } from '@/components/layout/sidebar-header-bar'
import NewAnalysisBtn from './new-analysis-btn'

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { data: sidebarData, isLoading, error } = useSidebarData()
  const { t } = useTranslation()

  if (isLoading || !sidebarData) {
    return (
      <Sidebar collapsible='icon' {...props}>
        <SidebarHeaderBar />
        <SidebarContent>
          <div className='px-3 py-2'>{t('sidebar.preparing')}</div>
        </SidebarContent>
        <SidebarFooterActions />
        <SidebarRail />
      </Sidebar>
    )
  }

  if (error) {
    return (
      <Sidebar collapsible='icon' {...props}>
        <SidebarHeaderBar />
        <SidebarContent>
          <div className='px-3 py-2 text-red-500'>{t('sidebar.failedToLoad')}</div>
        </SidebarContent>
        <SidebarFooterActions />
        <SidebarRail />
      </Sidebar>
    )
  }

  return (
    <Sidebar collapsible='icon' {...props}>
      <SidebarHeaderBar />
      <SidebarContent>
        <NewAnalysisBtn />
        {sidebarData.navGroups.map((props) => (
          <NavGroup key={props.title} {...props} />
        ))}
      </SidebarContent>
      <SidebarFooterActions />
      <SidebarRail />
    </Sidebar>
  )
}
