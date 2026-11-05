import assert from 'node:assert/strict'
import test from 'node:test'
import { MarkdownManager } from '@tiptap/markdown'
import { Marked, marked } from 'marked'
import { createEditorExtensions } from '../src/editorExtensions.ts'

function editorMarkdown() {
  const extensions = createEditorExtensions()
  const options = extensions.find(extension => extension.name === 'markdown').options
  return new MarkdownManager({ extensions, marked: options.marked, markedOptions: options.markedOptions })
}

test('checklists survive multiple editors without contaminating read-only parsers', () => {
  const source = '- [ ] Pending task\n- [x] Finished task'
  const reader = new Marked()
  const expectedHtml = reader.parse(source)
  const editors = Array.from({ length: 4 }, editorMarkdown)
  for (const editor of editors) {
    const content = editor.parse(source)
    assert.equal(content.content[0].type, 'taskList')
    assert.deepEqual(content.content[0].content.map(item => item.attrs.checked), [false, true])
    assert.deepEqual(editor.parse(editor.serialize(content)), content)
    assert.equal(reader.parse(source), expectedHtml)
    assert.equal(marked.parse(source), expectedHtml)
  }
  assert.notEqual(editors[0].instance, editors[1].instance)
})

test('existing formatted descriptions and attachment URLs round-trip without semantic loss', () => {
  const editor = editorMarkdown()
  const source = [
    '## Release checklist',
    '**Bold** and *italic* and ~~removed~~ with `inline code`.',
    '- Bullet\n  - Nested bullet\n\n1. First\n2. Second',
    '- [ ] Pending\n- [x] Finished',
    '> Quoted text',
    '```python\nprint("hello")\n```',
    '| Name | Status |\n| --- | --- |\n| Release | Ready |',
    '[Download notes](/api/v1/attachments/file-id/download)',
    '![Screenshot](/api/v1/attachments/image-id/download)',
  ].join('\n\n')
  const original = editor.parse(source)
  const saved = editor.serialize(original)
  assert.deepEqual(editorMarkdown().parse(saved), original)
  assert.match(saved, /```python/)
  assert.match(saved, /\[x\] Finished/)
  assert.match(saved, /\/api\/v1\/attachments\/file-id\/download/)
  assert.match(saved, /!\[Screenshot\]\(\/api\/v1\/attachments\/image-id\/download\)/)
})

test('user mentions and ticket atoms preserve stable IDs without storing protected labels', () => {
  const editor = editorMarkdown()
  const ticket = '00000000-0000-0000-0000-000000000001'
  const person = '00000000-0000-0000-0000-000000000002'
  const source = `Ask [@user](/users/${person}) about [Ticket](/items/${ticket}).`
  const content = editor.parse(source)
  const references = content.content[0].content.filter(node => node.type === 'reference')
  assert.deepEqual(references.map(node => node.attrs), [{ kind: 'user', id: person }, { kind: 'ticket', id: ticket }])
  assert.equal(editor.serialize(content), source)
  assert.deepEqual(editorMarkdown().parse(editor.serialize(content)), content)
  const atom = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'reference', attrs: { kind: 'ticket', id: ticket, title: 'Private title', status: 'Open' } }] }] }
  assert.equal(editor.serialize(atom), `[Ticket](/items/${ticket})`)
})
