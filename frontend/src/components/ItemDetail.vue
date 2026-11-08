<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import type { Assignee, Attachment, Discussion, LabelDefinition, WorkItem } from '../types'
import LabelBadge from './LabelBadge.vue'
import { itemTypes, priorities, statuses } from '../types'
import Markdown from '../Markdown.vue'
import UserAvatar from './UserAvatar.vue'
import ItemField from './ItemField.vue'
const RichTextEditor = defineAsyncComponent(() => import('./RichTextEditor.vue'))

const props = defineProps<{ itemId: string; canWrite: boolean; standalone: boolean }>()
const emit = defineEmits<{ close: []; updated: [] }>()
const route = useRoute(), router = useRouter()
function openFullscreen() {
  const query = { ...route.query }
  delete query.view
  router.replace({ path: route.path, query, hash: route.hash })
}
const item = ref<WorkItem | null>(null), discussion = ref<Discussion[]>([]), attachments = ref<Attachment[]>([])
const error = ref(''), busy = ref(false), editingContent = ref(false), comment = ref('')
const checklistBusy = ref(false)
const commentUploading = ref(false)
const descriptionUploading = ref(false), contentDraft = ref({ title: '', description: '' })
const titleInput = ref<{ $el: HTMLInputElement } | null>(null)
const copyStatus = ref('')
const headerReference = computed(() => item.value?.reference.replace(/-(\d+)$/, '#$1'))
async function copyLink() {
  if (!item.value) return
  copyStatus.value = ''
  const url = new URL(item.value.web_url, window.location.origin).href
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(url)
    else {
      const focused = document.activeElement as HTMLElement | null
      const input = document.createElement('textarea')
      input.value = url
      input.setAttribute('readonly', '')
      input.style.position = 'fixed'; input.style.left = '-9999px'
      document.body.appendChild(input)
      try {
        input.select()
        if (!document.execCommand('copy')) throw new Error('Copy failed')
      } finally { input.remove(); focused?.focus({ preventScroll: true }) }
    }
    copyStatus.value = 'Link copied'
  } catch { copyStatus.value = 'Unable to copy link. Copy the ticket link manually.' }
}
const assignees = ref<Assignee[]>([]), assigneesReady = ref(false)
const labels = ref<LabelDefinition[]>([]), labelsReady = ref(false)
const assigneeOptions = computed(() => {
  const options: { value: string; label: string; disabled?: boolean }[] = [{ value: '', label: 'Unassigned' }, ...assignees.value.map(user => ({ value: user.id, label: user.name + (user.is_bot ? ' (Bot)' : '') }))]
  if (item.value?.assignee && !assignees.value.some(user => user.id === item.value?.assignee_id)) {
    options.push({ value: item.value.assignee.id, label: item.value.assignee.name + ' (no longer assignable)', disabled: true })
  }
  return options
})
const participants = computed(() => [...new Map(discussion.value.map(entry => [entry.author, entry])).values()])

async function load() {
  try {
    const [i, d, a] = await Promise.all([api<WorkItem>(`/items/${props.itemId}`), api<Discussion[]>(`/items/${props.itemId}/discussion`), api<Attachment[]>(`/items/${props.itemId}/attachments`)])
    item.value = i; discussion.value = d; attachments.value = a
    labels.value = await api<LabelDefinition[]>(`/projects/${i.project_id}/labels`)
    labelsReady.value = true
    if (props.canWrite) {
      assignees.value = await api<Assignee[]>(`/projects/${i.project_id}/assignees`)
      assigneesReady.value = true
    }
  } catch (e) { error.value = (e as Error).message }
}
onMounted(load)
type EditableField = 'type' | 'status' | 'priority' | 'due_date' | 'labels' | 'assignee_id'
async function saveField(field: EditableField, value: string) {
  const saved = field === 'labels' ? JSON.parse(value) : field === 'due_date' || field === 'assignee_id' ? value || null : value
  return saveFields({ [field]: saved })
}
async function saveFields(values: Record<string, unknown>) {
  if (!props.canWrite || busy.value || checklistBusy.value) return false
  busy.value = true; error.value = ''
  try {
    item.value = await api<WorkItem>(`/items/${props.itemId}`, { method: 'PATCH', body: JSON.stringify(values) })
    await load(); emit('updated')
    return true
  } catch (e) { error.value = (e as Error).message; return false } finally { busy.value = false }
}
async function editContent() {
  if (!item.value || !props.canWrite || busy.value || checklistBusy.value) return
  contentDraft.value = { title: item.value.title, description: item.value.description }
  editingContent.value = true; error.value = ''
  await nextTick()
  titleInput.value?.$el.focus()
}
function cancelContent() {
  if (busy.value || descriptionUploading.value) return
  editingContent.value = false; error.value = ''
}
async function saveContent() {
  if (descriptionUploading.value) return
  if (await saveFields(contentDraft.value)) editingContent.value = false
}
async function addComment() {
  if (checklistBusy.value) return
  busy.value = true; error.value = ''
  try {
    await api(`/items/${props.itemId}/comments`, { method: 'POST', body: JSON.stringify({ body: comment.value }) })
    comment.value = ''; await load(); emit('updated')
  } catch (e) { error.value = (e as Error).message } finally { busy.value = false }
}
async function refreshAttachments() {
  try {
    const [files, entries] = await Promise.all([
      api<Attachment[]>(`/items/${props.itemId}/attachments`),
      api<Discussion[]>(`/items/${props.itemId}/discussion`),
    ])
    attachments.value = files
    discussion.value = entries
  } catch (e) { error.value = (e as Error).message }
}

async function toggleChecklist(index: number, checked: boolean, entry?: Discussion) {
  if (!item.value || !props.canWrite || editingContent.value || busy.value || checklistBusy.value) return
  checklistBusy.value = true
  error.value = ''
  const path = entry
    ? `/items/${props.itemId}/comments/${entry.id}/checklist/${index}`
    : `/items/${props.itemId}/checklist/${index}`
  try {
    await api(path, { method: 'PATCH', body: JSON.stringify({ checked, version: entry ? entry.body_version : item.value.description_version }) })
    await load()
    emit('updated')
  } catch (e) {
    error.value = (e as Error).message
    await load()
  } finally { checklistBusy.value = false }
}
</script>

<template>
  <div v-if="!standalone" class="panel-shade" @click="emit('close')"></div>
  <section class="detail-panel" :class="{ standalone }" :role="standalone ? undefined : 'dialog'" aria-label="Work item detail" @keydown.esc="emit('close')">
    <header class="detail-top"><div class="detail-reference"><RouterLink v-if="item" :to="item.web_url" title="Open standalone page">{{ headerReference }}</RouterLink><span v-else>Work item</span><PButton v-if="item" class="quiet copy-ticket-link" aria-label="Copy ticket link" :title="copyStatus || 'Copy ticket link'" @click="copyLink"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path v-if="copyStatus === 'Link copied'" d="m5 12 4 4L19 6" /><template v-else><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h4" /></template></svg></PButton><span class="sr-only" role="status">{{ copyStatus }}</span></div><div><PButton v-if="item && canWrite && !editingContent" class="quiet detail-edit" :disabled="busy || checklistBusy" aria-label="Edit ticket" @click="editContent">Edit</PButton>
    <PButton v-if="!standalone && item" type="button" class="quiet detail-fullscreen" aria-label="Open fullscreen" title="Open fullscreen" @click="openFullscreen"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 10l7-7m-6 0h6v6M10 14l-7 7m0-6v6h6" /></svg></PButton>
    <PButton class="quiet" @click="emit('close')" :aria-label="standalone ? 'Back to project' : 'Close detail'">{{ standalone ? '← Back' : '×' }}</PButton></div></header>
    <div v-if="error" class="error banner" role="alert">{{ error }}</div>
    <div v-if="!item" class="empty-state">{{ error ? 'Unable to load work item.' : 'Loading work item…' }}</div>
    <div v-else class="detail-body">
      <h1 v-if="!editingContent">{{ item.title }}</h1>
      <div class="detail-layout">
        <div class="detail-main">
      <form v-if="editingContent" class="edit-form" aria-label="Edit ticket" @submit.prevent="saveContent" @keydown.esc.stop.prevent="cancelContent">
        <label>Title<InputText ref="titleInput" v-model="contentDraft.title" required maxlength="250" :disabled="busy" /></label>
        <div class="editor-field"><span class="editor-field-label">Description</span><RichTextEditor v-model="contentDraft.description" label="Description" :item-id="itemId" :project-id="item.project_id" :disabled="busy" @uploading="descriptionUploading = $event" @uploaded="refreshAttachments" /></div>
        <footer><PButton type="button" severity="secondary" outlined :disabled="busy || descriptionUploading" @click="cancelContent">Cancel</PButton><PButton type="submit" :disabled="busy || checklistBusy || descriptionUploading">Save changes</PButton></footer>
      </form>
      <template v-else><Markdown v-if="item.description" :text="item.description" :project-id="item.project_id" :interactive="canWrite" :busy="busy || checklistBusy" @toggle="(index, checked) => toggleChecklist(index, checked)" /><p v-else class="muted">No description yet.</p></template>
      <p v-if="checklistBusy" class="hint" role="status">Saving checklist…</p>
      <section v-if="attachments.length" class="attachments"><h3>Attachments <span class="count">{{ attachments.length }}</span></h3><a v-for="a in attachments" :key="a.id" :href="a.url" target="_blank" rel="noopener">↳ {{ a.filename }} <small>{{ Math.max(1, Math.round(a.size / 1024)) }} KB</small></a></section>
      <section class="discussion">
        <h2>Activity</h2>
        <div v-for="entry in discussion" :key="entry.id" class="discussion-entry" :class="entry.kind"><UserAvatar :name="entry.author" :src="entry.avatar_url" /><div class="discussion-content"><header><strong>{{ entry.author }}</strong><span v-if="entry.author_is_bot" class="bot-badge">Bot</span><time>{{ new Date(entry.created_at).toLocaleString() }}</time></header><Markdown v-if="entry.kind === 'comment'" :text="entry.body" :project-id="item.project_id" :interactive="canWrite && !editingContent" :busy="busy || checklistBusy" @toggle="(index, checked) => toggleChecklist(index, checked, entry)" /><p v-else>{{ entry.body }}</p></div></div>
        <form v-if="canWrite" class="comment-form rich-comment-form" @submit.prevent="addComment">
          <RichTextEditor v-model="comment" label="Comment" placeholder="Leave a comment…" :item-id="itemId" :project-id="item.project_id" :disabled="busy"
            @uploading="commentUploading = $event" @uploaded="refreshAttachments" />
          <footer><PButton type="submit" :loading="busy" :disabled="busy || commentUploading || checklistBusy || !comment.trim()">Add comment</PButton></footer>
        </form>
        <p v-else class="hint">You have read-only access to this project.</p>
      </section>
        </div>
        <aside class="detail-metadata" aria-label="Work item metadata">
          <section><ItemField label="Status" kind="select" :value="item.status" :options="statuses" :can-write="canWrite" :disabled="busy || checklistBusy" :save="value => saveField('status', value)" @editing="error = ''"><span class="status-badge" :class="item.status.toLowerCase().replace(' ', '-')">{{ item.status }}</span></ItemField></section>
          <section><ItemField label="Type" kind="select" :value="item.type" :options="itemTypes" :can-write="canWrite" :disabled="busy || checklistBusy" :save="value => saveField('type', value)" @editing="error = ''"><span>{{ item.type }}</span></ItemField></section>
          <section><ItemField label="Priority" kind="select" :value="item.priority" :options="priorities" :can-write="canWrite" :disabled="busy || checklistBusy" :save="value => saveField('priority', value)" @editing="error = ''"><span class="priority" :class="item.priority.toLowerCase()">{{ item.priority }}</span></ItemField></section>
          <section><ItemField label="Due date" kind="date" :value="item.due_date || ''" :can-write="canWrite" :disabled="busy || checklistBusy" :save="value => saveField('due_date', value)" @editing="error = ''"><span>{{ item.due_date || 'Not set' }}</span></ItemField></section>
          <section><ItemField label="Labels" kind="labels" :value="JSON.stringify(item.labels)" :label-definitions="labels" :can-write="canWrite" :disabled="busy || checklistBusy || !labelsReady" :save="value => saveField('labels', value)" @editing="error = ''"><div v-if="item.labels.length" class="labels"><LabelBadge v-for="tag in item.labels" :key="tag" :name="tag" :definition="labels.find(label => label.name === tag)" /></div><span v-else class="muted">None</span></ItemField></section>
          <section><ItemField label="Assignee" kind="select" :value="item.assignee_id || ''" :options="assigneeOptions" :can-write="canWrite" :disabled="busy || checklistBusy || !assigneesReady" :save="value => saveField('assignee_id', value)" @editing="error = ''"><span v-if="item.assignee" class="assignee-value"><UserAvatar :name="item.assignee.name" :src="item.assignee.avatar_url" /><span>{{ item.assignee.name }} <span v-if="item.assignee.is_bot" class="bot-badge">Bot</span></span></span><span v-else class="muted">Unassigned</span></ItemField></section>
          <section><h3>Participants <span class="count">{{ participants.length }}</span></h3><div v-if="participants.length" class="detail-participants"><span v-for="participant in participants" :key="participant.author" :title="participant.author"><UserAvatar :name="participant.author" :src="participant.avatar_url" /></span></div><span v-else class="muted">None</span></section>
        </aside>
      </div>
    </div>
  </section>
</template>
