<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, refreshAuth } from '../api'
import UserAvatar from './UserAvatar.vue'
import SettingsDetailPanel from './SettingsDetailPanel.vue'

const props = defineProps<{ panelId?: string }>()
const emit = defineEmits<{ open: [id: string]; close: [] }>()

interface ApplicationUser {
  id: string; name: string; email: string; role: 'administrator' | 'member' | null
  active: boolean; avatar_url: string | null; last_login_at: string | null
}
const users = ref<ApplicationUser[]>([]), search = ref(''), loading = ref(false), error = ref('')
const selected = computed(() => users.value.find(user => user.id === props.panelId))
const role = ref('member'), active = ref(true), busy = ref(false)
watch(selected, user => { role.value = user?.role || 'member'; active.value = user?.active ?? true })
const filteredUsers = computed(() => {
  const term = search.value.trim().toLowerCase()
  return users.value.filter(user => `${user.name} ${user.email} ${user.role === 'administrator' ? 'Admin' : user.role ? 'Member' : 'Pending'}`.toLowerCase().includes(term))
})
function lastLogin(value: string | null) {
  return value ? new Date(value).toLocaleString() : 'Not recorded'
}
async function load() {
  loading.value = true; error.value = ''
  try { users.value = await api<ApplicationUser[]>('/admin/users') }
  catch (e) { error.value = (e as Error).message }
  finally { loading.value = false }
}
onMounted(load)
async function save() {
  if (!selected.value) return
  busy.value = true; error.value = ''
  try {
    await api(`/admin/users/${selected.value.id}`, { method: 'PUT', body: JSON.stringify({ role: role.value, active: active.value }) })
    await refreshAuth()
    await load()
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
</script>

<template>
  <section class="application-users" aria-label="Application users">
    <header class="users-heading"><div><h2>Users</h2><p class="hint">All user accounts, including inactive accounts and users awaiting membership. Automation accounts are managed in Bots.</p></div><PButton type="button" severity="secondary" outlined :disabled="loading" @click="load">Refresh</PButton></header>
    <InputText v-model="search" type="search" class="user-search" placeholder="Search users…" aria-label="Search users" />
    <PMessage v-if="error" severity="error">{{ error }}</PMessage>
    <DataTable :value="filteredUsers" data-key="id" :loading="loading" paginator :rows="25" :rows-per-page-options="[25, 50, 100]" sort-field="name" :sort-order="1" scrollable table-style="min-width: 720px" aria-label="User accounts">
      <PColumn field="name" header="Name" sortable><template #body="{ data }"><span class="user-identity"><UserAvatar :name="data.name" :src="data.avatar_url" /><span>{{ data.name }}</span></span></template></PColumn>
      <PColumn field="email" header="Email" sortable />
      <PColumn field="role" header="Application role" sortable><template #body="{ data }"><PTag :value="data.role === 'administrator' ? 'Admin' : data.role ? 'Member' : 'Pending'" :severity="data.role === 'administrator' ? 'success' : 'secondary'" /></template></PColumn>
      <PColumn field="last_login_at" header="Last sign-in" sortable><template #body="{ data }"><time v-if="data.last_login_at" :datetime="data.last_login_at">{{ lastLogin(data.last_login_at) }}</time><span v-else class="muted">Not recorded</span></template></PColumn>
      <PColumn field="active" header="Status" sortable><template #body="{ data }"><PTag :value="!data.active ? 'Disabled' : !data.role ? 'Pending membership' : 'Active'" :severity="!data.active ? 'danger' : !data.role ? 'warn' : 'secondary'" /></template></PColumn>
      <PColumn header="Actions"><template #body="{ data }"><PButton type="button" severity="secondary" outlined :aria-label="`View user ${data.name}`" @click="emit('open', data.id)">Details</PButton></template></PColumn>
      <template #empty>No users found.</template>
    </DataTable>
    <SettingsDetailPanel v-if="panelId" :title="selected?.name || 'User details'" @close="emit('close')">
      <p v-if="loading" class="hint">Loading user…</p>
      <PMessage v-else-if="!selected" severity="error">User not found.</PMessage>
      <template v-else>
        <div class="user-identity"><UserAvatar :name="selected.name" :src="selected.avatar_url" /><h2>{{ selected.name }}</h2></div>
        <dl class="user-properties">
          <dt>Email</dt><dd>{{ selected.email || 'Not set' }}</dd>
          <dt>Application role</dt><dd>{{ selected.role === 'administrator' ? 'Admin' : selected.role ? 'Member' : 'Pending membership' }}</dd>
          <dt>Status</dt><dd>{{ selected.active ? 'Active' : 'Disabled' }}</dd>
          <dt>Last sign-in</dt><dd>{{ lastLogin(selected.last_login_at) }}</dd>
          <dt>User ID</dt><dd>{{ selected.id }}</dd>
        </dl>
        <form @submit.prevent="save">
          <label>Application role<PSelect v-model="role" :options="[{ label: 'Admin', value: 'administrator' }, { label: 'Member', value: 'member' }]" option-label="label" option-value="value" aria-label="Application role" :disabled="busy" /></label>
          <label>Status<SelectButton v-model="active" :options="[{ label: 'Active', value: true }, { label: 'Disabled', value: false }]" option-label="label" option-value="value" :allow-empty="false" aria-label="Account status" :disabled="busy" /></label>
          <PButton type="submit" :disabled="busy" :loading="busy">Save permissions</PButton>
        </form>
      </template>
    </SettingsDetailPanel>
  </section>
</template>

<style scoped>
.application-users { min-width: 0; }
.users-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.users-heading h2 { margin-bottom: 8px; }
.user-search { max-width: 360px; margin-bottom: 16px; }
.user-identity { display: flex; align-items: center; gap: 8px; }
.user-identity > .avatar { flex-shrink: 0; }
.user-identity h2 { margin: 0; }
.user-properties { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 14px; margin-top: 24px; }
.user-properties dt { color: var(--muted); }
.user-properties dd { margin: 0; overflow-wrap: anywhere; }
@media (max-width: 540px) { .user-properties { grid-template-columns: minmax(0, 1fr); gap: 8px; } .user-properties dd { margin-bottom: 12px; } }
</style>
