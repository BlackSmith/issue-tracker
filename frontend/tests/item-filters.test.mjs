import assert from 'node:assert/strict'
import test from 'node:test'
import { defaultStatuses, readFilterValues, statusFilterQuery } from '../src/itemFilters.ts'

test('missing statuses default to active items while explicit empty values mean all statuses', () => {
  assert.deepEqual(readFilterValues(undefined, defaultStatuses), ['Open', 'In progress'])
  assert.deepEqual(readFilterValues('', defaultStatuses), [])
  assert.deepEqual(readFilterValues(null, defaultStatuses), [])
  for (const values of [[], ['Done'], ['Open', 'Done'], ['In progress', 'Open']]) {
    assert.deepEqual(new Set(readFilterValues(statusFilterQuery(values), defaultStatuses)), new Set(values))
  }
})

test('repeated filter parameters retain complete labels and support legacy single-value links', () => {
  assert.deepEqual(readFilterValues('Open', defaultStatuses), ['Open'])
  assert.deepEqual(readFilterValues(['Open', 'Done', 'Open']), ['Open', 'Done'])
  const names = ['needs, triage', 'backend & API']
  const params = new URLSearchParams()
  names.forEach(name => params.append('label', name))
  assert.deepEqual(readFilterValues(params.getAll('label')), names)
  assert.deepEqual(readFilterValues(undefined), [])
})
