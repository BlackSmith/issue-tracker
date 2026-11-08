<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '../api'
import type { ApiToken } from '../types'

const props = withDefaults(defineProps<{
  basePath?: string
  ownerRole: string
  disabled?: boolean
  title?: string
}>(), { basePath: '/tokens', disabled: false, title: 'Personal API tokens' })
const tokens = ref<ApiToken[]>([]), loading = ref(true), busy = ref(false), error = ref('')
const showCreate = ref(false)
const name = ref(''), access = ref('read'), secret = ref(''), revealedId = ref(''), copied = ref(false)
const secretInput = ref<{ $el: HTMLInputElement } | null>(null)
const date = new Date(Date.now() + 30 * 86400000)
const expiresAt = ref(new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16))
let sequence = 0

async function load() {
  const current = ++sequence
  loading.value = true
  try {
    const result = await api<ApiToken[]>(props.basePath)
    if (current === sequence) tokens.value = result
  } catch (e) { if (current === sequence) error.value = (e as Error).message }
  finally { if (current === sequence) loading.value = false }
}
watch(() => props.basePath, () => { showCreate.value = false; secret.value = ''; revealedId.value = ''; error.value = ''; tokens.value = []; void load() }, { immediate: true })
watch(() => props.ownerRole, value => { if (value === 'reader') access.value = 'read' })

async function create() {
  if (props.disabled || busy.value) return
  busy.value = true; error.value = ''; secret.value = ''; copied.value = false
  try {
    const result = await api<ApiToken & { token: string }>(props.basePath, { method: 'POST', body: JSON.stringify({
      name: name.value, scopes: access.value === 'write' ? ['read', 'write'] : ['read'], expires_at: new Date(expiresAt.value).toISOString(),
    }) })
    const { token, ...metadata } = result
    secret.value = token; revealedId.value = metadata.id
    tokens.value = [metadata, ...tokens.value]
    name.value = ''
    showCreate.value = false
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function revoke(token: ApiToken) {
  busy.value = true; error.value = ''
  try {
    const result = await api<ApiToken>(`${props.basePath}/${token.id}`, { method: 'DELETE' })
    tokens.value = tokens.value.map(row => row.id === token.id ? result : row)
    if (revealedId.value === token.id) secret.value = ''
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function copy() {
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(secret.value)
    else {
      secretInput.value?.$el.select()
      if (!document.execCommand('copy')) throw new Error()
    }
    copied.value = true
  } catch { secretInput.value?.$el.select(); error.value = 'Select and copy the token shown above.' }
}
function formatted(value: string | null) { return value ? new Date(value).toLocaleString() : 'Never' }
</script>

<template>
  <section class="token-manager">
    <header><div><h2>{{ title }}</h2><p>Use a separate token for each integration or AI tool. Access is limited by the account and its project permissions.</p></div><PButton type="button" class="quiet" :disabled="loading || busy" @click="error = ''; load()">Refresh</PButton></header>
    <PButton v-if="!showCreate" type="button" class="token-create-toggle" :disabled="busy || disabled" :aria-expanded="false" @click="showCreate = true; error = ''">Create token</PButton>
    <p v-if="disabled && !showCreate" class="hint">Enable this bot before issuing a token.</p>
    <form v-if="showCreate" class="token-create-form" @submit.prevent="create">
      <label>Token name<InputText v-model="name" required maxlength="100" placeholder="e.g. AI assistant or reporting tool" :disabled="busy || disabled" /></label>
      <div class="token-fields"><label>Permissions<PSelect v-model="access" :options="[{ label: 'Read-only', value: 'read' }, { label: 'Read and write', value: 'write', disabled: ownerRole === 'reader' }]" option-label="label" option-value="value" option-disabled="disabled" aria-label="Permissions" :disabled="busy || disabled" /></label><label>Expires at<InputText v-model="expiresAt" type="datetime-local" required :disabled="busy || disabled" /></label></div>
      <div class="token-create-footer"><span>{{ disabled ? 'Enable this bot before issuing a token.' : 'Expiration is required, up to one year. Browser login is separate from API access.' }}</span><div class="token-create-actions"><PButton type="button" severity="secondary" outlined :disabled="busy" @click="showCreate = false">Cancel</PButton><PButton type="submit" :loading="busy" :disabled="busy || disabled">Create token</PButton></div></div>
    </form>
    <div v-if="secret" class="token-reveal" role="status"><strong>Copy your token now</strong><p>The full value is shown only once.</p><div><InputText ref="secretInput" :model-value="secret" readonly aria-label="New API token" spellcheck="false" /><PButton type="button" @click="copy">{{ copied ? 'Copied' : 'Copy' }}</PButton></div><PButton type="button" class="quiet" @click="secret = ''">I have saved the token</PButton></div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="loading" class="hint">Loading tokens…</p>
    <p v-else-if="!tokens.length" class="hint">No tokens yet. Create one to connect an integration.</p>
    <ul v-else class="token-list"><li v-for="token in tokens" :key="token.id"><div class="token-row-top"><strong>{{ token.name }}</strong><span class="token-state" :data-status="token.status">{{ token.status }}</span><PButton type="button" severity="danger" outlined :disabled="busy || token.status === 'revoked'" @click="revoke(token)">Revoke</PButton></div><code>{{ token.prefix }}…</code><div class="token-metadata"><span>{{ token.scopes.includes('write') ? 'Read and write' : 'Read-only' }}</span><span>Expires {{ formatted(token.expires_at) }}</span><span>Last used {{ formatted(token.last_used_at) }}</span></div></li></ul>
  </section>
</template>

<style scoped>
.token-manager { border: 1px solid var(--border); border-radius: 10px; padding: 26px; background: var(--surface); margin-top: 28px; }
.token-manager > header { display: flex; align-items: flex-start; gap: 12px; border-bottom: 1px solid var(--border); padding-bottom: 18px; margin-bottom: 22px; }
.token-manager header h2 { margin-bottom: 8px; }
.token-manager header p { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.7; }
.token-manager header > button { margin-left: auto; font-size: 11px; }
.token-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.token-create-footer { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 22px; }
.token-create-footer > span { font-size: 10px; line-height: 1.7; color: var(--muted); max-width: 370px; }
.token-create-footer button { flex-shrink: 0; }
.token-create-toggle { margin-bottom: 18px; }
.token-create-actions { display: flex; flex-wrap: wrap; gap: 8px; flex-shrink: 0; }
.token-reveal { border: 1px solid var(--accent-border); border-radius: 7px; background: var(--accent-soft); padding: 15px; margin: 18px 0; }
.token-reveal strong { color: var(--accent); font-size: 13px; }
.token-reveal p { color: var(--muted); font-size: 12px; margin: 8px 0; }
.token-reveal > div { display: flex; gap: 7px; margin: 10px 0; }
.token-reveal input { font: 12px monospace; min-width: 0; }
.token-reveal > .quiet { padding-left: 0; font-size: 11px; }
.token-list { list-style: none; padding: 0; margin: 0; }
.token-list li { border-top: 1px solid var(--border); padding: 15px 0; }
.token-list li:last-child { padding-bottom: 0; }
.token-row-top { display: flex; align-items: center; gap: 8px; margin-bottom: 7px; }
.token-row-top strong { font-size: 12px; overflow-wrap: anywhere; }
.token-row-top button { margin-left: auto; font-size: 11px; min-height: 29px; padding: 5px 8px; }
.token-state { font-size: 9px; text-transform: capitalize; border-radius: 4px; padding: 3px 6px; background: #edf4ef; color: #417451; }
.token-state[data-status="revoked"], .token-state[data-status="expired"] { background: #f1f2f4; color: #7c7f86; }
.token-list code { color: var(--muted); font-size: 10px; }
.token-metadata { display: flex; flex-wrap: wrap; gap: 7px 16px; color: var(--muted); font-size: 10px; margin-top: 9px; line-height: 1.7; }
@media(max-width: 720px) { .token-manager { padding: 18px; } .token-fields { grid-template-columns: 1fr; gap: 0; } .token-create-footer { align-items: flex-start; flex-wrap: wrap; } }
</style>
