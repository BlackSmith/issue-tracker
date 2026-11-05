<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Marked } from 'marked'
import DOMPurify from 'dompurify'
import { api, auth } from './api'
import { internalTicketTarget, referenceLinkText, storedReference, ticketShorthands } from './referenceSyntax'
import { loadReference, resolveTicketUrl, type TicketReference } from './references'
import { referenceBadge } from './referenceRendering'
const props = withDefaults(defineProps<{ text: string; projectId?: string; interactive?: boolean; busy?: boolean }>(), { interactive: false, busy: false })
const emit = defineEmits<{ toggle: [index: number, checked: boolean] }>()
const root = ref<HTMLElement | null>(null)
const router = useRouter()
let renderVersion = 0
const html = computed(() => {
  let index = 0
  const marker = crypto.getRandomValues(new Uint32Array(4)).join('-')
  const parser = new Marked({ renderer: {
    checkbox({ checked }) {
      return `<input type="checkbox" data-task-marker="${marker}" data-checklist-index="${index++}" ${checked ? 'checked' : ''}> `
    },
  } })
  const template = document.createElement('template')
  template.innerHTML = DOMPurify.sanitize(parser.parse(props.text, { async: false }), { USE_PROFILES: { html: true } })
  template.content.querySelectorAll('input').forEach(input => {
    // Only parser-generated tasks are actionable, never raw HTML form controls.
    const task = input.dataset.taskMarker === marker
    input.disabled = !task || !props.interactive || props.busy
    if (task) {
      input.setAttribute('aria-label', `Checklist item ${Number(input.dataset.checklistIndex) + 1}`)
    } else {
      delete input.dataset.checklistIndex
    }
    delete input.dataset.taskMarker
  })
  // Work on text nodes only: code and external URL fragments must remain literal.
  const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_TEXT)
  const textNodes: Text[] = []
  while (walker.nextNode()) textNodes.push(walker.currentNode as Text)
  for (const node of textNodes) {
    if (node.parentElement?.closest('pre, code, a, textarea, style')) continue
    const matches = ticketShorthands(node.data)
    if (!matches.length) continue
    const fragment = document.createDocumentFragment()
    let end = 0
    for (const match of matches) {
      fragment.append(document.createTextNode(node.data.slice(end, match.from)))
      const link = document.createElement('a')
      link.dataset.ticketQuery = match.query
      link.textContent = `#${match.query}`
      fragment.append(link)
      end = match.to
    }
    fragment.append(document.createTextNode(node.data.slice(end)))
    node.replaceWith(fragment)
  }
  return template.innerHTML
})

async function enrichReferences() {
  const version = ++renderVersion
  const account = auth.user?.id
  await nextTick()
  if (!root.value || !account || version !== renderVersion) return
  const links = Array.from(root.value.querySelectorAll<HTMLAnchorElement>('a'))
  await Promise.all(links.map(async link => {
    if (link.closest('pre, code')) return
    const href = link.getAttribute('href') || ''
    const label = referenceLinkText(href, link.textContent || '')
    if (!label && !link.dataset.ticketQuery) return
    const reference = storedReference(href)
    let value
    let kind: 'user' | 'ticket' = 'ticket'
    if (reference) {
      kind = reference.kind
      value = await loadReference(reference)
    } else if (href && internalTicketTarget(href, window.location.origin)) {
      value = await resolveTicketUrl(href)
    } else if (link.dataset.ticketQuery) {
      const params = new URLSearchParams({ q: link.dataset.ticketQuery })
      if (props.projectId) params.set('project_id', props.projectId)
      try {
        const values = await api<TicketReference[]>(`/references/tickets?${params}`)
        value = values.length === 1 ? values[0] : null
      } catch { value = null }
    } else return
    if (version !== renderVersion || account !== auth.user?.id || !root.value?.contains(link)) return
    link.replaceWith(referenceBadge(value || null, kind), document.createTextNode(label?.suffix || ''))
  }))
}
onMounted(enrichReferences)
watch([html, () => props.projectId, () => auth.user?.id], enrichReferences, { flush: 'post' })
onBeforeUnmount(() => { renderVersion++ })

function navigate(event: MouseEvent) {
  if (event.defaultPrevented || event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
  const link = (event.target as HTMLElement).closest<HTMLAnchorElement>('a.reference-chip[href]')
  if (!link) return
  event.preventDefault()
  void router.push(link.getAttribute('href')!)
}

function changed(event: Event) {
  const input = event.target
  if (!(input instanceof HTMLInputElement) || !props.interactive || props.busy || input.dataset.checklistIndex === undefined) return
  emit('toggle', Number(input.dataset.checklistIndex), input.checked)
}
</script>
<template><div ref="root" class="markdown" :aria-busy="busy" @change="changed" @click="navigate" v-html="html"></div></template>

<style scoped>
.markdown :deep(li:has(> input[type="checkbox"])),
.markdown :deep(li:has(> p > input[type="checkbox"])) { list-style: none; }
.markdown :deep(input[type="checkbox"]:not(:disabled)) { cursor: pointer; }
.markdown :deep(input[type="checkbox"]:focus-visible) { outline: 2px solid var(--accent); outline-offset: 3px; }
</style>
