<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, auth } from '../api'
import type { Project, User } from '../types'
import UserAvatar from './UserAvatar.vue'

interface Member {
  user_id: string; name: string; email: string; role: string; avatar_url: string | null
  organization_role: User['role']; active: boolean; is_bot: boolean
}
const props = defineProps<{ project: Project; embedded?: boolean }>()
const emit = defineEmits<{ close: []; updated: [] }>()
const members = ref<Member[]>([]), users = ref<User[]>([])
const drafts = ref<Record<string, string>>({})
const loading = ref(true), loaded = ref(false), busy = ref(false), error = ref(''), message = ref('')
const memberId = ref(''), memberRole = ref('member')
const showAddMember = ref(false)
const available = computed(() => users.value.filter(u => u.role && !members.value.some(m => m.user_id === u.id)))
const selected = computed(() => available.value.find(u => u.id === memberId.value))
const path = `/projects/${props.project.id}/members`
function roleOptions(isBot = false, organizationRole: User['role'] = null) {
  return [
    { label: 'Admin', value: 'administrator', disabled: isBot || organizationRole === 'reader' },
    { label: 'Member', value: 'member', disabled: isBot && organizationRole === 'reader' },
    { label: 'Reader', value: 'reader', disabled: false },
  ]
}

async function load() {
  const [current, candidates] = await Promise.all([api<Member[]>(path), api<User[]>(`/projects/${props.project.id}/member-candidates`)])
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
    emit('updated')
    if (userId === auth.user?.id && auth.user.role !== 'administrator' && role !== 'administrator') return
    await load()
    if (adding) { memberId.value = ''; memberRole.value = 'member'; showAddMember.value = false }
    message.value = adding ? 'Member added.' : 'Permissions updated.'
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function remove(member: Member) {
  busy.value = true; error.value = ''; message.value = ''
  try {
    await api(`${path}/${member.user_id}`, { method: 'DELETE' })
    emit('updated')
    if (member.user_id === auth.user?.id && auth.user.role !== 'administrator') return
    await load()
    message.value = `${member.name} removed from project membership.`
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
</script>

<template>
  <div :class="{ 'modal-backdrop': !embedded }" @click.self="!embedded && !busy && emit('close')" @keydown.esc.stop="!embedded && !busy && emit('close')">
    <section :class="embedded ? 'embedded-members' : 'modal members-modal'" :role="embedded ? undefined : 'dialog'" :aria-modal="embedded ? undefined : true" aria-labelledby="members-heading" :aria-busy="loading || busy">
      <header><div><h2 id="members-heading">Project members</h2><p v-if="!embedded" class="hint">{{ project.name }}</p></div><PButton v-if="!embedded" type="button" class="quiet" :disabled="busy" aria-label="Close" @click="emit('close')">×</PButton></header>
      <p class="hint">Admin manages project settings, members, and project labels. Member can contribute to work items but cannot configure the project. Reader is read-only. Organization readers remain read-only, and organization administrators always retain full access.</p>
      <p v-if="project.visibility === 'organization'" class="hint">This project is visible to the organization. Removing a human member restores their default organization access; it does not block access. Bots always require explicit membership.</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="message" class="hint" role="status">{{ message }}</p>
      <p v-if="loading" class="hint">Loading members…</p>
      <template v-else-if="loaded">
        <PButton v-if="!showAddMember" type="button" class="add-member-toggle" :disabled="busy || !available.length" :aria-expanded="false" @click="showAddMember = true">Add member</PButton>
        <form v-else class="add-member" @submit.prevent="save(memberId, memberRole, true)">
          <h3>Add a member</h3>
          <div class="add-member-fields">
            <label>Member<PSelect v-model="memberId" :options="available.map(user => ({ value: user.id, label: user.name + (user.is_bot ? ' (bot)' : ' — ' + user.email) }))" option-label="label" option-value="value" filter placeholder="Select a member" aria-label="Member" :disabled="busy || !available.length" @change="memberRole = selected?.is_bot && selected.role === 'reader' ? 'reader' : 'member'" /></label>
            <label>Project role<SelectButton v-model="memberRole" :options="roleOptions(selected?.is_bot, selected?.role)" option-label="label" option-value="value" option-disabled="disabled" :allow-empty="false" size="small" aria-label="Project role" :disabled="busy" /></label>
            <PButton type="submit" :disabled="busy || !memberId || (selected?.is_bot && selected.role === 'reader' && memberRole !== 'reader')">Add member</PButton>
          </div>
          <PButton type="button" class="quiet" :disabled="busy" @click="showAddMember = false">Cancel</PButton>
          <p v-if="selected?.is_bot && selected.role === 'reader'" class="hint">This bot has a read-only account. Select Reader to grant access.</p>
          <p v-if="!available.length" class="hint">All active organization members have already been added.</p>
        </form>
        <h3>Current members ({{ members.length }})</h3>
        <ul v-if="members.length" class="members-list">
          <li v-for="member in members" :key="member.user_id" class="member-row">
            <UserAvatar :name="member.name" :src="member.avatar_url" />
            <div class="member-identity"><strong>{{ member.name }}</strong> <span v-if="member.is_bot" class="bot-badge">Bot</span><small>{{ member.email || 'Bot account' }}</small><small v-if="!member.active || !member.organization_role">{{ !member.active ? 'Inactive account' : 'No organization membership' }}</small><small v-else>Organization role: {{ member.organization_role }}</small></div>
            <SelectButton v-model="drafts[member.user_id]" :options="roleOptions(member.is_bot, member.organization_role)" option-label="label" option-value="value" option-disabled="disabled" :allow-empty="false" size="small" :aria-label="`Project role for ${member.name}`" :disabled="busy || !member.active || !member.organization_role" />
            <PButton type="button" :aria-label="`Save permissions for ${member.name}`" :disabled="busy || !member.active || !member.organization_role || drafts[member.user_id] === member.role" @click="save(member.user_id, drafts[member.user_id]!)">Save</PButton>
            <PButton type="button" severity="secondary" outlined :aria-label="`Remove ${member.name}`" :disabled="busy" @click="remove(member)">Remove</PButton>
          </li>
        </ul>
        <p v-else class="hint">No explicit project members yet.</p>
      </template>
      <footer v-if="!embedded"><PButton type="button" :disabled="busy" @click="emit('close')">Done</PButton></footer>
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
.member-row > .p-selectbutton { flex-shrink: 0; }
.add-member { border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 20px; }
.add-member-toggle { margin-bottom: 20px; }
.add-member h3 { margin-bottom: 10px; }
.add-member-fields { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: end; gap: 10px; }
.add-member-fields label { min-width: 0; margin-bottom: 0; gap: 5px; font-size: 12px; }
.add-member > .hint { margin: 8px 0 0; }
@media (max-width: 600px) {
  .member-row { flex-wrap: wrap; }
  .member-identity { flex-basis: calc(100% - 50px); }
  .member-row > .p-selectbutton { flex-basis: 100%; }
  .add-member-fields { grid-template-columns: minmax(0, 1fr); }
  .add-member-fields > .p-button { justify-self: start; }
}
</style>
