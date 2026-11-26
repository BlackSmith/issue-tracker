import { onUnmounted, ref, watch, type Ref } from 'vue'
import { auth, refreshAuth } from './api'

// A workspace owns one connection; mounted ticket details observe its invalidations.
export const ticketRevision = ref(0)

export function useLiveTickets(projectId: Ref<string>) {
  let socket: WebSocket | undefined
  let retry: ReturnType<typeof setTimeout> | undefined
  let refresh: ReturnType<typeof setTimeout> | undefined
  let generation = 0, attempts = 0
  function invalidate() {
    if (refresh) return
    refresh = setTimeout(() => { refresh = undefined; ticketRevision.value++ }, 150)
  }
  function stop() {
    generation++
    clearTimeout(retry); clearTimeout(refresh)
    refresh = undefined
    socket?.close(); socket = undefined
  }
  function connect(current: number) {
    if (current !== generation || !auth.user?.role || !projectId.value) return
    const url = new URL('/api/v1/tickets/live', window.location.href)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    url.searchParams.set('project', projectId.value)
    const connection = new WebSocket(url)
    socket = connection
    connection.onopen = () => { attempts = 0 }
    connection.onmessage = event => {
      if (current !== generation) return
      try { if (JSON.parse(event.data).type === 'refresh') invalidate() }
      catch { /* Ignore malformed or unsupported events. */ }
    }
    connection.onclose = async () => {
      if (current !== generation) return
      try { await refreshAuth() } catch { /* Retry after temporary network failures. */ }
      if (current !== generation) return
      retry = setTimeout(() => connect(current), Math.min(30000, 1000 * 2 ** attempts++) + Math.random() * 500)
    }
  }
  const unwatch = watch(() => [projectId.value, auth.user?.id, auth.user?.role], () => {
    stop(); attempts = 0; connect(generation)
  }, { immediate: true })
  function visible() {
    if (document.visibilityState !== 'visible') return
    if (socket?.readyState === WebSocket.OPEN) invalidate()
    else { stop(); connect(generation) }
  }
  document.addEventListener('visibilitychange', visible)
  onUnmounted(() => { unwatch(); stop(); document.removeEventListener('visibilitychange', visible) })
}
