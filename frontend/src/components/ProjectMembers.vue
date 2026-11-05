<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import type { Project, User } from '../types'
import UserAvatar from './UserAvatar.vue'

interface Member {
  user_id: string; name: string; email: string; role: string; avatar_url: string | null
  organization_role: User['role']; active: boolean; is_bot: boolean
}
const props = defineProps<{ project: Project; embedded?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const members = ref<Member[]>([]), users = ref<User[]>([])
const drafts = ref<Record<string, string>>({})
const loading = ref(true), loaded = ref(false), busy = ref(false), error = ref(''), message = ref('')
const memberId = ref(''), memberRole = ref('member')
const available = computed(() => users.value.filter(u => u.role && !members.value.some(m => m.user_id === u.id)))
const selected = computed(() => available.value.find(u => u.id === memberId.value))
const path = `/projects/${props.project.id}/members`

async function load() {
  const [current, candidates] = await Promise.all([api<Member[]>(path), api<User[]>('/users')])
  members.value = current; users.value = candidates
  drafts.value = Object.fromEntries(current.map(m => [m.user_id, m.role]))
  loaded.value = true
}
onMounted(async () => {
  try { await load() } catch (e) { error.value = (e as Error).message }
  finally { loading.value = false }
})
async function save(userId: string, role: string, adding = false) {
  busy.value = true; error.value = ''; message.value = ''
  try {
    await api(path, { method: 'PUT', body: JSON.stringify({ user_id: userId, role }) })
    await load()
    if (adding) { memberId.value = ''; memberRole.value = 'member' }
    message.value = adding ? 'Member added.' : 'Permissions updated.'
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function remove(member: Member) {
  busy.value = true; error.value = ''; message.value = ''
  try {
    await api(`${path}/${member.user_id}`, { method: 'DELETE' })
    await load()
    message.value = `${member.name} removed from project membership.`
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
</script>

<template>
  <div :class="{ 'modal-backdrop': !embedded }" @click.self="!embedded && !busy && emit('close')" @keydown.esc.stop="!embedded && !busy && emit('close')">
    <section :class="embedded ? 'embedded-members' : 'modal members-modal'" :role="embedded ? undefined : 'dialog'" :aria-modal="embedded ? undefined : true" aria-labelledby="members-heading" :aria-busy="loading || busy">
      <header><div><h2 id="members-heading">Project members</h2><p v-if="!embedded" class="hint">{{ project.name }}</p></div><button v-if="!embedded" type="button" class="quiet" :disabled="busy" aria-label="Close" @click="emit('close')">×</button></header>
      <p class="hint">Manage explicit project memberships. Member allows reading and writing; Reader is read-only. Organization readers remain read-only, and organization administrators always retain full access.</p>
      <p v-if="project.visibility === 'organization'" class="hint">This project is visible to the organization. Removing a human member restores their default organization access; it does not block access. Bots always require explicit membership.</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="message" class="hint" role="status">{{ message }}</p>
      <p v-if="loading" class="hint">Loading members…</p>
      <template v-else-if="loaded">
        <h3>Current members ({{ members.length }})</h3>
        <ul v-if="members.length" class="members-list">
          <li v-for="member in members" :key="member.user_id" class="member-row">
            <UserAvatar :name="member.name" :src="member.avatar_url" />
            <div class="member-identity"><strong>{{ member.name }}</strong> <span v-if="member.is_bot" class="bot-badge">Bot</span><small>{{ member.email || 'Bot account' }}</small><small v-if="!member.active || !member.organization_role">{{ !member.active ? 'Inactive account' : 'No organization membership' }}</small><small v-else>Organization role: {{ member.organization_role }}</small></div>
            <select v-model="drafts[member.user_id]" :aria-label="`Project role for ${member.name}`" :disabled="busy || !member.active || !member.organization_role">
              <option value="member" :disabled="member.is_bot && member.organization_role === 'reader'">Member</option><option value="reader">Reader</option><option v-if="member.role === 'administrator'" value="administrator">Administrator (legacy)</option>
            </select>
            <button type="button" :aria-label="`Save permissions for ${member.name}`" :disabled="busy || !member.active || !member.organization_role || drafts[member.user_id] === member.role" @click="save(member.user_id, drafts[member.user_id]!)">Save</button>
            <button type="button" :aria-label="`Remove ${member.name}`" :disabled="busy" @click="remove(member)">Remove</button>
          </li>
        </ul>
        <p v-else class="hint">No explicit project members yet.</p>
        <form class="add-member" @submit.prevent="save(memberId, memberRole, true)">
          <h3>Add a member</h3>
          <label>Member<select v-model="memberId" required :disabled="busy || !available.length" @change="memberRole = selected?.is_bot && selected.role === 'reader' ? 'reader' : 'member'"><option value="" disabled>Select a member</option><option v-for="user in available" :key="user.id" :value="user.id">{{ user.name }}{{ user.is_bot ? ' (bot)' : ' — ' + user.email }}</option></select></label>
          <label>Project role<select v-model="memberRole" :disabled="busy"><option value="member" :disabled="selected?.is_bot && selected.role === 'reader'">Member</option><option value="reader">Reader</option></select></label>
          <p v-if="selected?.is_bot && selected.role === 'reader'" class="hint">This bot has a read-only account. Select Reader to grant access.</p>
          <p v-if="!available.length" class="hint">All active organization members have already been added.</p>
          <button class="primary" :disabled="busy || !memberId || (selected?.is_bot && selected.role === 'reader' && memberRole !== 'reader')">Add member</button>
        </form>
      </template>
      <footer v-if="!embedded"><button type="button" :disabled="busy" @click="emit('close')">Done</button></footer>
    </section>
  </div>
</template>

<style scoped>
.members-modal { width: 780px; max-width: 100%; }
.members-modal header { align-items: flex-start; }
.members-modal header h2 { margin-bottom: 4px; }
.members-list { list-style: none; padding: 0; margin: 0 0 24px; }
.member-row { display: flex; align-items: center; gap: 10px; padding: 14px 0; border-bottom: 1px solid var(--border); }
.member-identity { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.member-row > .avatar { flex-shrink: 0; }
.member-identity small { display: block; color: var(--muted); margin-top: 4px; }
.member-row select { width: 145px; }
.add-member { border-top: 1px solid var(--border); padding-top: 20px; }
@media (max-width: 600px) {
  .member-row { flex-wrap: wrap; }
  .member-identity { flex-basis: calc(100% - 50px); }
  .member-row select { flex: 1; }
}
</style>
