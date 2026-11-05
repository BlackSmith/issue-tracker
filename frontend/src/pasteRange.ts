import type { Mapping } from '@tiptap/pm/transform'

export function mapPastedRange(range: { from: number; to: number }, mapping: Mapping) {
  // Typing at either edge is outside the pasted URL, not part of its lookup.
  return { from: mapping.map(range.from, 1), to: mapping.map(range.to, -1) }
}
