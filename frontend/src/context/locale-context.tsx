import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { translate, type Locale, type TranslationKey } from '@/i18n'

type LocaleProviderProps = {
  children: ReactNode
  defaultLocale?: Locale
  storageKey?: string
}

type LocaleProviderState = {
  locale: Locale
  setLocale: (locale: Locale) => void
  toggleLocale: () => void
}

const initialState: LocaleProviderState = {
  locale: 'en',
  setLocale: () => null,
  toggleLocale: () => null,
}

const LocaleProviderContext = createContext<LocaleProviderState>(initialState)

export function LocaleProvider({
  children,
  defaultLocale = 'en',
  storageKey = 'vite-ui-locale',
}: LocaleProviderProps) {
  const [locale, _setLocale] = useState<Locale>(() => {
    const saved = localStorage.getItem(storageKey)
    return saved === 'vi' || saved === 'en' ? saved : defaultLocale
  })

  useEffect(() => {
    const root = document.documentElement
    root.lang = locale
    root.classList.remove('locale-en', 'locale-vi')
    root.classList.add(`locale-${locale}`)
  }, [locale])

  const setLocale = useCallback(
    (next: Locale) => {
      localStorage.setItem(storageKey, next)
      _setLocale(next)
    },
    [storageKey]
  )

  const toggleLocale = useCallback(() => {
    setLocale(locale === 'en' ? 'vi' : 'en')
  }, [locale, setLocale])

  const value = useMemo(
    () => ({ locale, setLocale, toggleLocale }),
    [locale, setLocale, toggleLocale]
  )

  return (
    <LocaleProviderContext.Provider value={value}>
      {children}
    </LocaleProviderContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useLocale = () => {
  const context = useContext(LocaleProviderContext)
  if (context === undefined) {
    throw new Error('useLocale must be used within a LocaleProvider')
  }
  return context
}

// eslint-disable-next-line react-refresh/only-export-components
export const useTranslation = () => {
  const { locale } = useLocale()
  const t = useCallback(
    (key: TranslationKey, params?: Record<string, string | number>) =>
      translate(locale, key, params),
    [locale]
  )
  return { t, locale }
}
