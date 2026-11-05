import assert from 'node:assert/strict'
import test from 'node:test'
import { internalTicketTarget, referenceLinkText, storedReference, ticketShorthands } from '../src/referenceSyntax.ts'

const origin = 'https://tracker.example'
const id = '00000000-0000-0000-0000-000000000001'

test('only same-origin ticket URLs are eligible for conversion', () => {
  assert.deepEqual(internalTicketTarget(`${origin}/product/123?view=panel#activity`, origin), { slug: 'product', number: '123' })
  assert.deepEqual(internalTicketTarget(`/items/${id}`, origin), { id })
  assert.deepEqual(internalTicketTarget(`${origin}/projects/${id}?item=${id}`, origin), { id, projectId: id })
  for (const url of ['https://tracker.example.attacker.test/product/1', 'https://other.example/product/1',
    'javascript:alert(1)', 'https://user:password@tracker.example/product/1', '/product/', '/product/0', '/api/v1/items/123']) {
    assert.equal(internalTicketTarget(url, origin), null, url)
  }
})

test('reference storage and shorthand recognition do not confuse ordinary text', () => {
  assert.deepEqual(storedReference(`/users/${id}`), { kind: 'user', id })
  assert.equal(storedReference('/items/not-a-uuid'), null)
  assert.equal(storedReference(`https://attacker.test/items/${id}`), null)
  const text = 'See #123 and (#APP-1), not abc#12 or #123abc or #123ž or a color #ff1234.'
  assert.deepEqual(ticketShorthands(text).map(match => text.slice(match.from, match.to)), ['#123', '#APP-1'])
})

test('enrichment preserves pasted URL continuations and leaves custom link labels intact', () => {
  const url = `${origin}/product/123`
  assert.deepEqual(referenceLinkText(url, url), { suffix: '' })
  assert.deepEqual(referenceLinkText(url, `${url} KEEP THIS TEXT`), { suffix: ' KEEP THIS TEXT' })
  assert.equal(referenceLinkText(url, 'Read these important details'), null)
  assert.deepEqual(referenceLinkText(`/items/${id}`, 'Ticket'), { suffix: '' })
  assert.deepEqual(referenceLinkText(`/users/${id}`, '@user'), { suffix: '' })
})
