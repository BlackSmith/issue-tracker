import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import type { EditorView } from '@tiptap/pm/view'
import type { ReferenceKind } from './referenceSyntax'

export interface SuggestionQuery {
  kind: ReferenceKind; query: string; from: number; to: number
}
interface SuggestionOptions {
  query: (value: SuggestionQuery, view: EditorView) => void
  hide: () => void
  keydown: (event: KeyboardEvent) => boolean
}

export const ReferenceSuggestions = Extension.create<SuggestionOptions>({
  name: 'referenceSuggestions',
  addOptions() { return { query: () => {}, hide: () => {}, keydown: () => false } },
  addProseMirrorPlugins() {
    const options = this.options
    return [new Plugin({
      key: new PluginKey('referenceSuggestions'),
      props: { handleKeyDown: (_view, event) => options.keydown(event) },
      view() {
        let previous = ''
        return {
          update(view) {
            const selection = view.state.selection
            const parent = selection.$from.parent
            const code = parent.type.spec.code || selection.$from.marks().some(mark => mark.type.name === 'code' || mark.type.name === 'link')
            const before = parent.textBetween(0, selection.$from.parentOffset, undefined, '\ufffc')
            const match = /(?:^|[\s(])([@#])([\p{L}\p{N}_.-]{0,80})$/u.exec(before)
            if (!view.editable || !selection.empty || code || !match) {
              if (previous) options.hide()
              previous = ''
              return
            }
            const kind = match[1] === '@' ? 'user' : 'ticket'
            const query = match[2]!
            const from = selection.from - query.length - 1
            const key = `${kind}:${from}:${selection.to}:${query}`
            if (key === previous) return
            previous = key
            options.query({ kind, query, from, to: selection.to }, view)
          },
          destroy() { options.hide() },
        }
      },
    })]
  },
})
