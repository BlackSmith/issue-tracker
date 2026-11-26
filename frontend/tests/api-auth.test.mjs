import assert from 'node:assert/strict'
import { afterEach, beforeEach, mock, test } from 'node:test'
import { api, ApiError, auth, refreshAuth, signOut } from '../src/api.ts'

const properties = new Map()
const root = { style: { setProperty: (key, value) => properties.set(key, value) }, dataset: {} }
const user = { id: 'member-id', name: 'Member', role: 'member', theme_accent: 'purple', theme_background: 'sand' }
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

beforeEach(() => {
  mock.method(globalThis, 'fetch')
  globalThis.document = { documentElement: root, querySelector: () => null }
  Object.assign(auth, { user: { ...user }, csrf: 'stale-csrf', ready: true })
  properties.clear()
})
afterEach(() => { mock.restoreAll(); delete globalThis.document })

test('a successful attachment deletion accepts an empty 204 response', async () => {
  fetch.mock.mockImplementation(async (path, options) => {
    assert.equal(path, '/api/v1/items/item-id/attachments/attachment-id')
    assert.equal(options.method, 'DELETE')
    assert.equal(options.headers.get('X-CSRF-Token'), auth.csrf)
    return new Response(null, { status: 204 })
  })
  assert.equal(await api('/items/item-id/attachments/attachment-id', { method: 'DELETE' }), undefined)
})

test('an expired session clears the signed-in UI and appearance after an API 401', async () => {
  const paths = []
  fetch.mock.mockImplementation(async path => {
    paths.push(path)
    return path.endsWith('/auth/me') ? json({ user: null, csrf_token: 'anonymous-csrf' }) : json({ detail: 'Authentication required' }, 401)
  })
  await assert.rejects(api('/projects'), error => error instanceof ApiError && error.status === 401)
  assert.deepEqual(paths, ['/api/v1/projects', '/api/v1/auth/me'])
  assert.equal(auth.user, null)
  assert.equal(auth.csrf, 'anonymous-csrf')
  assert.equal(properties.get('--accent'), '#26734d')
  assert.equal(properties.get('--app-background'), '#ffffff')
})

test('invalid CSRF refreshes the session without replaying a failed write', async () => {
  const calls = []
  fetch.mock.mockImplementation(async (path, options) => {
    calls.push([path, options.method || 'GET'])
    return path.endsWith('/auth/me') ? json({ user, csrf_token: 'fresh-csrf' }) : json({ detail: 'Invalid CSRF token' }, 403)
  })
  await assert.rejects(api('/items/item-id', { method: 'PATCH', body: '{}' }), { message: 'Invalid CSRF token', status: 403 })
  assert.deepEqual(calls, [['/api/v1/items/item-id', 'PATCH'], ['/api/v1/auth/me', 'GET']])
  assert.equal(auth.user.id, user.id)
  assert.equal(auth.csrf, 'fresh-csrf')
})

test('sign out with an expired session shows the login screen without posting stale CSRF', async () => {
  fetch.mock.mockImplementation(async path => {
    assert.equal(path, '/api/v1/auth/me')
    return json({ user: null, csrf_token: 'anonymous-csrf' })
  })
  await signOut()
  assert.equal(auth.user, null)
  assert.equal(fetch.mock.callCount(), 1)
})

test('sign out refreshes CSRF before the POST and then refreshes the anonymous session', async () => {
  let loggedOut = false
  const calls = []
  fetch.mock.mockImplementation(async (path, options) => {
    calls.push(path)
    if (path.endsWith('/auth/me')) return json({ user: loggedOut ? null : user, csrf_token: loggedOut ? 'anonymous-csrf' : 'fresh-csrf' })
    assert.equal(path, '/api/v1/auth/logout')
    assert.equal(options.method, 'POST')
    assert.equal(options.headers.get('X-CSRF-Token'), 'fresh-csrf')
    loggedOut = true
    return json({ ok: true })
  })
  await signOut()
  assert.deepEqual(calls, ['/api/v1/auth/me', '/api/v1/auth/logout', '/api/v1/auth/me'])
  assert.equal(auth.user, null)
})

test('session expiry between sign-out preflight and POST is handled without retrying logout', async () => {
  let expired = false, posts = 0
  fetch.mock.mockImplementation(async (path, options) => {
    if (path.endsWith('/auth/me')) return json({ user: expired ? null : user, csrf_token: expired ? 'anonymous-csrf' : 'fresh-csrf' })
    assert.equal(options.method, 'POST')
    posts++
    expired = true
    return json({ detail: 'Invalid CSRF token' }, 403)
  })
  await signOut()
  assert.equal(posts, 1)
  assert.equal(auth.user, null)
})

test('ordinary permission failures and invalid bearer credentials do not change browser authentication', async () => {
  fetch.mock.mockImplementation(async () => json({ detail: 'Project administrator required' }, 403))
  await assert.rejects(api('/projects/private/members'), { status: 403 })
  fetch.mock.mockImplementation(async () => json({ detail: 'Invalid API token' }, 401))
  await assert.rejects(api('/projects', { headers: { Authorization: 'Bearer invalid' } }), { status: 401 })
  assert.equal(fetch.mock.callCount(), 2)
  assert.equal(auth.user.id, user.id)
  assert.equal(auth.csrf, 'stale-csrf')
})

test('concurrent session refreshes share a single request', async () => {
  let complete
  fetch.mock.mockImplementation(() => new Promise(resolve => { complete = resolve }))
  const first = refreshAuth(), second = refreshAuth()
  assert.equal(first, second)
  assert.equal(fetch.mock.callCount(), 1)
  complete(json({ user, csrf_token: 'fresh-csrf' }))
  await Promise.all([first, second])
  assert.equal(auth.csrf, 'fresh-csrf')
})

test('a failed session refresh does not recurse or keep an invalid user after confirmed 401', async () => {
  fetch.mock.mockImplementation(async path => path.endsWith('/auth/me')
    ? json({ detail: 'Unavailable' }, 503)
    : json({ detail: 'Authentication required' }, 401))
  await assert.rejects(api('/projects'), { status: 401 })
  assert.equal(fetch.mock.callCount(), 2)
  assert.equal(auth.user, null)
  assert.equal(auth.csrf, '')
})
