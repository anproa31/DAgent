import React from 'react'
import logo from '@/assets/olazc9.svg'
import { useSidebarData } from '@/hooks/use-sidebar-data'
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar'
import { NavGroup } from '@/components/layout/nav-group'
import NewAnalysisBtn from './new-analysis-btn'
import { DatabaseConnectionModal } from '@/components/layout/database-connection-modal'

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
    const { state, isMobile } = useSidebar()
  const { data: sidebarData, isLoading, error } = useSidebarData()
  const [modalOpen, setModalOpen] = React.useState(false)

  if (isLoading || !sidebarData) {
    return (
      <Sidebar collapsible='icon' {...props}>
        <SidebarHeader>
          <div className='px-3 py-2'>Loading...</div>
        </SidebarHeader>
        <SidebarContent>
          <div className='px-3 py-2'>Preparing...</div>
        </SidebarContent>
        <SidebarRail />
      </Sidebar>
    )
  }

  if (error) {
    return (
      <Sidebar collapsible='icon' {...props}>
        <SidebarHeader>
          <div className='px-3 py-2'>Error</div>
        </SidebarHeader>
        <SidebarContent>
          <div className='px-3 py-2 text-red-500'>Failed to load.</div>
        </SidebarContent>
        <SidebarRail />
      </Sidebar>
    )
  }

  return (
    <>
      <Sidebar collapsible='icon' {...props}>
        <SidebarHeader>
          <div className={isMobile || state === 'expanded' ? 'px-3 py-2' : 'flex items-center justify-center py-2'}>
            <img src={logo} alt='data-analysis-agent logo' className={isMobile || state === 'expanded' ? 'h-8 w-auto' : 'h-6 w-6'} />
          </div>
        </SidebarHeader>
        <SidebarContent>
          <NewAnalysisBtn />
          {sidebarData.navGroups.map((props) => (
            <NavGroup key={props.title} {...props} onModalOpen={setModalOpen} />
          ))}
        </SidebarContent>
        <SidebarRail />
      </Sidebar>
      <DatabaseConnectionModal open={modalOpen} onOpenChange={setModalOpen} />
    </>
  )
}
