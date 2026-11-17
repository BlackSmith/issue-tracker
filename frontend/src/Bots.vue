<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, auth } from './api'
import type { BotAccount, BotProject, Project } from './types'
import TokenManager from './components/TokenManager.vue'
import UserAvatar from './components/UserAvatar.vue'
import SettingsDetailPanel from './components/SettingsDetailPanel.vue'

const props = defineProps<{ embedded?: boolean; panelId?: string }>()
const emit = defineEmits<{ open: [id: string, replace?: boolean]; close: [] }>()

const bots = ref<BotAccount[]>([]), projects = ref<Project[]>([]), memberships = ref<BotProject[]>([])
const selectedId = computed(() => props.panelId === 'new' ? '' : props.panelId || '')
const error = ref(''), loading = ref(false), busy = ref(false), search = ref('')
const createName = ref(''), editName = ref('')
const projectId = ref(''), projectRole = ref('read-only')
const avatarInput = ref<HTMLInputElement | null>(null)
const selected = computed(() => bots.value.find(bot => bot.id === selectedId.value))
const filteredBots = computed(() => bots.value.filter(bot => bot.name.toLowerCase().includes(search.value.trim().toLowerCase())))
let loadSequence = 0

async function load() {
  if (auth.user?.role !== 'administrator') return
  loading.value = true; error.value = ''
  try {
    const [accounts, available] = await Promise.all([api<BotAccount[]>('/bots'), api<Project[]>('/projects')])
    bots.value = accounts; projects.value = available
  } catch (e) { error.value = (e as Error).message }
  finally { loading.value = false }
}
async function loadProjects() {
  const id = selected.value?.id, sequence = ++loadSequence
  memberships.value = []
  if (!id) return
  try {
    const result = await api<BotProject[]>(`/bots/${id}/projects`)
    if (sequence === loadSequence && id === selectedId.value) memberships.value = result
  } catch (e) { if (sequence === loadSequence) error.value = (e as Error).message }
}
watch(selected, bot => {
  editName.value = bot?.name || ''
  projectId.value = ''; projectRole.value = 'read-only'
})
watch(() => selected.value?.id, loadProjects, { immediate: true })
watch(() => props.panelId, id => {
  error.value = ''
  if (id === 'new') createName.value = ''
})
void load()

async function create() {
  busy.value = true; error.value = ''
  try {
    const account = await api<BotAccount>('/bots', { method: 'POST', body: JSON.stringify({ name: createName.value }) })
    bots.value = [...bots.value, account]; createName.value = ''; emit('open', account.id, true)
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function update(active = selected.value?.active) {
  if (!selected.value) return
  busy.value = true; error.value = ''
  try {
    const value = await api<BotAccount>(`/bots/${selected.value.id}`, { method: 'PUT', body: JSON.stringify({ name: editName.value, active }) })
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
  <component :is="embedded ? 'section' : 'main'" class="bots-page" :class="{ 'bots-embedded': embedded }">
    <div v-if="!embedded" class="breadcrumbs"><RouterLink to="/">Workspace</RouterLink><span>/</span> Bot accounts</div>
    <p v-if="auth.user?.role !== 'administrator'" class="error" role="alert">Administrator access is required.</p>
    <template v-else>
      <header class="page-heading"><div><h2>Bot accounts</h2><p>Give automations and AI tools their own identity and project access.</p></div><PButton type="button" :disabled="busy" @click="emit('open', 'new')">Create bot</PButton></header>
      <PMessage v-if="error && !panelId" severity="error">{{ error }}</PMessage>
      <InputText v-model="search" type="search" class="bot-search" placeholder="Search bots…" aria-label="Search bots" />
      <DataTable :value="filteredBots" data-key="id" :loading="loading" paginator :rows="25" sort-field="name" :sort-order="1" scrollable table-style="min-width: 480px" aria-label="Bot accounts">
        <PColumn field="name" header="Name" sortable><template #body="{ data }"><span class="bot-identity"><UserAvatar :name="data.name" :src="data.avatar_url" /><span>{{ data.name }}</span></span></template></PColumn>
        <PColumn field="role" header="Application role"><template #body>Member</template></PColumn>
        <PColumn field="active" header="Status" sortable><template #body="{ data }"><PTag :value="data.active ? 'Active' : 'Disabled'" :severity="data.active ? 'success' : 'secondary'" /></template></PColumn>
        <PColumn header="Actions"><template #body="{ data }"><PButton type="button" severity="secondary" outlined :disabled="busy" :aria-label="`Edit bot ${data.name}`" @click="emit('open', data.id)">Edit</PButton></template></PColumn>
        <template #empty>No bots found.</template>
      </DataTable>
      <SettingsDetailPanel v-if="panelId" :key="panelId" :title="panelId === 'new' ? 'Create bot' : selected?.name || 'Bot details'" :busy="busy" @close="emit('close')">
        <PMessage v-if="error" severity="error">{{ error }}</PMessage>
        <form v-if="panelId === 'new'" aria-label="Create bot" @submit.prevent="create"><label>Bot name<InputText v-model="createName" required maxlength="200" placeholder="e.g. AI assistant" :disabled="busy" /></label><p class="hint">Bots are application members. Assign Reporter or Read-only access separately for each project.</p><div class="bot-actions"><PButton type="button" severity="secondary" outlined :disabled="busy" @click="emit('close')">Cancel</PButton><PButton type="submit" :loading="busy" :disabled="busy">Create bot</PButton></div></form>
        <p v-else-if="loading" class="hint">Loading bot…</p>
        <div v-else-if="selected" class="bot-details">
          <section class="bot-card bot-picture-card" aria-labelledby="bot-picture-heading">
            <h2 id="bot-picture-heading">Bot picture</h2>
            <div class="bot-picture-row">
              <UserAvatar class="bot-picture" :name="selected.name" :src="selected.avatar_url" />
              <div><div class="bot-actions"><PButton type="button" severity="secondary" outlined :disabled="busy" @click="avatarInput?.click()">Upload picture</PButton><PButton v-if="selected.avatar_url" type="button" severity="secondary" outlined :disabled="busy" @click="removeAvatar">Remove picture</PButton></div><p class="hint">PNG, JPEG, GIF or WebP · up to 5 MB. Cropped to a square and saved immediately.</p></div>
            </div>
            <input ref="avatarInput" type="file" accept="image/png,image/jpeg,image/gif,image/webp" aria-label="Bot picture" hidden :disabled="busy" @change="uploadAvatar" />
          </section>
          <section class="bot-card"><header><h2>{{ selected.name }} <span class="bot-badge">Bot</span></h2><p>API access only. Bots have no password or OIDC login.</p></header><form @submit.prevent="update()"><label>Display name<InputText v-model="editName" required maxlength="200" :disabled="busy" /></label><div class="bot-actions"><PButton type="submit" :disabled="busy">Save bot</PButton><PButton type="button" severity="secondary" outlined :disabled="busy" @click="update(!selected.active)">{{ selected.active ? 'Disable bot' : 'Enable bot' }}</PButton></div></form><p class="hint">Disabling a bot revokes all its tokens. Re-enabling requires a new token.</p></section>
          <section class="bot-card"><header><h2>Project access</h2><p>Bots can access only explicitly assigned projects.</p></header><form class="bot-project-form" @submit.prevent="grantProject"><label>Project<PSelect v-model="projectId" :options="projects.map(p => ({ value: p.id, label: `${p.name} (${p.key})` }))" option-label="label" option-value="value" filter placeholder="Select a project" aria-label="Project" :disabled="busy" /></label><label>Project permission<PSelect v-model="projectRole" :options="[{ label: 'Read-only', value: 'read-only' }, { label: 'Reporter', value: 'reporter' }]" option-label="label" option-value="value" aria-label="Project permission" :disabled="busy" /></label><PButton type="submit" :disabled="busy || !projectId">Grant / update access</PButton></form><ul class="bot-project-list"><li v-for="p in memberships" :key="p.project_id"><RouterLink :to="`/${p.slug}/`">{{ p.name }}</RouterLink><span>{{ p.effective_role === 'read-only' ? 'Read-only' : 'Reporter' }}</span><PButton type="button" severity="secondary" outlined :disabled="busy" @click="removeProject(p.project_id)">Remove</PButton></li></ul><p v-if="!memberships.length" class="hint">No projects assigned. This bot cannot read or change tickets yet.</p></section>
          <TokenManager :key="selected.id + ':' + selected.active" :base-path="`/bots/${selected.id}/tokens`" :owner-role="selected.role" :disabled="!selected.active" title="Bot API tokens" />
        </div>
        <PMessage v-else severity="error">Bot not found.</PMessage>
      </SettingsDetailPanel>
    </template>
  </component>
</template>

<style scoped>
.bots-page { max-width: 1250px; margin: 0 auto; padding: 30px 35px 50px; }
.bots-page.bots-embedded { max-width: none; padding: 0; }
.bot-search { max-width: 360px; margin-bottom: 16px; }
.bot-card { background: var(--surface); padding: 22px; border: 1px solid var(--border); border-radius: 9px; margin-bottom: 22px; }
.bot-card header { border-bottom: 1px solid var(--border); padding-bottom: 15px; margin-bottom: 20px; }
.bot-card h2 { font-size: 17px; margin-bottom: 12px; overflow-wrap: anywhere; }
.bot-card p { color: var(--muted); font-size: 12px; line-height: 1.7; margin-bottom: 0; }
.bot-card .hint { margin-top: 17px; font-size: 11px; }
.bot-identity { display: flex; align-items: center; gap: 8px; min-width: 0; overflow-wrap: anywhere; }
.bot-picture-row { display: flex; align-items: center; gap: 18px; }
.bot-picture { width: 72px; height: 72px; font-size: 28px; flex-shrink: 0; }
.bot-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.bot-project-form > button { font-size: 12px; }
.bot-project-list { list-style: none; padding: 0; margin: 20px 0 0; }
.bot-project-list li { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; border-top: 1px solid var(--border); padding: 12px 0; font-size: 12px; }
.bot-project-list li > span { color: var(--muted); font-size: 10px; }
.bot-project-list button { margin-left: auto; font-size: 10px; padding: 5px 8px; min-height: 27px; }
.bot-details { min-width: 0; }
.bot-details :deep(.token-manager) { margin-top: 0; }
@media(max-width: 800px) { .bots-page { padding: 24px 16px; } .bot-card { padding: 19px; } }
</style>
