import assert from 'node:assert/strict'
import test from 'node:test'
import { getSchema } from '@tiptap/core'
import { EditorState } from '@tiptap/pm/state'
import { createEditorExtensions } from '../src/editorExtensions.ts'
import { mapPastedRange } from '../src/pasteRange.ts'

test('typing around a pending pasted reference stays outside its replacement range', () => {
  const schema = getSchema(createEditorExtensions())
  const url = 'https://tracker.example/project/1'
  const doc = schema.node('doc', null, [schema.node('paragraph', null, [schema.text(url)])])
  const state = EditorState.create({ schema, doc })
  let range = { from: 1, to: url.length + 1 }
  const trailing = state.tr.insertText(' KEEP THIS TEXT', range.to)
  range = mapPastedRange(range, trailing.mapping)
  assert.equal(trailing.doc.textBetween(range.from, range.to), url)
  assert.equal(trailing.doc.textBetween(range.to, trailing.doc.content.size), ' KEEP THIS TEXT')
  const afterTrailing = state.apply(trailing)
  const leading = afterTrailing.tr.insertText('Prefix ', range.from)
  range = mapPastedRange(range, leading.mapping)
  assert.equal(leading.doc.textBetween(range.from, range.to), url)
  assert.equal(leading.doc.textBetween(1, range.from), 'Prefix ')
  const removed = afterTrailing.tr.delete(1, url.length + 1)
  const deletedRange = mapPastedRange({ from: 1, to: url.length + 1 }, removed.mapping)
  assert.equal(deletedRange.from, deletedRange.to)
})
