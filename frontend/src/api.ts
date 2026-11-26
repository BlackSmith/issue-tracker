import { reactive } from 'vue'
import type { User } from './types'
import { applyTheme } from './theme.ts'
import { setLanguage, t, validationMessage } from './i18n.ts'

export const auth = reactive({ user: null as User | null, csrf: '', ready: false })
let authRefresh: Promise<void> | undefined

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (options.method && options.method !== 'GET') headers.set('X-CSRF-Token', auth.csrf)
  const response = await fetch(`/api/v1${path}`, { ...options, headers, credentials: 'same-origin' })
  if (!response.ok) {
    let message = t('Request failed ({status})', { status: response.status })
    try {
      const result = await response.json()
      message = typeof result.detail === 'string' ? result.detail : result.detail?.map(validationMessage).join('; ') || message
    } catch { /* Keep the status message for non-JSON errors. */ }
    if (path !== '/auth/me' && !headers.has('Authorization')) await reconcileAuthFailure(response.status, message)
    throw new ApiError(response.status, message)
  }
  return response.status === 204 ? undefined as T : response.json()
}

export function refreshAuth(): Promise<void> {
  if (!authRefresh) {
    authRefresh = api<{ user: User | null; csrf_token: string }>('/auth/me').then(result => {
      auth.user = result.user
      applyTheme(result.user)
      if (result.user) setLanguage(result.user.language)
      auth.csrf = result.csrf_token
      auth.ready = true
    }).finally(() => { authRefresh = undefined })
  }
  return authRefresh
}

export async function reconcileAuthFailure(status: number, message: string) {
  if (status !== 401 && !(status === 403 && message === 'Invalid CSRF token')) return
  try { await refreshAuth() }
  catch {
    // A confirmed authentication failure must not leave a stale signed-in UI,
    // even if the follow-up session request cannot reach the server.
    if (status === 401) {
      auth.user = null
      auth.csrf = ''
      auth.ready = true
      applyTheme(null)
    }
  }
}

export async function signOut() {
  // Another tab or session expiry may have invalidated our user and CSRF token.
  await refreshAuth()
  if (!auth.user) return
  try { await api('/auth/logout', { method: 'POST' }) }
  catch (error) {
    await refreshAuth()
    if (auth.user) throw error
    return
  }
  await refreshAuth()
}
