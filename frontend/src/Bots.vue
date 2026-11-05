<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, auth } from './api'
import type { BotAccount, BotProject, Project } from './types'
import TokenManager from './components/TokenManager.vue'
import UserAvatar from './components/UserAvatar.vue'

const bots = ref<BotAccount[]>([]), projects = ref<Project[]>([]), memberships = ref<BotProject[]>([])
const selectedId = ref(''), error = ref(''), loading = ref(false), busy = ref(false)
const createName = ref(''), createRole = ref('reader'), editName = ref(''), editRole = ref('reader')
const projectId = ref(''), projectRole = ref('reader')
const avatarInput = ref<HTMLInputElement | null>(null)
const selected = computed(() => bots.value.find(bot => bot.id === selectedId.value))
let loadSequence = 0

async function load() {
  if (auth.user?.role !== 'administrator') return
  loading.value = true; error.value = ''
  try {
    const [accounts, available] = await Promise.all([api<BotAccount[]>('/bots'), api<Project[]>('/projects')])
    bots.value = accounts; projects.value = available
    if (!selectedId.value && accounts.length) selectedId.value = accounts[0]!.id
  } catch (e) { error.value = (e as Error).message }
  finally { loading.value = false }
}
async function loadProjects() {
  const id = selectedId.value, sequence = ++loadSequence
  memberships.value = []
  if (!id) return
  try {
    const result = await api<BotProject[]>(`/bots/${id}/projects`)
    if (sequence === loadSequence && id === selectedId.value) memberships.value = result
  } catch (e) { if (sequence === loadSequence) error.value = (e as Error).message }
}
watch(selected, bot => {
  editName.value = bot?.name || ''; editRole.value = bot?.role || 'reader'
  projectId.value = ''; projectRole.value = 'reader'
})
watch(selectedId, loadProjects)
void load()

async function create() {
  busy.value = true; error.value = ''
  try {
    const account = await api<BotAccount>('/bots', { method: 'POST', body: JSON.stringify({ name: createName.value, role: createRole.value }) })
    bots.value = [...bots.value, account]; selectedId.value = account.id; createName.value = ''
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function update(active = selected.value?.active) {
  if (!selected.value) return
  busy.value = true; error.value = ''
  try {
    const value = await api<BotAccount>(`/bots/${selected.value.id}`, { method: 'PUT', body: JSON.stringify({ name: editName.value, role: editRole.value, active }) })
    bots.value = bots.value.map(bot => bot.id === value.id ? value : bot)
    await loadProjects()
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function uploadAvatar(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0], bot = selected.value
  if (!file || !bot) return
  error.value = ''
  if (file.size > 5 * 1024 * 1024) {
    error.value = 'Profile pictures must be smaller than 5 MB'
    input.value = ''
    return
  }
  busy.value = true
  try {
    const data = new FormData()
    data.append('file', file)
    const updated = await api<BotAccount>(`/bots/${bot.id}/avatar`, { method: 'PUT', body: data })
    bot.avatar_url = updated.avatar_url
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false; input.value = '' }
}
async function removeAvatar() {
  const bot = selected.value
  if (!bot) return
  busy.value = true; error.value = ''
  try {
    const updated = await api<BotAccount>(`/bots/${bot.id}/avatar`, { method: 'DELETE' })
    bot.avatar_url = updated.avatar_url
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function grantProject() {
  if (!selected.value || !projectId.value) return
  busy.value = true; error.value = ''
  try {
    await api(`/bots/${selected.value.id}/projects/${projectId.value}`, { method: 'PUT', body: JSON.stringify({ role: projectRole.value }) })
    await loadProjects(); projectId.value = ''
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function removeProject(id: string) {
  if (!selected.value) return
  busy.value = true; error.value = ''
  try {
    await api(`/bots/${selected.value.id}/projects/${id}`, { method: 'DELETE' })
    await loadProjects()
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
</script>

<template>
  <main class="bots-page">
    <div class="breadcrumbs"><RouterLink to="/">Workspace</RouterLink><span>/</span> Bot accounts</div>
    <p v-if="auth.user?.role !== 'administrator'" class="error" role="alert">Administrator access is required.</p>
    <template v-else>
      <header class="page-heading"><div><span class="eyebrow">AUTOMATION & INTEGRATIONS</span><h1>Bot accounts</h1><p>Give automations and AI tools their own identity and project access.</p></div></header>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="bot-layout">
        <aside class="bot-sidebar">
          <section class="bot-card"><h2>Create a bot</h2><form @submit.prevent="create"><label>Bot name<input v-model="createName" required maxlength="200" placeholder="e.g. AI assistant" :disabled="busy" /></label><label>Account permissions<select v-model="createRole" :disabled="busy"><option value="reader">Read-only</option><option value="member">Member — read and write</option></select></label><button class="primary" :disabled="busy">Create bot</button></form></section>
          <nav aria-label="Bot accounts"><p v-if="loading" class="hint">Loading bots…</p><button v-for="bot in bots" :key="bot.id" type="button" :aria-pressed="selectedId === bot.id" :disabled="busy" @click="selectedId = bot.id"><UserAvatar :name="bot.name" :src="bot.avatar_url" /><span class="bot-identity">{{ bot.name }}<small>{{ bot.role === 'reader' ? 'Read-only' : 'Member' }} · {{ bot.active ? 'Active' : 'Disabled' }}</small></span><span class="bot-badge">Bot</span></button></nav>
        </aside>
        <div v-if="selected" class="bot-details">
          <section class="bot-card bot-picture-card" aria-labelledby="bot-picture-heading">
            <h2 id="bot-picture-heading">Bot picture</h2>
            <div class="bot-picture-row">
              <UserAvatar class="bot-picture" :name="selected.name" :src="selected.avatar_url" />
              <div><div class="bot-actions"><button type="button" :disabled="busy" @click="avatarInput?.click()">Upload picture</button><button v-if="selected.avatar_url" type="button" :disabled="busy" @click="removeAvatar">Remove picture</button></div><p class="hint">PNG, JPEG, GIF or WebP · up to 5 MB. Cropped to a square and saved immediately.</p></div>
            </div>
            <input ref="avatarInput" type="file" accept="image/png,image/jpeg,image/gif,image/webp" aria-label="Bot picture" hidden :disabled="busy" @change="uploadAvatar" />
          </section>
          <section class="bot-card"><header><h2>{{ selected.name }} <span class="bot-badge">Bot</span></h2><p>API access only. Bots have no password or OIDC login.</p></header><form @submit.prevent="update()"><label>Display name<input v-model="editName" required maxlength="200" :disabled="busy" /></label><label>Account permissions<select v-model="editRole" :disabled="busy"><option value="reader">Read-only</option><option value="member">Member — read and write</option></select></label><div class="bot-actions"><button class="primary" :disabled="busy">Save bot</button><button type="button" :disabled="busy" @click="update(!selected.active)">{{ selected.active ? 'Disable bot' : 'Enable bot' }}</button></div></form><p class="hint">Disabling a bot revokes all its tokens. Re-enabling requires a new token.</p></section>
          <section class="bot-card"><header><h2>Project access</h2><p>Bots can access only explicitly assigned projects, including organization-visible projects.</p></header><form class="bot-project-form" @submit.prevent="grantProject"><label>Project<select v-model="projectId" required :disabled="busy"><option value="" disabled>Select a project</option><option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }} ({{ p.key }})</option></select></label><label>Project permission<select v-model="projectRole" :disabled="busy"><option value="reader">Read-only</option><option value="member" :disabled="selected.role === 'reader'">Read and write</option></select></label><button class="primary" :disabled="busy || !projectId">Grant / update access</button></form><ul class="bot-project-list"><li v-for="p in memberships" :key="p.project_id"><RouterLink :to="`/${p.slug}/`">{{ p.name }}</RouterLink><span>{{ p.effective_role === 'reader' ? 'Read-only' : 'Read and write' }}</span><button type="button" :disabled="busy" @click="removeProject(p.project_id)">Remove</button></li></ul><p v-if="!memberships.length" class="hint">No projects assigned. This bot cannot read or change tickets yet.</p></section>
          <TokenManager :key="selected.id + ':' + selected.active" :base-path="`/bots/${selected.id}/tokens`" :owner-role="selected.role" :disabled="!selected.active" title="Bot API tokens" />
        </div>
        <section v-else class="empty-state"><h2>Select or create a bot</h2><p>Each bot gets its own tokens and activity attribution.</p></section>
      </div>
    </template>
  </main>
</template>

<style scoped>
.bots-page { max-width: 1250px; margin: 0 auto; padding: 30px 35px 50px; }
.bot-layout { display: grid; grid-template-columns: 280px minmax(0, 1fr); align-items: start; gap: 25px; }
.bot-card { background: var(--surface); padding: 22px; border: 1px solid var(--border); border-radius: 9px; margin-bottom: 22px; }
.bot-card header { border-bottom: 1px solid var(--border); padding-bottom: 15px; margin-bottom: 20px; }
.bot-card h2 { font-size: 17px; margin-bottom: 12px; overflow-wrap: anywhere; }
.bot-card p { color: var(--muted); font-size: 12px; line-height: 1.7; margin-bottom: 0; }
.bot-card .hint { margin-top: 17px; font-size: 11px; }
.bot-sidebar nav { display: flex; flex-direction: column; gap: 7px; }
.bot-sidebar nav button { justify-content: space-between; text-align: left; padding: 13px; gap: 8px; }
.bot-sidebar nav button[aria-pressed="true"] { border-color: var(--accent); background: var(--accent-soft); }
.bot-sidebar nav button > .avatar { flex-shrink: 0; }
.bot-identity { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.bot-picture-row { display: flex; align-items: center; gap: 18px; }
.bot-picture { width: 72px; height: 72px; font-size: 28px; flex-shrink: 0; }
.bot-sidebar small { display: block; font-size: 10px; color: var(--muted); margin-top: 6px; }
.bot-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.bot-project-form > button { font-size: 12px; }
.bot-project-list { list-style: none; padding: 0; margin: 20px 0 0; }
.bot-project-list li { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; border-top: 1px solid var(--border); padding: 12px 0; font-size: 12px; }
.bot-project-list li > span { color: var(--muted); font-size: 10px; }
.bot-project-list button { margin-left: auto; font-size: 10px; padding: 5px 8px; min-height: 27px; }
.bot-details { min-width: 0; }
.bot-details :deep(.token-manager) { margin-top: 0; }
@media(max-width: 800px) { .bots-page { padding: 24px 16px; } .bot-layout { grid-template-columns: 1fr; gap: 22px; } .bot-card { padding: 19px; } }
</style>
