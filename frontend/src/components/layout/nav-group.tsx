import { ReactNode, useState } from 'react'
import { Link, useLocation } from '@tanstack/react-router'
import { ChevronRight, Trash2 } from 'lucide-react'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu'
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
  NavCollapsible,
  NavItem,
  NavLink,
  NavAction,
  type NavGroup,
} from './types'

export function NavGroup({
  title,
  items,
  onModalOpen,
}: NavGroup & { onModalOpen?: (open: boolean) => void }) {
  const { state, isMobile } = useSidebar()
  const href = useLocation({ select: (location) => location.href })
  return (
    <SidebarGroup>
      {title && <SidebarGroupLabel>{title}</SidebarGroupLabel>}
      <SidebarMenu>
        {items.map((item) => {
          const key = `${item.title}-${item.url || item.action}`

          if (!item.items)
            return (
              <SidebarMenuLink
                key={key}
                item={item}
                href={href}
                onModalOpen={onModalOpen}
              />
            )

          if (state === 'collapsed' && !isMobile)
            return (
              <SidebarMenuCollapsedDropdown
                key={key}
                item={item}
                href={href}
                onModalOpen={onModalOpen}
              />
            )

          return (
            <SidebarMenuCollapsible
              key={key}
              item={item}
              href={href}
              onModalOpen={onModalOpen}
            />
          )
        })}
      </SidebarMenu>
    </SidebarGroup>
  )
}

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

const SidebarMenuLink = ({
  item,
  href,
  onModalOpen,
}: {
  item: NavLink | NavAction
  href: string
  onModalOpen?: (open: boolean) => void
}) => {
  const { setOpenMobile } = useSidebar()

  if ('action' in item && item.action === 'openModal') {
    return (
      <SidebarMenuItem>
        <SidebarMenuButton
          onClick={() => {
            onModalOpen?.(true)
            setOpenMobile(false)
          }}
          tooltip={item.title}
        >
          {item.icon && <item.icon />}
          <span>{item.title}</span>
          {item.badge && <NavBadge>{item.badge}</NavBadge>}
        </SidebarMenuButton>
      </SidebarMenuItem>
    )
  }

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={checkIsActive(href, item as NavLink)}
        tooltip={item.title}
      >
        <Link
          to={(item as NavLink).url}
          search={(item as NavLink).search as never}
          onClick={() => setOpenMobile(false)}
        >
          {item.icon && <item.icon />}
          <span>{item.title}</span>
          {item.badge && <NavBadge>{item.badge}</NavBadge>}
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

const SidebarMenuCollapsible = ({
  item,
  href,
  onModalOpen,
}: {
  item: NavCollapsible
  href: string
  onModalOpen?: (open: boolean) => void
}) => {
  const { setOpenMobile } = useSidebar()
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null)
  return (
    <>
      <Collapsible
        asChild
        // defaultOpen={checkIsActive(href, item, true)}
        defaultOpen={true}
        className='group/collapsible'
      >
        <SidebarMenuItem>
          <CollapsibleTrigger asChild>
            <SidebarMenuButton tooltip={item.title}>
              {item.icon && <item.icon />}
              <span>{item.title}</span>
              {item.badge && <NavBadge>{item.badge}</NavBadge>}
              <ChevronRight className='ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90' />
            </SidebarMenuButton>
          </CollapsibleTrigger>
          <CollapsibleContent className='CollapsibleContent'>
            <SidebarMenuSub>
              {item.items.map((subItem) => (
                <SidebarMenuSubItem key={subItem.title}>
                  {'action' in subItem && subItem.action === 'openModal' ? (
                    <SidebarMenuSubButton
                      onClick={() => {
                        onModalOpen?.(true)
                        setOpenMobile(false)
                      }}
                    >
                      {subItem.icon && <subItem.icon />}
                      <span>{subItem.title}</span>
                      {subItem.badge && <NavBadge>{subItem.badge}</NavBadge>}
                    </SidebarMenuSubButton>
                  ) : (
                    <div className="group/navitem flex items-center w-full">
                      <SidebarMenuSubButton
                        asChild
                        isActive={checkIsActive(href, subItem as any)}
                        className="flex-1 min-w-0"
                      >
                        <Link
                          to={(subItem as NavLink).url}
                          search={(subItem as NavLink).search as never}
                          onClick={() => setOpenMobile(false)}
                        >
                          {subItem.icon && <subItem.icon />}
                          <span className="truncate">{subItem.title}</span>
                          {subItem.badge && <NavBadge>{subItem.badge}</NavBadge>}
                        </Link>
                      </SidebarMenuSubButton>
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
                </SidebarMenuSubItem>
              ))}
            </SidebarMenuSub>
          </CollapsibleContent>
        </SidebarMenuItem>
      </Collapsible>
      {deleteTarget && (
        <DeleteConfirmDialog
          open={!!deleteTarget}
          onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
          onConfirm={() => {
            const targetItem = item.items.find(
              (sub) => sub.id === deleteTarget.id && sub.onDelete
            )
            targetItem?.onDelete?.(deleteTarget.id)
            setDeleteTarget(null)
          }}
          itemTitle={deleteTarget.title}
        />
      )}
    </>
  )
}

const SidebarMenuCollapsedDropdown = ({
  item,
  href,
  onModalOpen,
}: {
  item: NavCollapsible
  href: string
  onModalOpen?: (open: boolean) => void
}) => {
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null)
  return (
    <>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              tooltip={item.title}
              isActive={checkIsActive(href, item as any)}
            >
              {item.icon && <item.icon />}
              <span>{item.title}</span>
              {item.badge && <NavBadge>{item.badge}</NavBadge>}
              <ChevronRight className='ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90' />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side='right' align='start' sideOffset={4}>
            <DropdownMenuLabel>
              {item.title} {item.badge ? `(${item.badge})` : ''}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {item.items.map((sub) => (
              <DropdownMenuItem
                key={`${sub.title}-${(sub as any).url || (sub as any).action}`}
                asChild={!('action' in sub)}
                onClick={
                  'action' in sub && sub.action === 'openModal'
                    ? () => onModalOpen?.(true)
                    : undefined
                }
              >
                {'action' in sub && sub.action === 'openModal' ? (
                  <div className='cursor-pointer'>
                    {sub.icon && <sub.icon />}
                    <span className='max-w-52 text-wrap'>{sub.title}</span>
                    {sub.badge && (
                      <span className='ml-auto text-xs'>{sub.badge}</span>
                    )}
                  </div>
                ) : (
                  <div className="flex items-center w-full group/dropitem">
                    <Link
                      to={(sub as NavLink).url}
                      search={(sub as NavLink).search as never}
                      className={`flex-1 flex items-center gap-2 ${checkIsActive(href, sub as NavItem) ? 'bg-secondary' : ''}`}
                    >
                      {sub.icon && <sub.icon />}
                      <span className='max-w-44 text-wrap truncate'>{sub.title}</span>
                      {sub.badge && (
                        <span className='ml-auto text-xs'>{sub.badge}</span>
                      )}
                    </Link>
                    {sub.onDelete && sub.id && (
                      <button
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          setDeleteTarget({ id: sub.id!, title: sub.title })
                        }}
                        className="opacity-0 group-hover/dropitem:opacity-100 transition-opacity duration-150 p-1 rounded-sm hover:bg-destructive/10 hover:text-destructive text-muted-foreground flex-shrink-0 ml-1"
                        title="Delete conversation"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                )}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
      {deleteTarget && (
        <DeleteConfirmDialog
          open={!!deleteTarget}
          onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
          onConfirm={() => {
            const targetItem = item.items.find(
              (sub) => sub.id === deleteTarget.id && sub.onDelete
            )
            targetItem?.onDelete?.(deleteTarget.id)
            setDeleteTarget(null)
          }}
          itemTitle={deleteTarget.title}
        />
      )}
    </>
  )
}

function parseHref(href: string): { pathname: string; searchParams: URLSearchParams } {
  try {
    if (href.startsWith('http://') || href.startsWith('https://')) {
      const u = new URL(href)
      return { pathname: u.pathname, searchParams: u.searchParams }
    }
  } catch {
    /* fall through */
  }
  const q = href.indexOf('?')
  if (q === -1) {
    return { pathname: href, searchParams: new URLSearchParams() }
  }
  return {
    pathname: href.slice(0, q),
    searchParams: new URLSearchParams(href.slice(q + 1)),
  }
}

function checkIsActive(href: string, item: NavItem, mainNav = false): boolean {
  const { pathname, searchParams } = parseHref(href)

  const linkLike = item as NavLink & { items?: NavItem['items'] }
  const explicitSearch =
    'search' in linkLike ? linkLike.search : undefined

  if (linkLike.url != null && explicitSearch !== undefined) {
    const path = String(linkLike.url)
    if (pathname !== path) return false
    const keys = Object.keys(explicitSearch)
    if (keys.length === 0) {
      return [...searchParams.keys()].length === 0
    }
    for (const [k, v] of Object.entries(explicitSearch)) {
      if (v == null) continue
      if (searchParams.get(k) !== String(v)) return false
    }
    return true
  }

  if (linkLike.url) {
    const path = String(linkLike.url)
    if (
      pathname === path ||
      href === path ||
      href.split('?')[0] === path
    ) {
      return true
    }
  }

  if (item?.items?.length) {
    return item.items.some(
      (i) =>
        typeof i === 'object' &&
        i !== null &&
        'url' in i &&
        (!('action' in i) || (i as { action?: string }).action !== 'openModal') &&
        checkIsActive(href, i as NavItem)
    )
  }

  if (mainNav && linkLike.url) {
    const path = String(linkLike.url)
    const hp = pathname.split('/').filter(Boolean)[0]
    const ip = path.split('/').filter(Boolean)[0]
    return !!hp && !!ip && hp === ip
  }

  return false
}
