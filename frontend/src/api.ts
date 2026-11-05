import { reactive } from 'vue'
import type { User } from './types'
import { applyTheme } from './theme'

export const auth = reactive({ user: null as User | null, csrf: '', ready: false })

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (options.method && options.method !== 'GET') headers.set('X-CSRF-Token', auth.csrf)
  const response = await fetch(`/api/v1${path}`, { ...options, headers, credentials: 'same-origin' })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const result = await response.json()
      message = typeof result.detail === 'string' ? result.detail : result.detail?.map((e: { msg: string }) => e.msg).join('; ') || message
    } catch { /* Keep the status message for non-JSON errors. */ }
    throw new Error(message)
  }
  return response.json()
}

export async function refreshAuth() {
  const result = await api<{ user: User | null; csrf_token: string }>('/auth/me')
  auth.user = result.user
  applyTheme(result.user)
  auth.csrf = result.csrf_token
  auth.ready = true
}
