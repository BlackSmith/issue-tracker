<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import type { LabelDefinition } from '../types'
import LabelBadge from './LabelBadge.vue'

const props = defineProps<{ projectId?: string }>()
const emit = defineEmits<{ updated: [] }>()
const base = computed(() => props.projectId ? `/projects/${props.projectId}/labels` : '/organization/labels')
const labels = ref<LabelDefinition[]>([]), busy = ref(false), loading = ref(true), error = ref(''), message = ref('')
const editing = ref('')
const empty = () => ({ name: '', color: '#16a34a', description: '' })
const form = ref(empty())
async function load() {
  try { labels.value = await api<LabelDefinition[]>(base.value) }
  catch (e) { error.value = (e as Error).message }
  finally { loading.value = false }
}
onMounted(load)
function edit(label: LabelDefinition) {
  editing.value = label.id
  form.value = { name: label.name, color: label.color, description: label.description }
  error.value = ''; message.value = ''
}
function cancel() { editing.value = ''; form.value = empty() }
async function save() {
  busy.value = true; error.value = ''; message.value = ''
  try {
    await api(base.value + (editing.value ? `/${editing.value}` : ''), { method: editing.value ? 'PUT' : 'POST', body: JSON.stringify(form.value) })
    cancel(); await load(); emit('updated'); message.value = 'Label saved.'
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function remove(label: LabelDefinition) {
  if (!window.confirm(`Delete label "${label.name}"?`)) return
  busy.value = true; error.value = ''; message.value = ''
  try {
    await api(`${base.value}/${label.id}`, { method: 'DELETE' })
    if (editing.value === label.id) cancel()
    await load(); emit('updated'); message.value = 'Label deleted.'
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
</script>

<template>
  <section class="label-manager" aria-label="Label management">
    <p class="hint">{{ projectId ? 'All organization labels are inherited automatically. Manage inherited labels in organization settings.' : 'Organization labels are available in every project, including projects created later.' }}</p>
    <p v-if="loading" class="hint">Loading labels…</p>
    <ul v-else class="managed-labels">
      <li v-for="label in labels" :key="label.id">
        <div><LabelBadge :name="label.name" :definition="label" /><p v-if="label.description">{{ label.description }}</p><small>{{ label.project_id ? 'Project label' : 'Organization label' }}</small></div>
        <div v-if="label.project_id === (projectId || null)" class="label-actions"><button :disabled="busy" @click="edit(label)">Edit</button><button :disabled="busy" @click="remove(label)">Delete</button></div>
        <small v-else>Inherited</small>
      </li>
    </ul>
    <p v-if="!loading && !labels.length" class="hint">No labels defined yet.</p>
    <form @submit.prevent="save">
      <h3>{{ editing ? 'Edit label' : 'Create label' }}</h3>
      <label>Name<input v-model="form.name" required maxlength="50" :disabled="busy" /></label>
      <label>Color<input v-model="form.color" type="color" required :disabled="busy" /></label>
      <label>Description<textarea v-model="form.description" rows="3" maxlength="2000" :disabled="busy" /></label>
      <p class="hint">Names must be unique among the labels available in a project. Renaming preserves existing ticket assignments. Used labels cannot be deleted.</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="message" class="hint" role="status">{{ message }}</p>
      <footer><button v-if="editing" type="button" :disabled="busy" @click="cancel">Cancel</button><button class="primary" :disabled="busy || loading">{{ busy ? 'Saving…' : editing ? 'Save label' : 'Create label' }}</button></footer>
    </form>
  </section>
</template>

<style scoped>
.managed-labels { padding: 0; list-style: none; }
.managed-labels li { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--border); overflow-wrap: anywhere; }
.managed-labels li > div:first-child { min-width: 0; }
.managed-labels p { margin: 6px 0; white-space: pre-wrap; }
.label-actions { display: flex; gap: 6px; flex-wrap: wrap; }
input[type=color] { width: 80px; height: 40px; padding: 4px; }
</style>
