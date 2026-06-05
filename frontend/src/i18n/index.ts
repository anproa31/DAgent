import { translations, type Locale, type TranslationKey } from './translations'

export type { Locale, TranslationKey }

export function translate(
  locale: Locale,
  key: TranslationKey,
  params?: Record<string, string | number>
): string {
  let text: string = translations[locale][key] ?? translations.en[key]
  if (!params) return text
  for (const [k, v] of Object.entries(params)) {
    text = text.replace(new RegExp(`\\{\\{${k}\\}\\}`, 'g'), String(v))
  }
  return text
}
