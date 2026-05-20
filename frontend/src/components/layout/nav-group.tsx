import { ReactNode, useState } from 'react'
import { Link, useLocation } from '@tanstack/react-router'
import { Trash2 } from 'lucide-react'
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from '@/components/ui/sidebar'
import { Badge } from '../ui/badge'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog'
import { NavCollapsible, NavItem, NavLink, NavAction, type NavGroup } from './types'

const NavBadge = ({ children }: { children: ReactNode }) => (
  <Badge className='rounded-full px-1 py-0 text-xs'>{children}</Badge>
)

const DeleteConfirmDialog = ({
  open,
  onOpenChange,
  onConfirm,
  itemTitle,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  itemTitle: string
}) => (
  <AlertDialog open={open} onOpenChange={onOpenChange}>
    <AlertDialogContent>
      <AlertDialogHeader>
        <AlertDialogTitle>Delete conversation?</AlertDialogTitle>
        <AlertDialogDescription>
          This will permanently delete "<strong>{itemTitle}</strong>" from your history. This action cannot be undone.
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel>Cancel</AlertDialogCancel>
        <AlertDialogAction
          onClick={onConfirm}
          className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
        >
          Delete
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
)

export function NavGroup({
  title,
  items,
  onModalOpen,
}: NavGroup & { onModalOpen?: (open: boolean) => void }) {
  const { state, isMobile } = useSidebar()
  const href = useLocation({ select: (location) => location.href })

  const datasourceItem = items.find(item => item.title === 'All Datasources')
  const newDatasourceItem = items.find(item => item.title === 'New Datasource')
  const historyItem = items.find(item => item.title === 'History')

  const isCollapsed = state === 'collapsed' && !isMobile
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null)

  return (
    <SidebarGroup className='min-h-0 flex flex-col gap-0'>
      {title && !isCollapsed && <SidebarGroupLabel>{title}</SidebarGroupLabel>}

      {/* Datasources section */}
      {(datasourceItem || newDatasourceItem) && (
        <>
          {datasourceItem && 'url' in datasourceItem && (
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip={datasourceItem.title}>
                  <Link to={datasourceItem.url}>
                    {datasourceItem.icon && <datasourceItem.icon />}
                    {!isCollapsed && <span>{datasourceItem.title}</span>}
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          )}
          {newDatasourceItem && 'action' in newDatasourceItem && (
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  tooltip={newDatasourceItem.title}
                  onClick={() => onModalOpen?.(true)}
                >
                  {newDatasourceItem.icon && <newDatasourceItem.icon />}
                  {!isCollapsed && <span>{newDatasourceItem.title}</span>}
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          )}
        </>
      )}

      {!isCollapsed && <SidebarSeparator className='my-2' />}

      {/* History section - scrollable history */}
      {historyItem && (
        <>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton className='h-8 pointer-events-none'>
                {historyItem.icon && <historyItem.icon />}
                {!isCollapsed && <span>History</span>}
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
          {!isCollapsed && (
            <>
              <div className='overflow-auto min-h-0 flex-1 max-h-[calc(100vh-300px)]'>
                <SidebarMenu>
                  {historyItem.items.map((subItem) => {
                    const isAction = 'action' in subItem && subItem.action === 'openModal'

                    return (
                      <SidebarMenuItem key={isAction ? `${subItem.title}-action` : subItem.url}>
                        {isAction ? (
                          <SidebarMenuButton onClick={() => onModalOpen?.(true)}>
                            {subItem.icon && <subItem.icon />}
                            <span>{subItem.title}</span>
                          </SidebarMenuButton>
                        ) : (
                          <div className="group/navitem flex items-center w-full">
                            <SidebarMenuButton
                              asChild
                              className="flex-1"
                            >
                              <Link to={subItem.url} search={subItem.search as any}>
                                {subItem.icon && <subItem.icon />}
                                <span className='truncate'>{subItem.title}</span>
                                {subItem.badge && <NavBadge>{subItem.badge}</NavBadge>}
                              </Link>
                            </SidebarMenuButton>
                            {subItem.onDelete && subItem.id && (
                              <button
                                onClick={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  setDeleteTarget({ id: subItem.id!, title: subItem.title })
                                }}
                                className="opacity-0 group-hover/navitem:opacity-100 transition-opacity duration-150 p-1 rounded-sm hover:bg-destructive/10 hover:text-destructive text-muted-foreground flex-shrink-0 mr-1"
                                title="Delete conversation"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </div>
                        )}
                      </SidebarMenuItem>
                    )
                  })}
                </SidebarMenu>
              </div>
              {deleteTarget && (
                <DeleteConfirmDialog
                  open={!!deleteTarget}
                  onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
                  onConfirm={() => {
                    const targetItem = historyItem?.items.find(
                      (s) => s.id === deleteTarget.id && s.onDelete
                    )
                    targetItem?.onDelete?.(deleteTarget.id)
                    setDeleteTarget(null)
                  }}
                  itemTitle={deleteTarget.title}
                />
              )}
            </>
          )}
        </>
      )}
    </SidebarGroup>
  )
}
