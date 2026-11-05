import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import { TableKit } from '@tiptap/extension-table'
import TaskItem from '@tiptap/extension-task-item'
import TaskList from '@tiptap/extension-task-list'
import { Markdown } from '@tiptap/markdown'
import { Marked, marked } from 'marked'
import type { NodeViewRenderer } from '@tiptap/core'
import { ReferenceNode } from './referenceNode.ts'

export function createEditorExtensions(referenceNodeView?: NodeViewRenderer) {
  return [
    StarterKit.configure({ underline: false, link: { openOnClick: false } }),
    Image.configure({ inline: true }),
    TaskList,
    TaskItem.configure({ nested: true }),
    TableKit.configure({ table: { renderWrapper: true } }),
    ReferenceNode.configure({ nodeView: referenceNodeView }),
    Markdown.configure({
      // Tiptap registers custom tokens. Each editor needs its own parser so those
      // tokens cannot leak into read-only rendering or other mounted editors.
      marked: new Marked() as unknown as typeof marked,
      markedOptions: { gfm: true },
    }),
  ]
}
