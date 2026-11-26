<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import type { Assignee, Attachment, Discussion, LabelDefinition, WorkItem } from '../types'
import LabelBadge from './LabelBadge.vue'
import { itemTypes, priorities, statuses } from '../types'
import Markdown from '../Markdown.vue'
import UserAvatar from './UserAvatar.vue'
import ItemField from './ItemField.vue'
import StatusBadge from './StatusBadge.vue'
import NotificationSettings from './NotificationSettings.vue'
import { dateOnly, dateTime, t } from '../i18n'
import { activityText } from '../activity'
import { ticketRevision } from '../realtime'
const RichTextEditor = defineAsyncComponent(() => import('./RichTextEditor.vue'))

const props = defineProps<{ itemId: string; canWrite: boolean; canManage: boolean; restrictTicketVisibility: boolean; standalone: boolean }>()
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
const contentOriginal = ref({ title: '', description: '' })
const contentConflict = computed(() => editingContent.value && item.value &&
  (item.value.title !== contentOriginal.value.title || item.value.description !== contentOriginal.value.description))
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
  const options: { value: string; label: string; disabled?: boolean }[] = [{ value: '', label: t('Unassigned') }, ...assignees.value.map(user => ({ value: user.id, label: user.name + (user.is_bot ? t(' (Bot)') : '') }))]
  if (item.value?.assignee && !assignees.value.some(user => user.id === item.value?.assignee_id)) {
    options.push({ value: item.value.assignee.id, label: item.value.assignee.name + t(' (no longer assignable)'), disabled: true })
  }
  return options
})
const expandedActivityGroups = ref(new Set<string>())
const discussionGroups = computed(() => {
  const groups: { id: string; activity: boolean; entries: Discussion[] }[] = []
  for (const entry of discussion.value) {
    const previous = groups.at(-1)
    if (entry.kind === 'activity' && previous?.activity) previous.entries.push(entry)
    else groups.push({ id: `${entry.kind}-${entry.id}`, activity: entry.kind === 'activity', entries: [entry] })
  }
  return groups
})
function toggleActivityGroup(id: string) {
  if (expandedActivityGroups.value.has(id)) expandedActivityGroups.value.delete(id)
  else expandedActivityGroups.value.add(id)
}

let loadSequence = 0
async function load() {
  const sequence = ++loadSequence
  try {
    const [i, d, a] = await Promise.all([api<WorkItem>(`/items/${props.itemId}`), api<Discussion[]>(`/items/${props.itemId}/discussion`), api<Attachment[]>(`/items/${props.itemId}/attachments`)])
    if (sequence !== loadSequence) return
    item.value = i; discussion.value = d; attachments.value = a
    labels.value = await api<LabelDefinition[]>(`/projects/${i.project_id}/labels`)
    labelsReady.value = true
    if (props.canWrite) {
      assignees.value = await api<Assignee[]>(`/projects/${i.project_id}/assignees`)
      assigneesReady.value = true
    }
  } catch (e) {
    if (sequence !== loadSequence) return
    error.value = (e as Error).message
    if ([401, 403, 404].includes((e as { status: number }).status)) {
      item.value = null; discussion.value = []; attachments.value = []
    }
  }
}
onMounted(load)
let pendingRefresh = false
watch(ticketRevision, () => {
  if (busy.value || checklistBusy.value) pendingRefresh = true
  else load()
})
watch([busy, checklistBusy], () => {
  if (pendingRefresh && !busy.value && !checklistBusy.value) { pendingRefresh = false; load() }
})
type EditableField = 'type' | 'status' | 'priority' | 'due_date' | 'labels' | 'assignee_id'
function saveField(field: EditableField) {
  return (value: string, original: string) => {
    const decode = (v: string) => field === 'labels' ? JSON.parse(v) : field === 'due_date' || field === 'assignee_id' ? v || null : v
    return saveFields({ [field]: decode(value) }, { [field]: decode(original) })
  }
}
async function saveFields(values: Record<string, unknown>, expected: Record<string, unknown>) {
  if (!props.canWrite || busy.value || checklistBusy.value) return false
  busy.value = true; error.value = ''
  try {
    item.value = await api<WorkItem>(`/items/${props.itemId}`, { method: 'PATCH', body: JSON.stringify({ ...values, expected }) })
    await load(); emit('updated')
    return true
  } catch (e) {
    error.value = (e as Error).message
    if ((e as { status: number }).status === 409) await load()
    return false
  } finally { busy.value = false }
}
async function editContent() {
  if (!item.value || !props.canWrite || busy.value || checklistBusy.value) return
  contentDraft.value = { title: item.value.title, description: item.value.description }
  contentOriginal.value = { ...contentDraft.value }
  editingContent.value = true; error.value = ''
  await nextTick()
  titleInput.value?.$el.focus()
}
async function togglePublication() {
  if (!item.value || !props.canManage || busy.value || checklistBusy.value) return
  busy.value = true; error.value = ''
  try {
    item.value = await api<WorkItem>(`/items/${props.itemId}/publication`, {
      method: 'PUT', body: JSON.stringify({ is_project_public: !item.value.is_project_public }),
    })
    await load(); emit('updated')
  } catch (e) { error.value = (e as Error).message } finally { busy.value = false }
}
function cancelContent() {
  if (busy.value || descriptionUploading.value) return
  editingContent.value = false; error.value = ''
}
async function saveContent() {
  if (descriptionUploading.value || contentConflict.value) return
  if (await saveFields(contentDraft.value, contentOriginal.value)) editingContent.value = false
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

async function removeAttachment(attachment: Attachment) {
  if (!props.canWrite || busy.value || checklistBusy.value) return
  busy.value = true; error.value = ''
  try {
    await api(`/items/${props.itemId}/attachments/${attachment.id}`, { method: 'DELETE' })
    await load(); emit('updated')
  } catch (e) { error.value = (e as Error).message } finally { busy.value = false }
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
  <section class="detail-panel" :class="{ standalone }" :role="standalone ? undefined : 'dialog'" :aria-label="t('Work item detail')" @keydown.esc="emit('close')">
    <header class="detail-top"><div class="detail-reference"><RouterLink v-if="item" :to="item.web_url" :title="t('Open standalone page')">{{ headerReference }}</RouterLink><span v-else>{{ t('Work item') }}</span><PButton v-if="item" class="quiet copy-ticket-link" :aria-label="t('Copy ticket link')" :title="t(copyStatus || 'Copy ticket link')" @click="copyLink"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path v-if="copyStatus === 'Link copied'" d="m5 12 4 4L19 6" /><template v-else><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h4" /></template></svg></PButton><span class="sr-only" role="status">{{ t(copyStatus) }}</span></div><div><PButton v-if="item && canWrite && !editingContent" class="quiet detail-edit" :disabled="busy || checklistBusy" :aria-label="t('Edit ticket')" @click="editContent">{{ t('Edit') }}</PButton>
    <PButton v-if="!standalone && item" type="button" class="quiet detail-fullscreen" :aria-label="t('Open fullscreen')" :title="t('Open fullscreen')" @click="openFullscreen"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 10l7-7m-6 0h6v6M10 14l-7 7m0-6v6h6" /></svg></PButton>
    <PButton class="quiet" @click="emit('close')" :aria-label="t(standalone ? 'Back to project' : 'Close detail')">{{ standalone ? t('← Back') : '×' }}</PButton></div></header>
    <div v-if="error" class="error banner" role="alert">{{ t(error) }}</div>
    <div v-if="!item" class="empty-state">{{ t(error ? 'Unable to load work item.' : 'Loading work item…') }}</div>
    <div v-else class="detail-body">
      <h1 v-if="!editingContent">{{ item.title }}</h1>
      <div class="detail-layout">
        <div class="detail-main">
      <form v-if="editingContent" class="edit-form" :aria-label="t('Edit ticket')" @submit.prevent="saveContent" @keydown.esc.stop.prevent="cancelContent">
        <p v-if="contentConflict" class="hint" role="status">{{ t('This content has changed. Cancel your edit and try again.') }}</p>
        <label>{{ t('Title') }}<InputText ref="titleInput" v-model="contentDraft.title" required maxlength="250" :disabled="busy" /></label>
        <div class="editor-field"><span class="editor-field-label">{{ t('Description') }}</span><RichTextEditor v-model="contentDraft.description" :label="t('Description')" :item-id="itemId" :project-id="item.project_id" :disabled="busy" @uploading="descriptionUploading = $event" @uploaded="refreshAttachments" /></div>
        <footer><PButton type="button" severity="secondary" outlined :disabled="busy || descriptionUploading" @click="cancelContent">{{ t('Cancel') }}</PButton><PButton type="submit" :disabled="busy || checklistBusy || descriptionUploading || !!contentConflict">{{ t('Save changes') }}</PButton></footer>
      </form>
      <template v-else><Markdown v-if="item.description" :text="item.description" :project-id="item.project_id" :interactive="canWrite" :busy="busy || checklistBusy" @toggle="(index, checked) => toggleChecklist(index, checked)" /><p v-else class="muted">{{ t('No description yet.') }}</p></template>
      <p v-if="checklistBusy" class="hint" role="status">{{ t('Saving checklist…') }}</p>
      <section v-if="attachments.length" class="attachments"><h3>{{ t('Attachments') }} <span class="count">{{ attachments.length }}</span></h3><div v-for="a in attachments" :key="a.id" class="attachment-row"><a :href="a.url" target="_blank" rel="noopener">↳ {{ a.filename }} <small>{{ Math.max(1, Math.round(a.size / 1024)) }} KB</small></a><PButton v-if="canWrite" type="button" class="quiet" :disabled="busy || checklistBusy" :aria-label="t('Remove attachment {filename}', { filename: a.filename })" @click="removeAttachment(a)">{{ t('Remove') }}</PButton></div></section>
      <section class="discussion">
        <h2>{{ t('Activity') }}</h2>
        <div v-for="group in discussionGroups" :key="group.id">
          <PButton v-if="group.activity && group.entries.length > 2" type="button" class="quiet activity-group-toggle" :aria-expanded="expandedActivityGroups.has(group.id)" :aria-controls="`discussion-${group.id}`" @click="toggleActivityGroup(group.id)">
            <span aria-hidden="true">{{ expandedActivityGroups.has(group.id) ? '▾' : '▸' }}</span>
            {{ t(expandedActivityGroups.has(group.id) ? 'Hide activities ({count})' : 'Show activities ({count})', { count: group.entries.length }) }}
          </PButton>
          <div :id="`discussion-${group.id}`" v-show="group.entries.length <= 2 || expandedActivityGroups.has(group.id)">
            <div v-for="entry in group.entries" :key="entry.id" class="discussion-entry" :class="entry.kind"><UserAvatar :name="entry.author" :src="entry.avatar_url" /><div class="discussion-content"><header><strong>{{ entry.author }}</strong><span v-if="entry.author_is_bot" class="bot-badge">{{ t('Bot') }}</span><time>{{ dateTime(entry.created_at) }}</time></header><Markdown v-if="entry.kind === 'comment'" :text="entry.body" :project-id="item.project_id" :interactive="canWrite && !editingContent" :busy="busy || checklistBusy" @toggle="(index, checked) => toggleChecklist(index, checked, entry)" /><p v-else>{{ activityText(entry.body) }}</p></div></div>
          </div>
        </div>
        <form v-if="canWrite" class="comment-form rich-comment-form" @submit.prevent="addComment">
          <RichTextEditor v-model="comment" :label="t('Comment')" :placeholder="t('Leave a comment…')" :item-id="itemId" :project-id="item.project_id" :disabled="busy"
            @uploading="commentUploading = $event" @uploaded="refreshAttachments" />
          <footer><PButton type="submit" :loading="busy" :disabled="busy || commentUploading || checklistBusy || !comment.trim()">{{ t('Add comment') }}</PButton></footer>
        </form>
        <p v-else class="hint">{{ t('You have read-only access to this project.') }}</p>
      </section>
        </div>
        <aside class="detail-metadata" :aria-label="t('Work item metadata')">
          <section v-if="restrictTicketVisibility" class="ticket-publication"><h3>{{ t('Ticket visibility') }}</h3><p>{{ t(item.is_project_public ? 'All project members' : 'Author, assignee and project owners') }}</p><PButton v-if="canManage" type="button" severity="secondary" outlined :disabled="busy || checklistBusy" @click="togglePublication">{{ t(item.is_project_public ? 'Restrict ticket visibility' : 'Publish to project members') }}</PButton></section>
          <section><ItemField :label="t('Status')" kind="status" :value="item.status" :options="statuses" :can-write="canWrite" :disabled="busy || checklistBusy" :save="saveField('status')" @editing="error = ''"><StatusBadge :status="item.status" /></ItemField></section>
          <section><ItemField :label="t('Type')" kind="select" :value="item.type" :options="itemTypes" :can-write="canWrite" :disabled="busy || checklistBusy" :save="saveField('type')" @editing="error = ''"><span>{{ t(item.type) }}</span></ItemField></section>
          <section><ItemField :label="t('Priority')" kind="select" :value="item.priority" :options="priorities" :can-write="canWrite" :disabled="busy || checklistBusy" :save="saveField('priority')" @editing="error = ''"><span class="priority" :class="item.priority.toLowerCase()">{{ t(item.priority) }}</span></ItemField></section>
          <section><ItemField :label="t('Due date')" kind="date" :value="item.due_date || ''" :can-write="canWrite" :disabled="busy || checklistBusy" :save="saveField('due_date')" @editing="error = ''"><span>{{ item.due_date ? dateOnly(item.due_date) : t('Not set') }}</span></ItemField></section>
          <section><ItemField :label="t('Labels')" kind="labels" :value="JSON.stringify(item.labels)" :label-definitions="labels" :can-write="canWrite" :disabled="busy || checklistBusy || !labelsReady" :save="saveField('labels')" @editing="error = ''"><div v-if="item.labels.length" class="labels"><LabelBadge v-for="tag in item.labels" :key="tag" :name="tag" :definition="labels.find(label => label.name === tag)" /></div><span v-else class="muted">{{ t('None') }}</span></ItemField></section>
          <section><ItemField :label="t('Assignee')" kind="select" :value="item.assignee_id || ''" :options="assigneeOptions" :can-write="canWrite" :disabled="busy || checklistBusy || !assigneesReady" :save="saveField('assignee_id')" @editing="error = ''"><span v-if="item.assignee" class="assignee-value"><UserAvatar :name="item.assignee.name" :src="item.assignee.avatar_url" /><span>{{ item.assignee.name }} <span v-if="item.assignee.is_bot" class="bot-badge">{{ t('Bot') }}</span></span></span><span v-else class="muted">{{ t('Unassigned') }}</span></ItemField></section>
          <NotificationSettings :item-id="itemId" />
        </aside>
      </div>
    </div>
  </section>
</template>

<style scoped>
.activity-group-toggle { margin-bottom: 16px; }
.attachment-row { display: flex; align-items: center; gap: 8px; }
.attachment-row a { flex: 1; min-width: 0; }
.attachment-row small { white-space: nowrap; }
.attachment-row button { flex-shrink: 0; }
</style>
