<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import UserAvatar from './UserAvatar.vue'

interface ApplicationUser {
  id: string; name: string; email: string; role: 'administrator' | 'member' | 'reader' | null
  active: boolean; avatar_url: string | null; last_login_at: string | null
}
const users = ref<ApplicationUser[]>([]), search = ref(''), loading = ref(false), error = ref('')
const filteredUsers = computed(() => {
  const term = search.value.trim().toLowerCase()
  return users.value.filter(user => `${user.name} ${user.email} ${user.role === 'administrator' ? 'Admin' : 'User'}`.toLowerCase().includes(term))
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
</script>

<template>
  <section class="application-users" aria-label="Application users">
    <header class="users-heading"><div><h2>Users</h2><p class="hint">All user accounts, including inactive accounts and users awaiting membership. Automation accounts are managed in Bots.</p></div><PButton type="button" severity="secondary" outlined :disabled="loading" @click="load">Refresh</PButton></header>
    <InputText v-model="search" type="search" class="user-search" placeholder="Search users…" aria-label="Search users" />
    <PMessage v-if="error" severity="error">{{ error }}</PMessage>
    <DataTable :value="filteredUsers" data-key="id" :loading="loading" paginator :rows="25" :rows-per-page-options="[25, 50, 100]" sort-field="name" :sort-order="1" scrollable table-style="min-width: 720px" aria-label="User accounts">
      <PColumn field="name" header="Name" sortable><template #body="{ data }"><span class="user-identity"><UserAvatar :name="data.name" :src="data.avatar_url" /><span>{{ data.name }}</span></span></template></PColumn>
      <PColumn field="email" header="Email" sortable />
      <PColumn field="role" header="Application role" sortable><template #body="{ data }"><PTag :value="data.role === 'administrator' ? 'Admin' : 'User'" :severity="data.role === 'administrator' ? 'success' : 'secondary'" /></template></PColumn>
      <PColumn field="last_login_at" header="Last sign-in" sortable><template #body="{ data }"><time v-if="data.last_login_at" :datetime="data.last_login_at">{{ lastLogin(data.last_login_at) }}</time><span v-else class="muted">Not recorded</span></template></PColumn>
      <PColumn field="active" header="Status" sortable><template #body="{ data }"><PTag :value="!data.active ? 'Disabled' : !data.role ? 'Pending membership' : 'Active'" :severity="!data.active ? 'danger' : !data.role ? 'warn' : 'secondary'" /></template></PColumn>
      <template #empty>No users found.</template>
    </DataTable>
  </section>
</template>

<style scoped>
.application-users { min-width: 0; }
.users-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.users-heading h2 { margin-bottom: 8px; }
.user-search { max-width: 360px; margin-bottom: 16px; }
.user-identity { display: flex; align-items: center; gap: 8px; }
.user-identity > .avatar { flex-shrink: 0; }
</style>
