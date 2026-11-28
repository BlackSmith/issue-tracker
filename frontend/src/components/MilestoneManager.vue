<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { dateOnly, t } from '../i18n'
import type { Milestone } from '../types'

const props = defineProps<{ projectId: string }>()
const emit = defineEmits<{ updated: [] }>()
const base = `/projects/${props.projectId}/milestones`
const milestones = ref<Milestone[]>([]), loading = ref(true), busy = ref(false)
const error = ref('')
const draft = ref<{ id: string; name: string; description: string; due_date: string } | null>(null)

async function load() {
  try { milestones.value = await api<Milestone[]>(base) }
  catch (e) { error.value = (e as Error).message }
  finally { loading.value = false }
}
onMounted(load)

function edit(milestone?: Milestone) {
  error.value = ''
  draft.value = milestone
    ? { id: milestone.id, name: milestone.name, description: milestone.description, due_date: milestone.due_date || '' }
    : { id: '', name: '', description: '', due_date: '' }
}

async function write(path: string, method: 'POST' | 'PUT', body: object) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    await api(path, { method, body: JSON.stringify(body) })
    draft.value = null
    await load()
    emit('updated')
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}

function save() {
  if (!draft.value || !draft.value.name.trim()) return
  const { id, name, description, due_date } = draft.value
  return write(id ? `${base}/${id}` : base, id ? 'PUT' : 'POST', { name, description, due_date: due_date || null })
}
</script>

<template>
  <section :aria-label="t('Milestones')">
    <p class="hint">{{ t('Only open milestones can be assigned. Closing a milestone keeps its existing ticket assignments.') }}</p>
    <PMessage v-if="error" severity="error">{{ t(error) }}</PMessage>
    <form v-if="draft" class="milestone-form" :aria-label="t(draft.id ? 'Edit milestone' : 'Add milestone')" @submit.prevent="save">
      <h3>{{ t(draft.id ? 'Edit milestone' : 'Add milestone') }}</h3>
      <label>{{ t('Name') }}<InputText v-model="draft.name" required maxlength="150" :disabled="busy" /></label>
      <label>{{ t('Target date') }}<InputText v-model="draft.due_date" type="date" :disabled="busy" /></label>
      <label>{{ t('Description') }}<PTextarea v-model="draft.description" rows="2" maxlength="2000" :disabled="busy" /></label>
      <footer>
        <PButton type="button" severity="secondary" outlined :disabled="busy" @click="draft = null; error = ''">{{ t('Cancel') }}</PButton>
        <PButton type="submit" :loading="busy" :disabled="busy || !draft.name.trim()">{{ t(draft.id ? 'Save changes' : 'Add milestone') }}</PButton>
      </footer>
    </form>
    <PButton v-else type="button" :disabled="busy || loading" @click="edit()">{{ t('Add milestone') }}</PButton>
    <p v-if="loading" class="hint">{{ t('Loading milestones…') }}</p>
    <ul v-else-if="milestones.length" class="milestone-list">
      <li v-for="milestone in milestones" :key="milestone.id">
        <div class="milestone-summary">
          <strong>{{ milestone.name }}</strong>
          <p class="muted">
            {{ t(milestone.closed ? 'Closed' : 'Open') }}
            <template v-if="milestone.due_date"> · {{ t('Target date') }}: <time :datetime="milestone.due_date">{{ dateOnly(milestone.due_date) }}</time></template>
          </p>
          <p v-if="milestone.description" class="milestone-description">{{ milestone.description }}</p>
        </div>
        <div class="milestone-actions">
          <PButton type="button" severity="secondary" outlined :disabled="busy || !!draft" :aria-label="t('Edit milestone {name}', { name: milestone.name })" @click="edit(milestone)">{{ t('Edit') }}</PButton>
          <PButton type="button" severity="secondary" outlined :disabled="busy || !!draft" :aria-label="t(milestone.closed ? 'Reopen milestone {name}' : 'Close milestone {name}', { name: milestone.name })" @click="write(`${base}/${milestone.id}/state`, 'PUT', { closed: !milestone.closed })">{{ t(milestone.closed ? 'Reopen milestone' : 'Close milestone') }}</PButton>
        </div>
      </li>
    </ul>
    <p v-else-if="!error" class="hint">{{ t('No milestones yet.') }}</p>
  </section>
</template>

<style scoped>
.milestone-form { display: grid; gap: 10px; padding: 12px 0; }
.milestone-form label { gap: 5px; }
.milestone-form footer, .milestone-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.milestone-form footer { justify-content: flex-end; }
.milestone-list { list-style: none; padding: 0; }
.milestone-list li { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; padding: 12px 0; border-bottom: 1px solid var(--border); }
.milestone-summary { min-width: 0; overflow-wrap: anywhere; }
.milestone-summary p { margin: 4px 0 0; }
.milestone-description { white-space: pre-wrap; }
</style>
