import { ReactNode, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { ChevronRight, Pin, PinOff, Trash2 } from 'lucide-react'
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
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
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '../ui/collapsible'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu'
import { cn } from '@/lib/utils'
import { NavGroup as NavGroupType, NavCollapsible, NavLink } from './types'

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

type CollapsibleSubItem = NavCollapsible['items'][number] & {
  url?: string
  search?: Record<string, unknown>
  params?: Record<string, string>
}

function IconModeNavSection({
  title,
  icon: Icon,
  items,
}: {
  title: string
  icon?: React.ElementType
  items: CollapsibleSubItem[]
}) {
  const actionableItems = items.filter((item) => !item.placeholder && item.id)

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu modal={false}>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton tooltip={title}>
              {Icon && <Icon />}
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            side='right'
            align='start'
            className='w-56 max-h-80 overflow-y-auto'
          >
            {actionableItems.length === 0 ? (
              <DropdownMenuItem disabled>
                {items.find((item) => item.placeholder)?.title ?? `No ${title.toLowerCase()}`}
              </DropdownMenuItem>
            ) : (
              actionableItems.map((subItem) => {
                const ItemIcon = subItem.icon
                return (
                  <DropdownMenuItem key={subItem.id} asChild>
                    <Link
                      to={subItem.url}
                      search={'search' in subItem ? (subItem.search as any) : undefined}
                      className='flex items-center gap-2 truncate'
                    >
                      {ItemIcon && (
                        <span className='flex h-4 w-4 shrink-0 items-center justify-center'>
                          <ItemIcon />
                        </span>
                      )}
                      <span className='truncate'>{subItem.title}</span>
                    </Link>
                  </DropdownMenuItem>
                )
              })
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

function CollapsibleNavSection({
  title,
  icon: Icon,
  items,
  defaultOpen = true,
  scrollable = false,
  onDeleteRequest,
  onOpenModal,
  isIconMode = false,
}: {
  title: string
  icon?: React.ElementType
  items: CollapsibleSubItem[]
  defaultOpen?: boolean
  scrollable?: boolean
  onDeleteRequest: (target: { id: string; title: string }) => void
  onOpenModal?: () => void
  isIconMode?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)

  if (isIconMode) {
    return <IconModeNavSection title={title} icon={Icon} items={items} />
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen} className='group/collapsible'>
      <SidebarMenu>
        <SidebarMenuItem>
          <CollapsibleTrigger asChild>
            <SidebarMenuButton className='h-8 w-full justify-between px-2'>
              <span className='flex min-w-0 items-center gap-2'>
                {Icon && <Icon className='h-4 w-4 shrink-0' />}
                <span className='text-sm font-medium truncate'>{title}</span>
              </span>
              <ChevronRight
                className={cn(
                  'h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200',
                  open && 'rotate-90'
                )}
              />
            </SidebarMenuButton>
          </CollapsibleTrigger>
          <CollapsibleContent className='CollapsibleContent'>
            <div
              className={cn(
                scrollable && 'max-h-[calc(100vh-300px)] min-h-0 flex-1 overflow-auto'
              )}
            >
              <SidebarMenuSub>
                {items.map((subItem) => {
                  if ('action' in subItem && subItem.action === 'openModal') {
                    const ActionIcon = subItem.icon
                    return (
                      <SidebarMenuSubItem key={subItem.title}>
                        <SidebarMenuSubButton
                          onClick={onOpenModal}
                          className='text-muted-foreground'
                        >
                          {ActionIcon && <ActionIcon />}
                          <span className='truncate'>{subItem.title}</span>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    )
                  }

                  if (!('url' in subItem) || !subItem.url) return null
                  const isPlaceholder = !!subItem.placeholder

                  return (
                    <SidebarMenuSubItem
                      key={subItem.url + subItem.title}
                      className='group/navitem'
                    >
                      <div className='relative w-full'>
                        <SidebarMenuSubButton
                          asChild={!isPlaceholder}
                          className={cn(
                            'min-w-0 w-full',
                            !isPlaceholder &&
                              subItem.id &&
                              'group-hover/navitem:pr-[3.25rem]'
                          )}
                          aria-disabled={isPlaceholder}
                        >
                          {isPlaceholder ? (
                            <span className='text-muted-foreground truncate'>
                              {subItem.title}
                            </span>
                          ) : (
                            <Link
                              to={subItem.url}
                              params={
                                'params' in subItem ? (subItem.params as any) : undefined
                              }
                              search={
                                'search' in subItem ? (subItem.search as any) : undefined
                              }
                            >
                              {subItem.icon && <subItem.icon />}
                              <span className='truncate'>{subItem.title}</span>
                              {subItem.badge && <NavBadge>{subItem.badge}</NavBadge>}
                            </Link>
                          )}
                        </SidebarMenuSubButton>
                        {!isPlaceholder && subItem.id && (
                          <div className='pointer-events-none absolute top-1/2 right-1 flex -translate-y-1/2 items-center gap-0 opacity-0 transition-opacity duration-150 group-hover/navitem:pointer-events-auto group-hover/navitem:opacity-100'>
                            {subItem.onPinToggle && (
                              <button
                                type='button'
                                onClick={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  subItem.onPinToggle!(subItem.id!)
                                }}
                                className='rounded-sm p-1 text-muted-foreground hover:bg-sidebar-accent'
                                title={
                                  subItem.isPinned
                                    ? 'Unpin conversation'
                                    : 'Pin conversation'
                                }
                              >
                                {subItem.isPinned ? (
                                  <PinOff className='h-3.5 w-3.5' />
                                ) : (
                                  <Pin className='h-3.5 w-3.5' />
                                )}
                              </button>
                            )}
                            {subItem.onDelete && (
                              <button
                                type='button'
                                onClick={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  onDeleteRequest({
                                    id: subItem.id!,
                                    title: subItem.title,
                                  })
                                }}
                                className='rounded-sm p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive'
                                title='Delete conversation'
                              >
                                <Trash2 className='h-3.5 w-3.5' />
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </SidebarMenuSubItem>
                  )
                })}
              </SidebarMenuSub>
            </div>
          </CollapsibleContent>
        </SidebarMenuItem>
      </SidebarMenu>
    </Collapsible>
  )
}

export function NavGroup({
  title,
  items,
}: NavGroupType) {
  const { state, isMobile } = useSidebar()

  const linkItems = items.filter(
    (item): item is NavLink => 'url' in item && !!item.url
  )
  const pinnedItem = items.find(
    (item): item is NavCollapsible => item.title === 'Pinned' && 'items' in item
  )
  const historyItem = items.find(
    (item): item is NavCollapsible => item.title === 'History' && 'items' in item
  )

  const isCollapsed = state === 'collapsed' && !isMobile
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null)
  const handleDeleteConfirm = () => {
    if (!deleteTarget) return
    const sections = [pinnedItem, historyItem]
    for (const section of sections) {
      const targetItem = section?.items?.find(
        (s) => s.id === deleteTarget.id && s.onDelete
      )
      if (targetItem?.onDelete) {
        targetItem.onDelete(deleteTarget.id)
        break
      }
    }
    setDeleteTarget(null)
  }

  return (
    <SidebarGroup className='min-h-0 flex flex-col gap-0'>
      {title && !isCollapsed && <SidebarGroupLabel>{title}</SidebarGroupLabel>}

      {linkItems.map((item) => (
        <SidebarMenu key={item.title}>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip={item.title}>
              <Link to={item.url}>
                {item.icon && <item.icon />}
                {!isCollapsed && <span>{item.title}</span>}
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      ))}

      {pinnedItem && (
        <div className={cn(isCollapsed ? 'mt-2' : 'mt-5')}>
          <CollapsibleNavSection
            title={pinnedItem.title}
            icon={pinnedItem.icon}
            items={(pinnedItem.items ?? []) as CollapsibleSubItem[]}
            defaultOpen
            isIconMode={isCollapsed}
            onDeleteRequest={setDeleteTarget}
          />
        </div>
      )}

      {historyItem && (
        <div className={cn(isCollapsed ? 'mt-2' : 'mt-5')}>
          <CollapsibleNavSection
            title={historyItem.title}
            icon={historyItem.icon}
            items={(historyItem.items ?? []) as CollapsibleSubItem[]}
            defaultOpen
            scrollable
            isIconMode={isCollapsed}
            onDeleteRequest={setDeleteTarget}
          />
        </div>
      )}

      {deleteTarget && (
        <DeleteConfirmDialog
          open={!!deleteTarget}
          onOpenChange={(open) => {
            if (!open) setDeleteTarget(null)
          }}
          onConfirm={handleDeleteConfirm}
          itemTitle={deleteTarget.title}
        />
      )}
    </SidebarGroup>
  )
}
