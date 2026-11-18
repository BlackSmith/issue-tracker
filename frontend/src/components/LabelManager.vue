<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import type { LabelDefinition } from '../types'
import LabelBadge from './LabelBadge.vue'
import SettingsDetailPanel from './SettingsDetailPanel.vue'
import { t } from '../i18n'

const props = defineProps<{ projectId?: string; panelId?: string }>()
const emit = defineEmits<{ updated: []; open: [id: string]; close: [] }>()
const panelMode = computed(() => props.panelId !== undefined)
const base = computed(() => props.projectId ? `/projects/${props.projectId}/labels` : '/organization/labels')
const labels = ref<LabelDefinition[]>([]), busy = ref(false), loading = ref(true), error = ref(''), message = ref('')
const editing = ref('')
const showForm = ref(false)
const empty = () => ({ name: '', color: '#16a34a', description: '' })
const form = ref(empty())
const panelFound = computed(() => !panelMode.value || props.panelId === 'new' || labels.value.some(label => label.id === props.panelId && label.project_id === (props.projectId || null)))
watch([() => props.panelId, loading], ([id, isLoading]) => {
  if (!panelMode.value || isLoading) return
  showForm.value = !!id
  editing.value = ''; form.value = empty(); error.value = ''
  if (id && id !== 'new') {
    const label = labels.value.find(label => label.id === id)
    if (label && panelFound.value) {
      editing.value = label.id
      form.value = { name: label.name, color: label.color, description: label.description }
    }
  }
}, { immediate: true })
async function load() {
  try { labels.value = await api<LabelDefinition[]>(base.value) }
  catch (e) { error.value = (e as Error).message }
  finally { loading.value = false }
}
onMounted(load)
function edit(label: LabelDefinition) {
  if (panelMode.value) { emit('open', label.id); return }
  showForm.value = true
  editing.value = label.id
  form.value = { name: label.name, color: label.color, description: label.description }
  error.value = ''; message.value = ''
}
function add() {
  error.value = ''; message.value = ''
  if (panelMode.value) emit('open', 'new')
  else showForm.value = true
}
function cancel() {
  editing.value = ''; form.value = empty(); showForm.value = false
  if (panelMode.value && props.panelId) emit('close')
}
async function save() {
  busy.value = true; error.value = ''; message.value = ''
  try {
    await api(base.value + (editing.value ? `/${editing.value}` : ''), { method: editing.value ? 'PUT' : 'POST', body: JSON.stringify(form.value) })
    cancel(); await load(); emit('updated'); message.value = 'Label saved.'
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function remove(label: LabelDefinition) {
  if (!window.confirm(t('Delete label "{name}"?', { name: label.name }))) return
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
  <section class="label-manager" :aria-label="t('Label management')">
    <p class="hint">{{ t(projectId ? 'All organization labels are inherited automatically. Manage inherited labels in organization settings.' : 'Organization labels are available in every project, including projects created later.') }}</p>
    <PMessage v-if="error && (!panelMode || !showForm)" severity="error">{{ t(error) }}</PMessage><PMessage v-if="message" severity="success">{{ t(message) }}</PMessage>
    <PButton v-if="!showForm" type="button" class="add-label-toggle" :disabled="busy || loading" :aria-expanded="false" @click="add">{{ t('Add label') }}</PButton>
    <component v-if="showForm" :is="panelMode ? SettingsDetailPanel : 'div'" v-bind="panelMode ? { title: t(!panelFound ? 'Label details' : editing ? 'Edit label' : 'Add label'), busy } : {}" @close="cancel">
    <PMessage v-if="panelMode && error" severity="error">{{ t(error) }}</PMessage>
    <PMessage v-if="!panelFound" severity="error">{{ t('Label not found.') }}</PMessage>
    <form v-else class="label-form" :aria-label="t(editing ? 'Edit label' : 'Add label')" @submit.prevent="save">
      <h3 v-if="!panelMode">{{ t(editing ? 'Edit label' : 'Add label') }}</h3>
      <div class="label-form-fields">
        <label>{{ t('Name') }}<InputText v-model="form.name" required maxlength="50" :disabled="busy" /></label>
        <label>{{ t('Color') }}<input v-model="form.color" type="color" required :disabled="busy" /></label>
      </div>
      <label>{{ t('Description') }}<PTextarea v-model="form.description" rows="2" maxlength="2000" :disabled="busy" /></label>
      <p class="hint">{{ t('Names must be unique among the labels available in a project. Renaming preserves existing ticket assignments. Used labels cannot be deleted.') }}</p>
      <footer><PButton type="button" severity="secondary" outlined :disabled="busy" @click="cancel">{{ t('Cancel') }}</PButton><PButton type="submit" :loading="busy" :disabled="busy || loading">{{ t(editing ? 'Save label' : 'Add label') }}</PButton></footer>
    </form>
    </component>
    <p v-if="loading" class="hint">{{ t('Loading labels…') }}</p>
    <ul v-else class="managed-labels">
      <li v-for="label in labels" :key="label.id">
        <div><LabelBadge :name="label.name" :definition="label" /><p v-if="label.description">{{ label.description }}</p></div>
        <div v-if="label.project_id === (projectId || null)" class="label-actions"><PButton severity="secondary" outlined :disabled="busy" @click="edit(label)">{{ t('Edit') }}</PButton><PButton severity="danger" outlined :disabled="busy" @click="remove(label)">{{ t('Delete') }}</PButton></div>
        <small v-else>{{ t('Inherited') }}</small>
      </li>
    </ul>
    <p v-if="!loading && !labels.length" class="hint">{{ t('No labels defined yet.') }}</p>
  </section>
</template>

<style scoped>
.managed-labels { padding: 0; list-style: none; }
.managed-labels li { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--border); overflow-wrap: anywhere; }
.managed-labels li > div:first-child { min-width: 0; }
.managed-labels p { margin: 6px 0; white-space: pre-wrap; }
.label-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.add-label-toggle { margin-bottom: 16px; }
.label-form { border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 16px; }
.label-form h3 { margin-bottom: 10px; }
.label-form-fields { display: grid; grid-template-columns: minmax(0, 1fr) 80px; gap: 10px; }
.label-form label { min-width: 0; gap: 5px; margin-bottom: 10px; font-size: 12px; }
.label-form footer { display: flex; justify-content: flex-end; gap: 8px; }
input[type=color] { width: 80px; height: 40px; padding: 4px; }
</style>
