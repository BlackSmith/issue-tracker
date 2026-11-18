import type { NodeViewRenderer } from '@tiptap/core'
import { loadReference, type Reference } from './references'
import type { ReferenceKey } from './referenceSyntax'
import { watch } from 'vue'
import { language, t } from './i18n'

export function referenceBadge(value: Reference | null, kind: ReferenceKey['kind']): HTMLElement {
  if (!value) {
    const span = document.createElement('span')
    span.className = 'reference-chip reference-unavailable'
    span.textContent = t(kind === 'user' ? 'User unavailable' : 'Ticket unavailable')
    return span
  }
  const link = document.createElement('a')
  link.href = value.href
  link.className = `reference-chip reference-${value.kind}`
  if (value.kind === 'user') {
    link.textContent = `@${value.name}`
    link.title = value.name
  } else {
    link.title = `${value.reference}: ${value.title} (${t(value.status)})`
    const reference = document.createElement('span')
    reference.className = 'reference-number'
    reference.textContent = `#${value.reference}`
    const title = document.createElement('span')
    title.className = 'reference-title'
    title.textContent = value.title
    const status = document.createElement('span')
    status.className = 'reference-status'
    status.dataset.status = value.status
    status.textContent = t(value.status)
    link.append(reference, title, status)
  }
  return link
}

export const referenceNodeView: NodeViewRenderer = ({ node }) => {
  const dom = document.createElement('span')
  dom.className = 'reference-node'
  dom.contentEditable = 'false'
  dom.textContent = node.attrs.kind === 'user' ? '@user…' : t('Loading ticket…')
  let destroyed = false
  let resolved: Reference | null | undefined
  function render(value: Reference | null) {
    const badge = referenceBadge(value, node.attrs.kind)
    if (badge instanceof HTMLAnchorElement) { badge.target = '_blank'; badge.rel = 'noopener' }
    dom.replaceChildren(badge)
  }
  const stop = watch(language, () => { if (resolved !== undefined) render(resolved) })
  void loadReference({ kind: node.attrs.kind, id: node.attrs.id }).then(value => {
    if (destroyed) return
    resolved = value
    render(value)
  })
  return {
    dom,
    ignoreMutation: () => true,
    stopEvent: event => event.type === 'click',
    selectNode: () => dom.classList.add('ProseMirror-selectednode'),
    deselectNode: () => dom.classList.remove('ProseMirror-selectednode'),
    destroy: () => { destroyed = true; stop() },
  }
}
