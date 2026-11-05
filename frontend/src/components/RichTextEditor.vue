<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, useId, watch } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import type { Level } from '@tiptap/extension-heading'
import type { Transaction } from '@tiptap/pm/state'
import type { EditorView } from '@tiptap/pm/view'
import { uploadAttachment } from '../attachments'
import { createEditorExtensions } from '../editorExtensions'
import { api } from '../api'
import { ReferenceSuggestions, type SuggestionQuery } from '../referenceSuggestions'
import { internalTicketTarget } from '../referenceSyntax'
import { resolveTicketUrl, type Reference } from '../references'
import { referenceNodeView } from '../referenceRendering'
import { mapPastedRange } from '../pasteRange'

const props = withDefaults(defineProps<{
  modelValue: string
  label: string
  placeholder?: string
  itemId?: string
  projectId?: string
  disabled?: boolean
}>(), { placeholder: 'Start writing…', disabled: false })
const emit = defineEmits<{
  'update:modelValue': [value: string]
  uploading: [value: boolean]
  uploaded: []
}>()

const error = ref('')
const progress = ref<number | null>(null)
const uploading = computed(() => progress.value !== null)
const fileInput = ref<HTMLInputElement | null>(null)
const linkOpen = ref(false)
const linkUrl = ref('')
const linkError = ref('')
let uploadController: AbortController | undefined
const pasteControllers = new Set<AbortController>()
const suggestionId = useId()
const suggestions = reactive({ visible: false, loading: false, kind: 'user' as 'user' | 'ticket',
  items: [] as Reference[], selected: 0, from: 0, to: 0, top: 0, left: 0, width: 360 })
let suggestionController: AbortController | undefined
let suggestionTimer: ReturnType<typeof setTimeout> | undefined
let suggestionRequest = 0

function hideSuggestions() {
  suggestions.visible = false
  suggestionRequest++
  suggestionController?.abort()
  clearTimeout(suggestionTimer)
}
function positionSuggestions(view: EditorView) {
  const coords = view.coordsAtPos(suggestions.to)
  suggestions.width = Math.min(420, window.innerWidth - 24)
  suggestions.left = Math.max(12, Math.min(coords.left, window.innerWidth - suggestions.width - 12))
  const height = Math.min(300, Math.max(65, suggestions.items.length * 57 + 35))
  suggestions.top = coords.bottom + height + 8 > window.innerHeight
    ? Math.max(8, coords.top - height - 8) : coords.bottom + 8
}
function querySuggestions(query: SuggestionQuery, view: EditorView) {
  hideSuggestions()
  const request = ++suggestionRequest
  Object.assign(suggestions, { ...query, visible: true, loading: true, items: [], selected: 0 })
  positionSuggestions(view)
  suggestionTimer = setTimeout(async () => {
    const controller = new AbortController()
    suggestionController = controller
    const params = new URLSearchParams({ q: query.query })
    if (props.projectId) params.set('project_id', props.projectId)
    try {
      const values = await api<Reference[]>(`/references/${query.kind === 'user' ? 'users' : 'tickets'}?${params}`, { signal: controller.signal })
      if (request !== suggestionRequest) return
      suggestions.items = values
    } catch {
      if (request === suggestionRequest) suggestions.items = []
    } finally {
      if (request === suggestionRequest) {
        suggestions.loading = false
        if (!view.isDestroyed) positionSuggestions(view)
      }
    }
  }, 120)
}
function selectReference(value: Reference) {
  if (!editor.value || props.disabled) return
  const range = { from: suggestions.from, to: suggestions.to }
  hideSuggestions()
  editor.value.chain().focus().insertContentAt(range, [
    { type: 'reference', attrs: { kind: value.kind, id: value.id } }, { type: 'text', text: ' ' },
  ]).run()
}
function suggestionKeydown(event: KeyboardEvent) {
  if (!suggestions.visible) return false
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    hideSuggestions()
    return true
  }
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    const length = suggestions.items.length
    if (length) suggestions.selected = (suggestions.selected + (event.key === 'ArrowDown' ? 1 : -1) + length) % length
    return true
  }
  if (event.key === 'Enter' || event.key === 'Tab') {
    const selected = suggestions.items[suggestions.selected]
    if (selected) { selectReference(selected); return true }
    if (suggestions.loading) return true
    hideSuggestions()
  }
  return false
}

const editor = useEditor({
  extensions: [...createEditorExtensions(referenceNodeView), ReferenceSuggestions.configure({
    query: querySuggestions, hide: hideSuggestions, keydown: suggestionKeydown,
  })],
  content: props.modelValue,
  contentType: 'markdown',
  editable: !props.disabled,
  editorProps: {
    attributes: {
      role: 'textbox',
      'aria-label': props.label,
      'aria-multiline': 'true',
      'data-placeholder': props.placeholder,
      'aria-autocomplete': 'list',
      'aria-controls': suggestionId,
    },
    handlePaste(_view, event) {
      const files = Array.from(event.clipboardData?.files || [])
      if (files.length) {
        event.preventDefault()
        void attach(files)
        return true
      }
      const text = event.clipboardData?.getData('text/plain').trim() || ''
      if (!text || !internalTicketTarget(text, window.location.origin)) return false
      event.preventDefault()
      void pasteTicket(text)
      return true
    },
    handleDrop(view, event, _slice, moved) {
      const files = Array.from(event.dataTransfer?.files || [])
      if (moved || !files.length) return false
      event.preventDefault()
      const position = view.posAtCoords({ left: event.clientX, top: event.clientY })
      if (position) editor.value?.commands.setTextSelection(position.pos)
      void attach(files)
      return true
    },
  },
  onUpdate({ editor }) {
    emit('update:modelValue', editor.isEmpty ? '' : editor.getMarkdown())
  },
  onBlur() { hideSuggestions() },
})

watch(() => props.modelValue, value => {
  const current = editor.value
  if (current && value !== (current.isEmpty ? '' : current.getMarkdown())) {
    current.commands.setContent(value, { contentType: 'markdown', emitUpdate: false })
  }
})
watch(() => props.disabled, disabled => { editor.value?.setEditable(!disabled); if (disabled) hideSuggestions() })
watch(() => [suggestions.visible, suggestions.selected, suggestions.items.length], async () => {
  const dom = editor.value?.view.dom
  dom?.setAttribute('aria-expanded', String(suggestions.visible))
  if (suggestions.visible && suggestions.items[suggestions.selected]) {
    dom?.setAttribute('aria-activedescendant', `${suggestionId}-${suggestions.selected}`)
    await nextTick()
    document.getElementById(`${suggestionId}-${suggestions.selected}`)?.scrollIntoView({ block: 'nearest' })
  } else dom?.removeAttribute('aria-activedescendant')
})
function repositionSuggestions() {
  if (suggestions.visible && editor.value && !editor.value.isDestroyed) positionSuggestions(editor.value.view)
}
onMounted(() => {
  window.addEventListener('resize', repositionSuggestions)
  window.addEventListener('scroll', repositionSuggestions, true)
})
onBeforeUnmount(() => {
  hideSuggestions()
  uploadController?.abort()
  pasteControllers.forEach(controller => controller.abort())
  window.removeEventListener('resize', repositionSuggestions)
  window.removeEventListener('scroll', repositionSuggestions, true)
})

async function pasteTicket(text: string) {
  const current = editor.value
  if (!current || props.disabled) return
  hideSuggestions()
  const from = current.state.selection.from
  current.chain().insertContent({ type: 'text', text, marks: [{ type: 'link', attrs: { href: text } }] })
    .command(({ tr }) => { tr.removeStoredMark(current.schema.marks.link!); return true }).run()
  let range = { from, to: current.state.selection.from }
  const map = ({ transaction }: { transaction: Transaction }) => { range = mapPastedRange(range, transaction.mapping) }
  current.on('transaction', map)
  const controller = new AbortController()
  pasteControllers.add(controller)
  try {
    const value = await resolveTicketUrl(text, controller.signal)
    if (!value || current.isDestroyed || controller.signal.aborted) return
    if (range.from >= range.to || current.state.doc.textBetween(range.from, range.to) !== text) return
    current.chain().insertContentAt(range,
      { type: 'reference', attrs: { kind: 'ticket', id: value.id } }, { updateSelection: false }).run()
  } finally {
    current.off('transaction', map)
    pasteControllers.delete(controller)
  }
}

const blockStyle = computed(() => {
  if (editor.value?.isActive('heading')) return String(editor.value.getAttributes('heading').level)
  return 'paragraph'
})
function setBlock(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  if (value === 'paragraph') editor.value?.chain().focus().setParagraph().run()
  else editor.value?.chain().focus().setHeading({ level: Number(value) as Level }).run()
}

const formats = [
  { label: 'Bold', text: 'B', name: 'bold', run: () => editor.value?.chain().focus().toggleBold().run() },
  { label: 'Italic', text: 'I', name: 'italic', run: () => editor.value?.chain().focus().toggleItalic().run() },
  { label: 'Strikethrough', text: 'S', name: 'strike', run: () => editor.value?.chain().focus().toggleStrike().run() },
  { label: 'Bullet list', text: '• List', name: 'bulletList', run: () => editor.value?.chain().focus().toggleBulletList().run() },
  { label: 'Numbered list', text: '1. List', name: 'orderedList', run: () => editor.value?.chain().focus().toggleOrderedList().run() },
  { label: 'Checklist', text: '☑ Tasks', name: 'taskList', run: () => editor.value?.chain().focus().toggleTaskList().run() },
  { label: 'Quote', text: '❝', name: 'blockquote', run: () => editor.value?.chain().focus().toggleBlockquote().run() },
  { label: 'Inline code', text: '</>', name: 'code', run: () => editor.value?.chain().focus().toggleCode().run() },
  { label: 'Code block', text: '{ }', name: 'codeBlock', run: () => editor.value?.chain().focus().toggleCodeBlock().run() },
]

function editLink() {
  linkUrl.value = editor.value?.getAttributes('link').href || ''
  linkError.value = ''
  linkOpen.value = !linkOpen.value
}
function applyLink() {
  let href = linkUrl.value.trim()
  if (!href) {
    editor.value?.chain().focus().extendMarkRange('link').unsetLink().run()
    linkOpen.value = false
    return
  }
  if (!/^(?:[a-z][a-z\d+.-]*:|\/|#)/i.test(href)) href = 'https://' + href
  try {
    if (!['http:', 'https:', 'mailto:', 'tel:'].includes(new URL(href, window.location.origin).protocol)) throw new Error()
  } catch {
    linkError.value = 'Enter a valid web address, email link, or relative URL.'
    return
  }
  const current = editor.value
  if (current?.state.selection.empty && !current.isActive('link')) {
    current.chain().focus().insertContent([
      { type: 'text', text: href, marks: [{ type: 'link', attrs: { href } }] },
      { type: 'text', text: ' ' },
    ]).run()
  } else {
    current?.chain().focus().extendMarkRange('link').setLink({ href }).run()
  }
  linkOpen.value = false
}

async function attach(files: File[]) {
  const current = editor.value
  if (!current || props.disabled || uploading.value || !files.length) return
  if (!props.itemId && !props.projectId) {
    error.value = 'Choose a project before attaching files.'
    return
  }
  // Map the insertion point through edits made while a file is uploading.
  let bookmark = current.state.selection.getBookmark()
  const mapSelection = ({ transaction }: { transaction: Transaction }) => {
    bookmark = bookmark.map(transaction.mapping)
  }
  current.on('transaction', mapSelection)
  error.value = ''
  progress.value = 0
  emit('uploading', true)
  const controller = new AbortController()
  uploadController = controller
  try {
    for (const file of files) {
      const attachment = await uploadAttachment({ itemId: props.itemId, projectId: props.projectId }, file, value => { progress.value = value }, controller.signal)
      if (current.isDestroyed) return
      const inlineImage = /\.(png|jpe?g|gif|webp)$/i.test(attachment.filename)
      const node = inlineImage
        ? { type: 'image', attrs: { src: attachment.url, alt: attachment.filename } }
        : { type: 'text', text: attachment.filename, marks: [{ type: 'link', attrs: { href: attachment.url } }] }
      current.chain().focus().command(({ tr }) => {
        tr.setSelection(bookmark.resolve(tr.doc))
        return true
      }).insertContent([node, { type: 'text', text: ' ' }]).run()
      bookmark = current.state.selection.getBookmark()
      emit('uploaded')
    }
  } catch (e) {
    if (!controller.signal.aborted) error.value = (e as Error).message
  } finally {
    current.off('transaction', mapSelection)
    progress.value = null
    emit('uploading', false)
    if (fileInput.value) fileInput.value.value = ''
  }
}
</script>

<template>
  <div class="rich-text-editor" :class="{ 'is-disabled': disabled }" :aria-busy="uploading">
    <div v-if="editor" class="rich-text-toolbar" role="toolbar" :aria-label="`${label} formatting`">
      <select :value="blockStyle" :disabled="disabled" aria-label="Text style" title="Text style" @change="setBlock">
        <option value="paragraph">Normal text</option>
        <option v-for="level in 6" :key="level" :value="level">Heading {{ level }}</option>
      </select>
      <button v-for="format in formats" :key="format.name" type="button" :data-format="format.name"
        :aria-label="format.label" :title="format.label" :aria-pressed="editor.isActive(format.name)"
        :disabled="disabled" @mousedown.prevent @click="format.run">{{ format.text }}</button>
      <button type="button" aria-label="Insert or edit link" title="Insert or edit link"
        :aria-pressed="linkOpen || editor.isActive('link')" :disabled="disabled" @mousedown.prevent @click="editLink">Link</button>
      <button type="button" aria-label="Insert table" title="Insert table" :disabled="disabled"
        @mousedown.prevent @click="editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()">Table</button>
      <button type="button" aria-label="Undo" title="Undo" :disabled="disabled || !editor.can().undo()"
        @mousedown.prevent @click="editor.chain().focus().undo().run()">↶</button>
      <button type="button" aria-label="Redo" title="Redo" :disabled="disabled || !editor.can().redo()"
        @mousedown.prevent @click="editor.chain().focus().redo().run()">↷</button>
    </div>
    <div v-if="linkOpen" class="rich-text-link" @keydown.esc.stop.prevent="linkOpen = false">
      <input v-model="linkUrl" type="text" aria-label="Link address" placeholder="https://example.com"
        :disabled="disabled" @keydown.enter.stop.prevent="applyLink" />
      <button type="button" :disabled="disabled || !linkUrl.trim()" @click="applyLink">Apply link</button>
      <button v-if="editor?.isActive('link')" type="button" :disabled="disabled"
        @click="linkUrl = ''; applyLink()">Remove link</button>
      <button type="button" @click="linkOpen = false" aria-label="Close link editor">×</button>
      <p v-if="linkError" class="error" role="alert">{{ linkError }}</p>
    </div>
    <div v-if="editor?.isActive('table')" class="rich-text-table-tools" aria-label="Table tools">
      <button type="button" :disabled="disabled" @mousedown.prevent @click="editor.chain().focus().addRowAfter().run()">＋ Row</button>
      <button type="button" :disabled="disabled" @mousedown.prevent @click="editor.chain().focus().addColumnAfter().run()">＋ Column</button>
      <button type="button" :disabled="disabled" @mousedown.prevent @click="editor.chain().focus().deleteTable().run()">Remove table</button>
    </div>
    <EditorContent :editor="editor" class="rich-text-content" :class="{ 'is-empty': editor?.isEmpty }" />
    <p class="reference-help">Type @ to mention someone or # to link a ticket. Paste a ticket URL to show its title and status.</p>
    <div v-if="itemId || projectId" class="rich-text-attachments">
      <button type="button" :disabled="disabled || uploading" @click="fileInput?.click()">＋ Attach files</button>
      <span>Drop files or paste an image · up to 20 MB</span>
      <input ref="fileInput" type="file" multiple hidden :aria-label="`${label} attachments`"
        @change="attach(Array.from(($event.target as HTMLInputElement).files || []))" />
    </div>
    <div v-if="uploading" class="rich-text-progress" role="status">Uploading… {{ progress }}%
      <progress :value="progress || 0" max="100" />
    </div>
    <p v-if="error" class="error rich-text-error" role="alert">{{ error }}</p>
  </div>
  <Teleport to="body">
    <div v-if="suggestions.visible" :id="suggestionId" class="reference-suggestions" role="listbox"
      :aria-label="suggestions.kind === 'user' ? 'Mention a user' : 'Link a ticket'"
      :style="{ top: `${suggestions.top}px`, left: `${suggestions.left}px`, width: `${suggestions.width}px` }">
      <div class="suggestion-heading">{{ suggestions.kind === 'user' ? 'Mention a user' : 'Link a ticket' }}</div>
      <p v-if="suggestions.loading" role="status">Searching…</p>
      <p v-else-if="!suggestions.items.length">No matching {{ suggestions.kind === 'user' ? 'users' : 'tickets' }}.</p>
      <button v-for="(value, index) in suggestions.items" :id="`${suggestionId}-${index}`" :key="value.id" type="button" role="option" tabindex="-1"
        :aria-selected="index === suggestions.selected" @mousedown.prevent @click="selectReference(value)"
        @mouseenter="suggestions.selected = index">
        <template v-if="value.kind === 'user'"><strong>@{{ value.name }}</strong><small>{{ value.role }}</small></template>
        <template v-else><strong>{{ value.reference }} · {{ value.title }}</strong><small>{{ value.status }}</small></template>
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.rich-text-editor { border: 1px solid var(--border); border-radius: 7px; background: var(--surface); overflow: hidden; }
.rich-text-editor:focus-within { outline: 2px solid var(--accent-muted); outline-offset: 1px; }
.rich-text-toolbar, .rich-text-table-tools { display: flex; flex-wrap: wrap; gap: 3px; align-items: center; padding: 7px; background: var(--subtle); border-bottom: 1px solid var(--border); }
.rich-text-toolbar button, .rich-text-table-tools button { min-height: 30px; padding: 5px 7px; font-size: 11px; border: 1px solid transparent; background: transparent; color: var(--accent-muted); box-shadow: none; }
.rich-text-toolbar button:hover, .rich-text-table-tools button:hover { background: var(--accent-soft); }
.rich-text-toolbar button[aria-pressed="true"] { background: var(--accent-soft); color: var(--accent); border-color: var(--accent-border); }
.rich-text-toolbar button[data-format="bold"] { font-weight: 750; }
.rich-text-toolbar button[data-format="italic"] { font-style: italic; }
.rich-text-toolbar button[data-format="strike"] { text-decoration: line-through; }
.rich-text-toolbar button[data-format="code"], .rich-text-toolbar button[data-format="codeBlock"] { font-family: monospace; }
.rich-text-toolbar select { width: 116px; height: 30px; padding: 4px 6px; font-size: 11px; }
.rich-text-link { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 10px; background: var(--subtle); border-bottom: 1px solid var(--border); }
.rich-text-link input { flex: 1; min-width: 130px; font-size: 12px; }
.rich-text-link button { font-size: 11px; }
.rich-text-link .error { width: 100%; margin: 0; }
.rich-text-table-tools button { font-size: 10px; min-height: 26px; }
.rich-text-content :deep(.tiptap) { min-height: 150px; padding: 14px; outline: none; color: var(--text); font-size: 13px; font-weight: 400; line-height: 1.85; overflow-wrap: anywhere; }
.rich-text-content.is-empty :deep(.tiptap)::before { content: attr(data-placeholder); float: left; height: 0; color: var(--muted); pointer-events: none; }
.rich-text-content :deep(.tiptap > :first-child) { margin-top: 0; }
.rich-text-content :deep(.tiptap > :last-child) { margin-bottom: 0; }
.rich-text-content :deep(p) { margin: 0 0 10px; }
.rich-text-content :deep(h1) { font-size: 25px; }
.rich-text-content :deep(h2) { font-size: 21px; }
.rich-text-content :deep(h3) { font-size: 18px; }
.rich-text-content :deep(h4), .rich-text-content :deep(h5), .rich-text-content :deep(h6) { font-size: 15px; }
.rich-text-content :deep(h1), .rich-text-content :deep(h2), .rich-text-content :deep(h3), .rich-text-content :deep(h4), .rich-text-content :deep(h5), .rich-text-content :deep(h6) { margin: 20px 0 10px; line-height: 1.4; letter-spacing: normal; color: var(--text); }
.rich-text-content :deep(ul), .rich-text-content :deep(ol) { padding-left: 24px; margin: 10px 0; }
.rich-text-content :deep(li p) { margin-bottom: 4px; }
.rich-text-content :deep(blockquote) { border-left: 3px solid var(--accent-border); margin: 12px 0; padding-left: 14px; color: var(--accent-muted); }
.rich-text-content :deep(code) { font-size: 12px; background: var(--accent-soft); padding: 2px 4px; border-radius: 3px; }
.rich-text-content :deep(pre) { background: var(--subtle); border: 1px solid var(--border); border-radius: 5px; padding: 14px; overflow: auto; }
.rich-text-content :deep(pre code) { padding: 0; background: none; }
.rich-text-content :deep(img) { max-width: 100%; max-height: 450px; object-fit: contain; vertical-align: middle; border: 1px solid var(--border); border-radius: 5px; }
.rich-text-content :deep(.ProseMirror-selectednode) { outline: 2px solid var(--accent-muted); }
.rich-text-content :deep(ul[data-type="taskList"]) { padding-left: 0; list-style: none; }
.rich-text-content :deep(li[data-checked]) { display: flex; align-items: flex-start; gap: 8px; }
.rich-text-content :deep(li[data-checked] > label) { display: flex; flex-direction: row; flex: 0 0 auto; margin: 5px 0 0; }
.rich-text-content :deep(li[data-checked] > div) { flex: 1; min-width: 0; }
.rich-text-content :deep(input[type="checkbox"]) { width: 14px; height: 14px; padding: 0; margin: 0; accent-color: var(--purple); cursor: pointer; }
.rich-text-content :deep(.tableWrapper) { overflow-x: auto; margin: 12px 0; }
.rich-text-content :deep(table) { border-collapse: collapse; width: 100%; table-layout: fixed; }
.rich-text-content :deep(td), .rich-text-content :deep(th) { border: 1px solid var(--border); padding: 6px 9px; position: relative; min-width: 70px; vertical-align: top; }
.rich-text-content :deep(th) { background: var(--accent-soft); font-weight: 600; }
.rich-text-content :deep(td p), .rich-text-content :deep(th p) { margin: 0; }
.rich-text-content :deep(.selectedCell)::after { content: ''; position: absolute; inset: 0; background: color-mix(in srgb, var(--accent) 20%, transparent); pointer-events: none; }
.rich-text-attachments { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 7px; border-top: 1px dashed var(--accent-border); }
.rich-text-attachments button { background: transparent; border-color: transparent; min-height: 28px; padding: 4px 7px; font-size: 11px; color: var(--accent); }
.rich-text-attachments span { font-size: 10px; color: var(--muted); }
.rich-text-progress { padding: 10px; background: var(--accent-soft); font-size: 12px; color: var(--accent); }
.rich-text-progress progress { display: block; width: 100%; margin-top: 6px; accent-color: var(--purple); }
.rich-text-error { margin: 8px; }
.reference-help { margin: 0; padding: 7px 12px; color: var(--muted); font-size: 10px; line-height: 1.6; border-top: 1px solid var(--border); }
.reference-suggestions { position: fixed; z-index: 50; padding: 5px; max-height: 300px; overflow-y: auto; background: var(--surface); color: var(--text); border: 1px solid var(--accent-border); border-radius: 8px; box-shadow: 0 8px 28px #15271e24; }
.suggestion-heading { padding: 6px 9px; font-size: 10px; font-weight: 650; color: var(--muted); }
.reference-suggestions button { display: flex; align-items: flex-start; flex-direction: column; gap: 4px; width: 100%; text-align: left; border: 0; border-radius: 4px; padding: 9px; background: transparent; }
.reference-suggestions button[aria-selected="true"] { background: var(--accent-soft); }
.reference-suggestions strong { font-size: 12px; font-weight: 550; overflow-wrap: anywhere; }
.reference-suggestions small { font-size: 10px; color: var(--muted); }
.reference-suggestions p { padding: 10px; margin: 0; font-size: 12px; color: var(--muted); }
.is-disabled { opacity: .75; }
@media (max-width: 720px) { .rich-text-toolbar { gap: 2px; } .rich-text-toolbar button { padding: 5px 6px; } .rich-text-content :deep(.tiptap) { padding: 12px; } }
</style>
