import { api, auth } from './api'
import type { WorkItem } from './types'
import { internalTicketTarget, storedReference, type ReferenceKey } from './referenceSyntax'

export interface UserReference extends ReferenceKey {
  kind: 'user'; name: string; role: string; is_bot: boolean; avatar_url: string | null; href: string
}
export interface TicketReference extends ReferenceKey {
  kind: 'ticket'; title: string; status: string; reference: string; href: string; project_id: string; number: number
}
export type Reference = UserReference | TicketReference

// Batch simultaneous lookups from multiple comments and editor nodes. Keep only
// in-flight results, scoped to the current account; labels are never permanent
// client cache entries that could outlive permission or status changes.
const pending = new Map<string, Promise<Reference | null>>()
let queue: { key: ReferenceKey; account: string; resolve: (value: Reference | null) => void }[] = []
let scheduled = false

export function loadReference(key: ReferenceKey): Promise<Reference | null> {
  if (key.kind !== 'ticket' && key.kind !== 'user') return Promise.resolve(null)
  const validated = storedReference(`/${key.kind === 'user' ? 'users' : 'items'}/${key.id}`)
  if (!validated) return Promise.resolve(null)
  key = validated
  const account = auth.user?.id
  if (!account) return Promise.resolve(null)
  const cacheKey = `${account}:${key.kind}:${key.id}`
  const existing = pending.get(cacheKey)
  if (existing) return existing
  const request = new Promise<Reference | null>(resolve => {
    queue.push({ key, account, resolve })
    if (!scheduled) { scheduled = true; queueMicrotask(flushReferences) }
  })
  pending.set(cacheKey, request)
  void request.finally(() => pending.delete(cacheKey))
  return request
}

async function flushReferences() {
  scheduled = false
  const batch = queue
  queue = []
  for (let start = 0; start < batch.length; start += 50) {
    const chunk = batch.slice(start, start + 50)
    try {
      const result = await api<{ tickets: TicketReference[]; users: UserReference[] }>('/references/resolve', {
        method: 'POST', body: JSON.stringify({
          tickets: chunk.filter(row => row.key.kind === 'ticket').map(row => row.key.id),
          users: chunk.filter(row => row.key.kind === 'user').map(row => row.key.id),
        }),
      })
      const values: Reference[] = [...result.tickets, ...result.users]
      for (const row of chunk) row.resolve(auth.user?.id === row.account
        ? values.find(value => value.kind === row.key.kind && value.id === row.key.id) || null : null)
    } catch { for (const row of chunk) row.resolve(null) }
  }
}

export async function resolveTicketUrl(href: string, signal?: AbortSignal): Promise<TicketReference | null> {
  const target = internalTicketTarget(href, window.location.origin)
  if (!target) return null
  const path = 'id' in target ? `/items/${target.id}`
    : `/projects/by-slug/${target.slug}/items/${target.number}`
  const account = auth.user?.id
  try {
    const item = await api<WorkItem>(path, { signal })
    if (auth.user?.id !== account || ('projectId' in target && target.projectId !== item.project_id)) return null
    return { kind: 'ticket', id: item.id, title: item.title, status: item.status,
      reference: item.reference, href: item.web_url, project_id: item.project_id, number: item.number }
  } catch { return null }
}
