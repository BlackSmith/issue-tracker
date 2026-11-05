import type { User } from './types'

export const accentOptions = [
  { id: 'green', name: 'Green', color: '#26734d' },
  { id: 'blue', name: 'Blue', color: '#2f66a3' },
  { id: 'purple', name: 'Purple', color: '#6750bd' },
  { id: 'teal', name: 'Teal', color: '#24777c' },
  { id: 'amber', name: 'Amber', color: '#916419' },
  { id: 'rose', name: 'Rose', color: '#aa425e' },
]
export const backgroundOptions = [
  { id: 'white', name: 'White', color: '#ffffff' },
  { id: 'mist', name: 'Mist', color: '#f3f5f4' },
  { id: 'mint', name: 'Mint', color: '#eaf4ed' },
  { id: 'sand', name: 'Sand', color: '#f8f2e7' },
  { id: 'slate', name: 'Slate', color: '#edf1f7' },
]
export const defaultAppearance = { theme_accent: 'green', theme_background: 'white' }

export function applyTheme(preferences?: Pick<User, 'theme_accent' | 'theme_background'> | null) {
  const accent = accentOptions.find(option => option.id === preferences?.theme_accent) || accentOptions[0]!
  const background = backgroundOptions.find(option => option.id === preferences?.theme_background) || backgroundOptions[0]!
  const root = document.documentElement
  root.style.setProperty('--accent', accent.color)
  root.style.setProperty('--app-background', background.color)
  root.dataset.accent = accent.id
  root.dataset.background = background.id
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', accent.color)
}
