export type ReferenceKind = 'user' | 'ticket'
export interface ReferenceKey { kind: ReferenceKind; id: string }
const uuidPattern = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
const storedPattern = new RegExp(`^/(items|users)/(${uuidPattern})/?$`, 'i')
const legacyProjectPattern = new RegExp(`^/projects/(${uuidPattern})/?$`, 'i')

export function storedReference(href: string): ReferenceKey | null {
  const match = storedPattern.exec(href)
  return match ? { kind: match[1]!.toLowerCase() === 'users' ? 'user' : 'ticket', id: match[2]!.toLowerCase() } : null
}

export function referenceMarkdown(reference: ReferenceKey): string {
  return reference.kind === 'user' ? `[@user](/users/${reference.id})` : `[Ticket](/items/${reference.id})`
}

export type TicketTarget = { id: string; projectId?: string } | { slug: string; number: string }
export function internalTicketTarget(href: string, origin: string): TicketTarget | null {
  let url: URL
  try { url = new URL(href, origin) } catch { return null }
  if (url.origin !== origin || url.username || url.password) return null
  const stable = storedReference(url.pathname)
  if (stable?.kind === 'ticket') return { id: stable.id }
  const legacy = legacyProjectPattern.exec(url.pathname)
  const item = url.searchParams.get('item')
  if (legacy && item && new RegExp(`^${uuidPattern}$`, 'i').test(item)) return { id: item.toLowerCase(), projectId: legacy[1]!.toLowerCase() }
  const match = /^\/([a-z0-9]+(?:-[a-z0-9]+)*)\/([1-9][0-9]*)\/?$/i.exec(url.pathname)
  return match ? { slug: match[1]!, number: match[2]! } : null
}

export const referenceTokenizer = {
  name: 'reference',
  level: 'inline' as const,
  start: (source: string) => source.indexOf('['),
  tokenize(source: string) {
    const match = new RegExp(`^\\[(Ticket|@user)\\]\\(/(items|users)/(${uuidPattern})\\)`, 'i').exec(source)
    if (!match || (match[1]!.toLowerCase() === 'ticket') !== (match[2]!.toLowerCase() === 'items')) return undefined
    return { type: 'reference', raw: match[0], kind: match[2]!.toLowerCase() === 'items' ? 'ticket' : 'user', id: match[3]!.toLowerCase() }
  },
}

export function ticketShorthands(text: string) {
  const pattern = /(^|[\s(])#((?:[A-Za-z][A-Za-z0-9]{1,9}-)?[1-9][0-9]*)(?![\p{L}\p{N}_-])/gu
  return Array.from(text.matchAll(pattern), match => ({
    from: match.index! + match[1]!.length, to: match.index! + match[0].length, query: match[2]!,
  }))
}

export function referenceLinkText(href: string, label: string): { suffix: string } | null {
  const reference = storedReference(href)
  if (reference?.kind === 'ticket' && label === 'Ticket') return { suffix: '' }
  if (reference?.kind === 'user' && label === '@user') return { suffix: '' }
  // Older pasted links may contain text typed after the URL in their label.
  // Preserve that continuation outside the chip instead of replacing it.
  if (href && label.startsWith(href)) return { suffix: label.slice(href.length) }
  return null
}
