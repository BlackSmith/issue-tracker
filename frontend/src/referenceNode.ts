import { Node, mergeAttributes, type NodeViewRenderer } from '@tiptap/core'
import { referenceMarkdown, referenceTokenizer } from './referenceSyntax.ts'

export const ReferenceNode = Node.create<{ nodeView?: NodeViewRenderer }>({
  name: 'reference',
  inline: true,
  group: 'inline',
  atom: true,
  marks: '',
  addOptions() { return { nodeView: undefined } },
  addAttributes() { return { kind: { default: 'ticket' }, id: { default: '' } } },
  parseHTML() {
    return [{ tag: 'span[data-reference-kind][data-reference-id]', getAttrs: element => ({
      kind: element.getAttribute('data-reference-kind'), id: element.getAttribute('data-reference-id'),
    }) }]
  },
  renderHTML({ node, HTMLAttributes }) {
    return ['span', mergeAttributes(HTMLAttributes, { 'data-reference-kind': node.attrs.kind, 'data-reference-id': node.attrs.id }),
      node.attrs.kind === 'user' ? '@user' : 'Ticket']
  },
  renderText({ node }) { return node.attrs.kind === 'user' ? '@user' : '#ticket' },
  markdownTokenizer: referenceTokenizer,
  parseMarkdown(token) {
    return { type: 'reference', attrs: { kind: token.kind, id: token.id } }
  },
  renderMarkdown(node) { return referenceMarkdown({ kind: node.attrs!.kind, id: node.attrs!.id }) },
  addNodeView() { return this.options.nodeView || null },
})
