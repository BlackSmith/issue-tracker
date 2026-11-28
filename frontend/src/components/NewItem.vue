<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import type { LabelDefinition, Milestone, Project, WorkItem } from '../types'
import LabelPicker from './LabelPicker.vue'
import { itemTypes, priorities } from '../types'
import { t, translatedOptions } from '../i18n'
import { ticketRevision } from '../realtime'

const RichTextEditor = defineAsyncComponent(() => import('./RichTextEditor.vue'))
const props = defineProps<{ project: Project; standalone: boolean }>()
const emit = defineEmits<{ close: []; toggleView: []; created: [item: WorkItem] }>()
const form = ref({ title: '', description: '', type: 'Task', status: 'Open', priority: 'Medium', labels: [] as string[], due_date: '', milestone_id: '' })
const labels = ref<LabelDefinition[]>([])
const milestones = ref<Milestone[]>([])
const milestoneOptions = computed(() => [
  { id: '', name: t('No milestone') },
  ...milestones.value.filter(milestone => !milestone.closed || milestone.id === form.value.milestone_id)
    .map(milestone => ({ id: milestone.id, name: milestone.closed ? t('{name} (closed)', { name: milestone.name }) : milestone.name, disabled: milestone.closed })),
])
async function loadMilestones() {
  try { milestones.value = await api<Milestone[]>(`/projects/${props.project.id}/milestones`) }
  catch (e) { error.value = (e as Error).message }
}
onMounted(loadMilestones)
watch(ticketRevision, loadMilestones)
onMounted(async () => {
  try { labels.value = await api<LabelDefinition[]>(`/projects/${props.project.id}/labels`) }
  catch (e) { error.value = (e as Error).message }
})
const busy = ref(false), error = ref(''), titleInput = ref<{ $el: HTMLInputElement } | null>(null)
const uploading = ref(false)
onMounted(() => titleInput.value?.$el.focus())

function close() {
  if (!busy.value) emit('close')
}
async function create() {
  if (busy.value || uploading.value || !props.project.can_write) return
  busy.value = true; error.value = ''
  try {
    const item = await api<WorkItem>(`/projects/${props.project.id}/items`, {
      method: 'POST',
      body: JSON.stringify({ ...form.value, due_date: form.value.due_date || null, milestone_id: form.value.milestone_id || null }),
    })
    emit('created', item)
  } catch (e) {
    error.value = (e as Error).message
    if ((e as { status?: number }).status === 409) await loadMilestones()
  }
  finally { busy.value = false }
}
</script>

<template>
  <div v-if="!standalone" class="panel-shade" @click="close"></div>
  <section class="detail-panel new-item-panel" :class="{ standalone }" :role="standalone ? undefined : 'dialog'" aria-labelledby="new-item-heading" :aria-busy="busy" @keydown.esc="close">
    <header class="detail-top">
      <div class="detail-reference"><span>{{ project.key }} · {{ t('New work item') }}</span></div>
      <div class="new-item-actions"><PButton type="button" class="quiet" :disabled="busy" :aria-label="t(standalone ? 'Show as panel' : 'Open fullscreen')" :title="t(standalone ? 'Show as panel' : 'Open fullscreen')" @click="emit('toggleView')"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path v-if="standalone" d="M21 3l-7 7m0-6v6h6M3 21l7-7m-6 0h6v6" /><path v-else d="M14 10l7-7m-6 0h6v6M10 14l-7 7m0-6v6h6" /></svg></PButton><PButton type="button" class="quiet" :disabled="busy" :aria-label="t(standalone ? 'Back to project' : 'Close new work item')" :title="t(standalone ? 'Back to project' : 'Close new work item')" @click="close"><svg v-if="standalone" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m12 5-7 7 7 7M5 12h14" /></svg><template v-else>×</template></PButton></div>
    </header>
    <div class="detail-body">
      <h1 id="new-item-heading">{{ t('New work item') }}</h1>
      <p v-if="!project.can_write" class="hint">{{ t('You have read-only access to this project.') }}</p>
      <form v-else class="edit-form" :aria-label="t('New work item')" @submit.prevent="create">
        <label>{{ t('Title') }}<InputText ref="titleInput" v-model="form.title" required maxlength="250" :placeholder="t('What needs to be done?')" :disabled="busy" /></label>
        <div class="detail-layout">
          <div class="detail-main">
            <div class="editor-field"><span class="editor-field-label">{{ t('Description') }}</span><RichTextEditor v-model="form.description" :label="t('Description')" :placeholder="t('Add context, a checklist, or acceptance criteria…')" :project-id="project.id" :disabled="busy" @uploading="uploading = $event" /></div>
          </div>
          <aside class="detail-metadata" :aria-label="t('Work item metadata')">
            <label>{{ t('Type') }}<PSelect v-model="form.type" :options="translatedOptions(itemTypes)" option-label="label" option-value="value" :disabled="busy" :aria-label="t('Type')" /></label>
            <label>{{ t('Priority') }}<PSelect v-model="form.priority" :options="translatedOptions(priorities)" option-label="label" option-value="value" :disabled="busy" :aria-label="t('Priority')" /></label>
            <label>{{ t('Due date') }}<InputText v-model="form.due_date" type="date" :disabled="busy" /></label>
            <label>{{ t('Milestone') }}<PSelect v-model="form.milestone_id" :options="milestoneOptions" option-label="name" option-value="id" option-disabled="disabled" filter :disabled="busy" :aria-label="t('Milestone')" /></label>
            <LabelPicker v-model="form.labels" :definitions="labels" :disabled="busy" />
          </aside>
        </div>
        <PMessage v-if="error" severity="error">{{ t(error) }}</PMessage>
        <footer><PButton type="button" severity="secondary" outlined :disabled="busy" @click="close">{{ t('Cancel') }}</PButton><PButton type="submit" :loading="busy" :disabled="busy || uploading">{{ t('Create work item') }}</PButton></footer>
      </form>
    </div>
  </section>
</template>

<style scoped>
.new-item-actions { display: flex; align-items: center; gap: 4px; }
.new-item-panel .detail-metadata input, .new-item-panel .detail-metadata select { padding: 8px 5px; }
.new-item-panel .detail-top { flex-wrap: wrap; gap: 8px; }
</style>
