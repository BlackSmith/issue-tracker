import { ref, watch } from 'vue'
import cs from './locales/cs.json' with { type: 'json' }

export type Language = 'en' | 'cs'
export const languages: { value: Language; label: string }[] = [{ value: 'en', label: 'English' }, { value: 'cs', label: 'Čeština' }]
const storageKey = 'tracker.language'
function initialLanguage(): Language {
  try {
    const stored = localStorage.getItem(storageKey)
    if (stored === 'en' || stored === 'cs') return stored
  } catch { /* Storage may be unavailable. */ }
  if (typeof navigator !== 'undefined') {
    for (const locale of navigator.languages?.length ? navigator.languages : [navigator.language]) {
      const preferred = locale?.toLowerCase().split('-')[0]
      if (preferred === 'en' || preferred === 'cs') return preferred
    }
  }
  return 'en'
}
export const language = ref<Language>(initialLanguage())
export function setLanguage(value: string) { language.value = value === 'cs' ? 'cs' : 'en' }
watch(language, value => {
  if (typeof document !== 'undefined') document.documentElement.lang = value
  try { localStorage.setItem(storageKey, value) } catch { /* Language still works without storage. */ }
}, { immediate: true })

// English source messages are stable catalog keys and the fallback for new messages.
export function t(message: string, parameters: Record<string, string | number> = {}): string {
  const translated = language.value === 'cs' ? (cs as Record<string, string>)[message] || message : message
  return translated.replace(/\{(\w+)\}/g, (match, key: string) => String(parameters[key] ?? match))
}
export function dateTime(value: string | null): string {
  return value ? new Intl.DateTimeFormat(language.value === 'cs' ? 'cs-CZ' : 'en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : t('Never')
}
export function dateOnly(value: string): string {
  return new Intl.DateTimeFormat(language.value === 'cs' ? 'cs-CZ' : 'en-US', { dateStyle: 'medium' }).format(new Date(`${value}T12:00:00`))
}
export function itemCount(count: number): string {
  const category = new Intl.PluralRules(language.value).select(count)
  return t(category === 'one' ? '{count} work item' : category === 'few' ? '{count} work items (few)' : '{count} work items', { count })
}
export function translatedOptions(values: readonly string[]) { return values.map(value => ({ value, label: t(value) })) }

export function validationMessage(issue: { msg: string; type?: string; ctx?: { expected?: string } }): string {
  if (issue.type === 'enum' || issue.type === 'literal_error') {
    const options = [...(issue.ctx?.expected || '').matchAll(/'([^']+)'/g)].map(match => t(match[1]!))
    if (options.length) return t('Choose one of: {options}', { options: options.join(', ') })
  }
  if (issue.type === 'missing') return t('This field is required.')
  if (issue.type === 'value_error') return t(issue.msg.replace(/^Value error, /, ''))
  return language.value === 'cs' ? t('The value is invalid. Check the format and allowed length.') : issue.msg
}
