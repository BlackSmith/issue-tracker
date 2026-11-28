<script setup lang="ts">
import { computed, nextTick, onMounted, provide, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, auth } from './api'
import type { Assignee, LabelDefinition, Milestone, Project, WorkItem } from './types'
import LabelBadge from './components/LabelBadge.vue'
import StatusBadge from './components/StatusBadge.vue'
import WorkItemFilters, { type FilterKey, type Filters } from './components/WorkItemFilters.vue'
import ItemDetail from './components/ItemDetail.vue'
import ProjectSettings from './components/ProjectSettings.vue'
import NewItem from './components/NewItem.vue'
import WorkspaceSidebar from './components/WorkspaceSidebar.vue'
import NotificationSettings, { notificationPreferenceUpdate } from './components/NotificationSettings.vue'
import { defaultStatuses, isDefaultStatusFilter, readFilterValues, statusFilterQuery } from './itemFilters'
import { dateOnly, dateTime, itemCount, t } from './i18n'
import { ticketRevision, useLiveTickets } from './realtime'

const route = useRoute(), router = useRouter()
provide(notificationPreferenceUpdate, shallowRef(null))
const projects = ref<Project[]>([]), items = ref<WorkItem[]>([]), total = ref(0)
const labels = ref<LabelDefinition[]>([])
const assignees = ref<Assignee[]>([])
const milestoneCatalog = ref<Milestone[]>([])
const loading = ref(true), error = ref(''), busy = ref(false)
const showProject = ref(false), showSettings = ref(false)
const settingsButton = ref<{ $el: HTMLButtonElement } | null>(null)
const projectForm = ref({ key: '', name: '', description: '', visibility: 'private' })
const resolvedItem = ref<WorkItem | null>(null), resolvedPath = ref('')
const projectId = computed(() => String(route.params.projectId
  || projects.value.find(p => p.slug === route.params.projectSlug)?.id
  || projects.value.find(p => p.legacy_slug === route.params.projectSlug)?.id
  || (resolvedPath.value === route.path ? resolvedItem.value?.project_id : '') || ''))
const project = computed(() => projects.value.find(p => p.id === projectId.value))
const milestones = computed(() => milestoneCatalog.value.filter(milestone => milestone.project_id === projectId.value))
const milestoneNames = computed(() => new Map(milestones.value.map(milestone => [milestone.id, milestone.name])))
const projectPath = computed(() => project.value ? `/${project.value.slug}/` : '/')
const hasProjectRoute = computed(() => !!route.params.projectSlug || !!route.params.projectId)
const itemId = computed(() => resolvedPath.value === route.path ? resolvedItem.value?.id || '' : '')
const ticketRoute = computed(() => !!route.params.itemNumber || !!route.params.itemId)
const resolvingTicket = computed(() => ticketRoute.value && !itemId.value && loading.value)
const creatingItem = computed(() => route.name === 'new-item')
const standalone = computed(() => (ticketRoute.value || creatingItem.value) && route.query.view !== 'panel')
const q = ref(''), status = ref<string[]>([...defaultStatuses]), label = ref<string[]>([]), sort = ref('updated')
const priority = ref<string[]>([]), type = ref<string[]>([]), assignee = ref<string[]>([]), direction = ref('desc')
const milestone = ref<string[]>([])
const sortOptions = computed(() => [
  { label: 'Updated date', value: 'updated' }, { label: 'Created date', value: 'created' },
  { label: 'Title', value: 'title' }, { label: 'Priority', value: 'priority' }, { label: 'Due date', value: 'due_date' },
].map(option => ({ ...option, label: t(option.label) })))
const filters = computed<Filters>(() => ({ status: status.value, label: label.value, priority: priority.value, type: type.value, assignee: assignee.value, milestone: milestone.value }))
const extraFilters = ['priority', 'type', 'assignee', 'milestone'] as const
const hasFilters = computed(() => !!q.value || !isDefaultStatusFilter(status.value) || label.value.length > 0 || extraFilters.some(key => filters.value[key].length))
const page = computed(() => Number(route.query.page) || 1)
const listQueryKeys = ['q', 'status', 'label', ...extraFilters, 'sort', 'direction', 'page']
const listKey = computed(() => JSON.stringify([projectId.value, ...listQueryKeys.map(key => route.query[key])]))
const loadedListKey = ref('')
const listLoading = computed(() => loading.value && listKey.value !== loadedListKey.value)
let sequence = 0
useLiveTickets(projectId)
watch(ticketRevision, () => load(true))

async function load(background = false) {
  const current = ++sequence
  if (!background) loading.value = true
  error.value = ''
  try {
    projects.value = await api<Project[]>('/projects')
    if (current !== sequence) return
    if (route.params.itemNumber) {
      const item = await api<WorkItem>(`/projects/by-slug/${encodeURIComponent(String(route.params.projectSlug))}/items/${route.params.itemNumber}`)
      if (current !== sequence) return
      if (route.path !== item.web_url) {
        await router.replace({ path: item.web_url, query: route.query, hash: route.hash })
        return
      }
      resolvedItem.value = item
      resolvedPath.value = route.path
    } else if (route.params.itemId || route.query.item) {
      const oldId = String(route.params.itemId || route.query.item)
      const item = await api<WorkItem>(`/items/${encodeURIComponent(oldId)}`)
      if (current !== sequence) return
      if (route.params.projectId && item.project_id !== route.params.projectId) throw new Error('Work item not found in this project')
      if (route.params.projectSlug && item.project_id !== projectId.value) throw new Error('Work item not found in this project')
      const query = { ...route.query }
      if (query.item) { delete query.item; query.view = 'panel' }
      await router.replace({ path: item.web_url, query, hash: route.hash })
      return
    }
    if (current !== sequence) return
    if (route.params.projectId) {
      if (!project.value) throw new Error('Project not found')
      await router.replace({ path: projectPath.value, query: route.query, hash: route.hash })
      return
    }
    if (hasProjectRoute.value && !project.value) throw new Error('Project not found')
    if (route.params.projectSlug && project.value && route.params.projectSlug !== project.value.slug) {
      await router.replace({ path: creatingItem.value ? `${projectPath.value}new` : projectPath.value, query: route.query, hash: route.hash })
      return
    }
    if (route.path === '/' && projects.value.length) {
      await router.replace({ path: `/${projects.value[0]!.slug}/`, query: route.query, hash: route.hash })
      return
    }
    q.value = String(route.query.q || ''); status.value = readFilterValues(route.query.status, defaultStatuses)
    label.value = readFilterValues(route.query.label); sort.value = String(route.query.sort || 'updated')
    priority.value = readFilterValues(route.query.priority); type.value = readFilterValues(route.query.type)
    assignee.value = readFilterValues(route.query.assignee)
    milestone.value = readFilterValues(route.query.milestone)
    direction.value = String(route.query.direction || defaultDirection(sort.value))
    if (projectId.value && !standalone.value) {
      const key = listKey.value
      const [definitions, people, catalog] = await Promise.all([
        api<LabelDefinition[]>(`/projects/${projectId.value}/labels`),
        api<Assignee[]>(`/projects/${projectId.value}/item-assignees`),
        api<Milestone[]>(`/projects/${projectId.value}/milestones`),
      ])
      if (current !== sequence) return
      labels.value = definitions
      assignees.value = people
      milestoneCatalog.value = catalog
      const params = new URLSearchParams({ q: q.value, sort: sort.value, direction: direction.value, page: String(page.value) })
      status.value.forEach(value => params.append('status', value))
      label.value.forEach(value => params.append('label', value))
      for (const key of extraFilters) filters.value[key].forEach(value => params.append(key, value))
      const result = await api<{ items: WorkItem[]; total: number }>(`/projects/${projectId.value}/items?${params}`)
      if (current !== sequence) return
      items.value = result.items; total.value = result.total
      loadedListKey.value = key
    }
  } catch (e) {
    if (current === sequence) {
      error.value = (e as Error).message
      if ((e as { status?: number }).status === 404 || (e as { status?: number }).status === 401) {
        resolvedItem.value = null; resolvedPath.value = ''; items.value = []; total.value = 0
        loadedListKey.value = ''
      }
    }
  }
  finally { if (current === sequence) loading.value = false }
}
onMounted(() => load())
watch(() => route.fullPath, () => {
  showProject.value = false
  showSettings.value = false
  load()
})

function filter(reset = true) {
  const query: Record<string, string | string[]> = {}
  if (q.value) query.q = q.value
  const selectedStatuses = statusFilterQuery(status.value)
  if (selectedStatuses !== undefined) query.status = selectedStatuses
  if (label.value.length) query.label = label.value
  if (sort.value !== 'updated') query.sort = sort.value
  if (direction.value !== defaultDirection(sort.value)) query.direction = direction.value
  for (const key of extraFilters) if (filters.value[key].length) query[key] = filters.value[key]
  if (!reset && page.value > 1) query.page = String(page.value)
  router.push({ path: projectPath.value, query })
}
function defaultDirection(value: string) { return ['title', 'due_date'].includes(value) ? 'asc' : 'desc' }
function changeFilter(key: FilterKey, values: string[]) {
  const targets = { status, label, priority, type, assignee, milestone }
  targets[key].value = values
  filter()
}
function changeSort() { direction.value = defaultDirection(sort.value); filter() }
function resetFilters() {
  q.value = ''; status.value = [...defaultStatuses]; label.value = []; priority.value = []; type.value = []; assignee.value = []; milestone.value = []
  filter()
}
function closeItem() {
  const query = { ...route.query }
  delete query.view
  delete query.item
  router.push({ path: projectPath.value, query })
}
async function closeSettings() {
  showSettings.value = false
  await nextTick()
  settingsButton.value?.$el.focus()
}
async function createProject() {
  busy.value = true; error.value = ''
  try {
    const created = await api<Project>('/projects', { method: 'POST', body: JSON.stringify(projectForm.value) })
    showProject.value = false; projectForm.value = { key: '', name: '', description: '', visibility: 'private' }
    await router.push(`/${created.slug}/`)
  } catch (e) { error.value = (e as Error).message } finally { busy.value = false }
}
function newItem() {
  router.push({ path: `${projectPath.value}new`, query: { ...route.query, view: 'panel' } })
}
function setCreationView() {
  const query = { ...route.query }
  if (standalone.value) query.view = 'panel'
  else delete query.view
  router.replace({ path: route.path, query })
}
function itemCreated(item: WorkItem) {
  router.replace({ path: item.web_url, query: route.query })
}
</script>

<template>
  <div class="workspace" :class="{ 'with-detail-panel': (itemId || resolvingTicket || (creatingItem && project)) && !standalone }">
    <WorkspaceSidebar :projects="projects" :project-id="projectId" :loading="loading" :can-create-project="auth.user?.role === 'administrator'" @create-project="showProject = true" />
    <main class="main-content" :class="{ 'standalone-content': standalone }">
      <PMessage v-if="error" severity="error" closable @close="error = ''">{{ t(error) }}</PMessage>
      <template v-if="!standalone">
        <div class="breadcrumbs">{{ t('Organization') }} <span>/</span> {{ project?.name || t('Projects') }}</div>
        <header class="page-heading">
          <div><span class="eyebrow">{{ project?.key || t('YOUR WORKSPACE') }}</span><h1>{{ t('Work items') }} <span v-if="project" class="count">{{ total }}</span></h1><p>{{ project?.description || t('Track ideas, move work forward, and keep everyone in the loop.') }}</p></div>
          <div class="heading-actions">
            <NotificationSettings v-if="project && (!project.restrict_ticket_visibility || project.can_manage)" :key="project.id" :project-id="project.id" compact />
            <PButton v-if="project?.can_manage" ref="settingsButton" type="button" severity="secondary" outlined aria-haspopup="dialog" @click="showSettings = true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" aria-hidden="true">
                <path d="M10 3h4l.6 2.4 1.3.8 2.4-.7 2 3.5-1.8 1.7v2.6l1.8 1.7-2 3.5-2.4-.7-1.3.8L14 21h-4l-.6-2.4-1.3-.8-2.4.7-2-3.5 1.8-1.7v-2.6L3.7 9l2-3.5 2.4.7 1.3-.8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              {{ t('Settings') }}
            </PButton>
            <PButton v-if="project?.can_write" @click="newItem">{{ t('＋ New work item') }}</PButton>
            <PButton v-else-if="!projects.length && auth.user?.role === 'administrator'" @click="showProject = true">{{ t('＋ Create project') }}</PButton>
          </div>
        </header>
        <template v-if="project">
          <div class="work-item-toolbar">
            <WorkItemFilters v-model:query="q" :filters="filters" :labels="labels" :assignees="assignees" :milestones="milestones" @change="changeFilter" @search="filter()" />
          </div>
          <div class="list-caption">
            <div class="list-caption-info">
              <span>{{ itemCount(total) }}</span>
              <PButton v-if="hasFilters" class="quiet" @click="resetFilters">{{ t('Reset filters') }}</PButton>
            </div>
            <div class="work-item-sort" role="group" :aria-label="t('Sorting')">
              <PSelect v-model="sort" class="sort-field" :options="sortOptions" option-label="label" option-value="value" @change="changeSort" :aria-label="t('Sort work items')" />
              <PButton type="button" class="sort-direction" severity="secondary" outlined :aria-label="t(direction === 'asc' ? 'Sort descending' : 'Sort ascending')" :title="t(direction === 'asc' ? 'Ascending · click to reverse' : 'Descending · click to reverse')" @click="direction = direction === 'asc' ? 'desc' : 'asc'; filter()">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M4 6h8M4 12h6M4 18h4M18 6v12" />
                  <path :d="direction === 'asc' ? 'm15 9 3-3 3 3' : 'm15 15 3 3 3-3'" />
                </svg>
              </PButton>
            </div>
          </div>
          <div v-if="listLoading" class="empty-state">{{ t('Loading work items…') }}</div>
          <section v-else-if="items.length" class="item-list" :aria-label="t('Work items')">
            <div v-for="item in items" :key="item.id" class="item-list-entry">
              <RouterLink class="item-row" :to="{ path: item.web_url, query: { ...route.query, view: 'panel' } }">
                <StatusBadge :status="item.status" icon-only />
                <span class="item-info">
                  <strong>{{ item.title }}</strong>
                  <span class="item-meta">{{ item.reference }} <span>·</span> {{ t(item.type) }} <span>·</span> {{ t(item.status) }} <span v-if="item.due_date">· {{ t('Due') }} {{ dateOnly(item.due_date) }}</span></span>
                  <span class="item-list-metadata">
                    <span>{{ t('Last updated') }}: <time :datetime="item.updated_at">{{ dateTime(item.updated_at) }}</time></span>
                    <span>{{ t('Author') }}: {{ item.author.name }}</span>
                    <span>{{ t('Assignee') }}: {{ item.assignee?.name ?? t('Unassigned') }}</span>
                    <span v-if="item.milestone_id && milestoneNames.has(item.milestone_id)">{{ t('Milestone') }}: {{ milestoneNames.get(item.milestone_id) }}</span>
                  </span>
                  <span v-if="item.labels.length" class="labels"><LabelBadge v-for="tag in item.labels" :key="tag" :name="tag" :definition="labels.find(label => label.name === tag)" /></span>
                </span>
                <span class="priority" :class="item.priority.toLowerCase()">{{ t(item.priority) }}</span>
                <span class="row-arrow">↗</span>
              </RouterLink>
              <NotificationSettings :item-id="item.id" compact />
            </div>
          </section>
          <div v-else class="empty-state"><span class="empty-icon">▤</span><h2>{{ t(hasFilters ? 'No matching work items' : 'No active work items') }}</h2><p>{{ t(hasFilters ? 'Try adjusting your filters or search terms.' : 'Done and canceled work items are hidden by default. Change the status filter to see them, or create a new work item.') }}</p><PButton v-if="project.can_write && !hasFilters" @click="newItem">{{ t('Create work item') }}</PButton></div>
          <Paginator v-if="!listLoading && total > 25" :first="(page - 1) * 25" :rows="25" :total-records="total" @page="router.push({ query: { ...route.query, page: $event.page + 1 } })" />
        </template>
        <div v-else-if="!loading" class="empty-state"><span class="empty-icon">▦</span><h2>{{ t(hasProjectRoute ? 'Project not found' : 'Welcome to your workspace') }}</h2><p>{{ t(hasProjectRoute ? 'This project does not exist or you do not have access to it.' : auth.user?.role === 'administrator' ? 'A project brings your team’s work together. Create one to get started.' : 'Ask an application admin or project owner to grant you access to a project.') }}</p></div>
      </template>
      <ItemDetail v-if="itemId || resolvingTicket" :key="itemId || route.path" :item-id="itemId" :can-write="project?.can_write || false" :can-manage="project?.can_manage || false" :restrict-ticket-visibility="project?.restrict_ticket_visibility || false" :standalone="standalone" @close="closeItem" @updated="load(true)" />
      <NewItem v-if="creatingItem && project" :key="project.id" :project="project" :standalone="standalone" @close="closeItem" @toggle-view="setCreationView" @created="itemCreated" />
      <div v-else-if="creatingItem && standalone" class="empty-state"><h2>{{ t(loading ? 'Loading project…' : 'Project not found') }}</h2><p v-if="!loading">{{ t('This project does not exist or you do not have access to it.') }}</p></div>
    </main>
  </div>

  <PDialog v-model:visible="showProject" modal :header="t('Create a project')" :closable="!busy" :dismissable-mask="!busy">
      <form @submit.prevent="createProject">
        <label>{{ t('Project name') }}<InputText v-model="projectForm.name" required maxlength="150" autofocus :placeholder="t('e.g. Product development')" :disabled="busy" /></label>
        <label>{{ t('Project key') }}<InputText v-model="projectForm.key" required pattern="[A-Z][A-Z0-9]{1,9}" maxlength="10" placeholder="APP" :disabled="busy" @update:model-value="projectForm.key = projectForm.key.toUpperCase()" /><small>{{ t('2–10 uppercase letters or numbers, starting with a letter.') }}</small></label>
        <p class="hint">{{ t('Project URL') }}: /{{ projectForm.key || 'KEY' }}/ · {{ t('Ticket URL') }}: /{{ projectForm.key || 'KEY' }}/123</p>
        <label>{{ t('Description') }}<PTextarea v-model="projectForm.description" rows="3" :disabled="busy" /></label>
        <p class="hint">{{ t('Only assigned project members and application admins can access this project.') }}</p>
        <PMessage v-if="error" severity="error">{{ t(error) }}</PMessage><footer><PButton type="button" severity="secondary" outlined :disabled="busy" @click="showProject = false">{{ t('Cancel') }}</PButton><PButton type="submit" :loading="busy" :disabled="busy">{{ t('Create project') }}</PButton></footer>
      </form>
  </PDialog>
  <ProjectSettings v-if="showSettings && project?.can_manage" :key="project.id" :project="project" @close="closeSettings" @labels-updated="load" @milestones-updated="load(true)" @permissions-updated="load" @updated="updated => projects = projects.map(p => p.id === updated.id ? updated : p)" />
</template>

<style scoped>
@layer app {
  .item-list-entry { display: flex; align-items: center; border-bottom: 1px solid var(--border); padding-right: 12px; }
  .item-list-entry .item-row { flex: 1; min-width: 0; border-bottom: 0; }
  .item-list-metadata { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 5px; color: var(--muted); font-size: 11px; overflow-wrap: anywhere; }
  .work-item-toolbar { padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--subtle); }
  .list-caption { gap: 12px; padding: 12px 0 8px; }
  .list-caption-info { display: flex; flex: 1 1 0; flex-wrap: wrap; align-items: center; column-gap: 12px; }
  .work-item-sort { display: flex; flex: 0 1 auto; min-width: 0; }
  .sort-field {
    align-items: center;
    width: 176px;
    min-width: 0;
    min-height: 44px;
    border-start-end-radius: 0;
    border-end-end-radius: 0;
  }
  .sort-direction {
    flex: 0 0 44px;
    min-height: 44px;
    margin-inline-start: -1px;
    padding: 0;
    border-color: var(--border);
    border-start-start-radius: 0;
    border-end-start-radius: 0;
    background: var(--surface);
    color: var(--accent);
  }
  .sort-direction:hover { background: var(--accent-soft); }
  .sort-field:hover, .sort-field:focus-within, .sort-direction:focus-visible { z-index: 1; }
}
</style>
