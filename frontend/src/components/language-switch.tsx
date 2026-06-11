import { Languages } from 'lucide-react'
import { useLocale, useTranslation } from '@/context/locale-context'
import { useSidebar } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function LanguageSwitch() {
  const { t, locale } = useTranslation()
  const { toggleLocale } = useLocale()
  const { state, isMobile } = useSidebar()
  const isCollapsed = state === 'collapsed' && !isMobile

  const label = locale === 'en' ? t('language.en') : t('language.vi')
  const shortLabel = locale === 'en' ? 'EN' : 'VI'

  return (
    <Button
      variant='outline'
      size={isCollapsed ? 'icon' : 'sm'}
      className={cn(
        'shrink-0',
        !isCollapsed && 'gap-1.5 px-2.5',
        isCollapsed && 'text-[10px] font-semibold'
      )}
      onClick={toggleLocale}
      title={`${t('language.switch')} — ${label}`}
      aria-label={t('language.switch')}
    >
      {isCollapsed ? (
        shortLabel
      ) : (
        <>
          <Languages className='h-4 w-4 shrink-0' />
          <span className='text-xs'>{label}</span>
        </>
      )}
    </Button>
  )
}
