<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, refreshAuth } from '../api'
import UserAvatar from './UserAvatar.vue'
import SettingsDetailPanel from './SettingsDetailPanel.vue'
import { dateTime, t } from '../i18n'

const props = defineProps<{ panelId?: string }>()
const emit = defineEmits<{ open: [id: string]; close: [] }>()

interface ApplicationUser {
  id: string; name: string; email: string; role: 'administrator' | 'member' | null
  active: boolean; avatar_url: string | null; last_login_at: string | null
  login_method: string; login_email: string | null; password_set: boolean; mail_status: string | null
}
const users = ref<ApplicationUser[]>([]), search = ref(''), loading = ref(false), error = ref('')
const selected = computed(() => users.value.find(user => user.id === props.panelId))
const role = ref('member'), active = ref(true), busy = ref(false)
const loginEmail = ref(''), newName = ref(''), newEmail = ref(''), newRole = ref('member'), passwordEnabled = ref(false), success = ref('')
watch(selected, user => { role.value = user?.role || 'member'; active.value = user?.active ?? true; loginEmail.value = user?.login_email || '' })
const filteredUsers = computed(() => {
  const term = search.value.trim().toLowerCase()
  return users.value.filter(user => `${user.name} ${user.email} ${t(user.role === 'administrator' ? 'Admin' : user.role ? 'Member' : 'Pending')}`.toLowerCase().includes(term))
})
function lastLogin(value: string | null) {
   return value ? dateTime(value) : t('Not recorded')
}
async function load() {
  loading.value = true; error.value = ''
  try { users.value = await api<ApplicationUser[]>('/admin/users') }
  catch (e) { error.value = (e as Error).message }
  finally { loading.value = false }
}
onMounted(async () => {
  await load()
  try { passwordEnabled.value = (await api<{ id: string }[]>('/auth/providers')).some(p => p.id === 'password') }
  catch (e) { error.value = (e as Error).message }
})
async function createUser() {
  busy.value = true; error.value = ''; success.value = ''
  try {
    const result = await api<{ id: string }>('/admin/users', { method: 'POST', body: JSON.stringify({ name: newName.value, email: newEmail.value, role: newRole.value }) })
    newName.value = ''; newEmail.value = ''; await load(); emit('open', result.id)
    success.value = 'Account created. A password invitation has been queued.'
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function passwordAction(action: 'invite' | 'reset' | 'email') {
  if (!selected.value) return
  if (action !== 'invite' && !window.confirm(t('This will invalidate the password and sign out all browser sessions. Continue?'))) return
  busy.value = true; error.value = ''; success.value = ''
  try {
    const path = action === 'email' ? 'login-email' : `password/${action}`
    await api(`/admin/users/${selected.value.id}/${path}`, { method: action === 'email' ? 'PUT' : 'POST', ...(action === 'email' ? { body: JSON.stringify({ email: loginEmail.value }) } : {}) })
    success.value = 'A new password link has been queued. Previous links are no longer valid.'
    await refreshAuth(); await load()
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
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
  <section class="application-users" :aria-label="t('Application users')">
    <header class="users-heading"><div><h2>{{ t('Users') }}</h2><p class="hint">{{ t('All user accounts, including inactive accounts and users awaiting membership. Automation accounts are managed in Bots.') }}</p></div><PButton v-if="passwordEnabled" @click="emit('open', 'new')">{{ t('Create user') }}</PButton><PButton type="button" severity="secondary" outlined :disabled="loading" @click="load">{{ t('Refresh') }}</PButton></header>
    <InputText v-model="search" type="search" class="user-search" :placeholder="t('Search users…')" :aria-label="t('Search users')" />
    <PMessage v-if="error && !panelId" severity="error">{{ t(error) }}</PMessage>
    <PMessage v-if="success && !panelId" severity="success">{{ t(success) }}</PMessage>
    <DataTable :value="filteredUsers" data-key="id" :loading="loading" paginator :rows="25" :rows-per-page-options="[25, 50, 100]" sort-field="name" :sort-order="1" scrollable table-style="min-width: 720px" :aria-label="t('User accounts')">
      <PColumn field="name" :header="t('Name')" sortable><template #body="{ data }"><span class="user-identity"><UserAvatar :name="data.name" :src="data.avatar_url" /><span>{{ data.name }}</span></span></template></PColumn>
      <PColumn field="email" :header="t('Email')" sortable />
      <PColumn field="role" :header="t('Application role')" sortable><template #body="{ data }"><PTag :value="t(data.role === 'administrator' ? 'Admin' : data.role ? 'Member' : 'Pending')" :severity="data.role === 'administrator' ? 'success' : 'secondary'" /></template></PColumn>
      <PColumn field="last_login_at" :header="t('Last sign-in')" sortable><template #body="{ data }"><time v-if="data.last_login_at" :datetime="data.last_login_at">{{ lastLogin(data.last_login_at) }}</time><span v-else class="muted">{{ t('Not recorded') }}</span></template></PColumn>
      <PColumn field="active" :header="t('Status')" sortable><template #body="{ data }"><PTag :value="t(!data.active ? 'Disabled' : !data.role ? 'Pending membership' : 'Active')" :severity="!data.active ? 'danger' : !data.role ? 'warn' : 'secondary'" /></template></PColumn>
      <PColumn :header="t('Actions')"><template #body="{ data }"><PButton type="button" severity="secondary" outlined :aria-label="t('View user {name}', { name: data.name })" @click="emit('open', data.id)">{{ t('Details') }}</PButton></template></PColumn>
      <template #empty>{{ t('No users found.') }}</template>
    </DataTable>
    <SettingsDetailPanel v-if="panelId" :title="selected?.name || t('User details')" @close="emit('close')">
      <PMessage v-if="error" severity="error">{{ t(error) }}</PMessage>
      <PMessage v-if="success" severity="success">{{ t(success) }}</PMessage>
      <form v-if="panelId === 'new' && passwordEnabled" @submit.prevent="createUser">
        <h2>{{ t('Create local account') }}</h2>
        <label>{{ t('Display name') }}<InputText v-model="newName" required maxlength="200" :disabled="busy" /></label>
        <label>{{ t('Sign-in email') }}<InputText v-model="newEmail" type="email" required maxlength="320" :disabled="busy" /></label>
        <label>{{ t('Application role') }}<PSelect v-model="newRole" :options="[{ label: t('Admin'), value: 'administrator' }, { label: t('Member'), value: 'member' }]" option-label="label" option-value="value" :disabled="busy" /></label>
        <PButton type="submit" :loading="busy" :disabled="busy">{{ t('Create and send invitation') }}</PButton>
      </form>
      <p v-else-if="loading" class="hint">{{ t('Loading user…') }}</p>
      <PMessage v-else-if="!selected" severity="error">{{ t('User not found.') }}</PMessage>
      <template v-else>
        <div class="user-identity"><UserAvatar :name="selected.name" :src="selected.avatar_url" /><h2>{{ selected.name }}</h2></div>
        <dl class="user-properties">
          <dt>{{ t('Email') }}</dt><dd>{{ selected.email || t('Not set') }}</dd>
          <dt>{{ t('Application role') }}</dt><dd>{{ t(selected.role === 'administrator' ? 'Admin' : selected.role ? 'Member' : 'Pending membership') }}</dd>
          <dt>{{ t('Status') }}</dt><dd>{{ t(selected.active ? 'Active' : 'Disabled') }}</dd>
          <dt>{{ t('Last sign-in') }}</dt><dd>{{ lastLogin(selected.last_login_at) }}</dd>
          <dt>{{ t('User ID') }}</dt><dd>{{ selected.id }}</dd>
          <dt>{{ t('Sign-in method') }}</dt><dd>{{ t(selected.login_method) }}</dd>
          <template v-if="selected.login_email"><dt>{{ t('Sign-in email') }}</dt><dd>{{ selected.login_email }}</dd><dt>{{ t('Password') }}</dt><dd>{{ t(selected.password_set ? 'Set' : 'Awaiting setup') }}</dd><dt>{{ t('Latest email') }}</dt><dd>{{ t(selected.mail_status || 'Not sent') }}</dd></template>
        </dl>
        <form @submit.prevent="save">
          <label>{{ t('Application role') }}<PSelect v-model="role" :options="[{ label: t('Admin'), value: 'administrator' }, { label: t('Member'), value: 'member' }]" option-label="label" option-value="value" :aria-label="t('Application role')" :disabled="busy" /></label>
          <label>{{ t('Status') }}<SelectButton v-model="active" :options="[{ label: t('Active'), value: true }, { label: t('Disabled'), value: false }]" option-label="label" option-value="value" :allow-empty="false" :aria-label="t('Account status')" :disabled="busy" /></label>
          <PButton type="submit" :disabled="busy" :loading="busy">{{ t('Save permissions') }}</PButton>
        </form>
        <section v-if="selected.login_method === 'password' && passwordEnabled">
          <h3>{{ t('Password management') }}</h3>
          <PButton v-if="!selected.password_set" :disabled="busy || !selected.active" @click="passwordAction('invite')">{{ t('Resend setup email') }}</PButton>
          <PButton severity="danger" outlined :disabled="busy || !selected.active" @click="passwordAction('reset')">{{ t('Reset password') }}</PButton>
          <form @submit.prevent="passwordAction('email')"><label>{{ t('Sign-in email') }}<InputText v-model="loginEmail" type="email" required maxlength="320" :disabled="busy" /></label><PButton type="submit" :disabled="busy || !selected.active || loginEmail === selected.login_email">{{ t('Change email and reset password') }}</PButton></form>
        </section>
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
