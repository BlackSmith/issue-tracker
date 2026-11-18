<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, auth } from './api'
import type { Assignee, LabelDefinition, Project, WorkItem } from './types'
import LabelBadge from './components/LabelBadge.vue'
import StatusBadge from './components/StatusBadge.vue'
import WorkItemFilters, { type FilterKey, type Filters } from './components/WorkItemFilters.vue'
import ItemDetail from './components/ItemDetail.vue'
import ProjectSettings from './components/ProjectSettings.vue'
import NewItem from './components/NewItem.vue'
import WorkspaceSidebar from './components/WorkspaceSidebar.vue'
import { defaultStatuses, isDefaultStatusFilter, readFilterValues, statusFilterQuery } from './itemFilters'
import { dateOnly, itemCount, t } from './i18n'

const route = useRoute(), router = useRouter()
const projects = ref<Project[]>([]), items = ref<WorkItem[]>([]), total = ref(0)
const labels = ref<LabelDefinition[]>([])
const assignees = ref<Assignee[]>([])
const loading = ref(true), error = ref(''), busy = ref(false)
const showProject = ref(false), showSettings = ref(false)
const projectForm = ref({ key: '', name: '', description: '', visibility: 'private' })
const resolvedItem = ref<WorkItem | null>(null), resolvedPath = ref('')
const projectId = computed(() => String(route.params.projectId
  || projects.value.find(p => p.slug === route.params.projectSlug)?.id
  || projects.value.find(p => p.legacy_slug === route.params.projectSlug)?.id
  || (resolvedPath.value === route.path ? resolvedItem.value?.project_id : '') || ''))
const project = computed(() => projects.value.find(p => p.id === projectId.value))
const projectPath = computed(() => project.value ? `/${project.value.slug}/` : '/')
const hasProjectRoute = computed(() => !!route.params.projectSlug || !!route.params.projectId)
const itemId = computed(() => resolvedPath.value === route.path ? resolvedItem.value?.id || '' : '')
const ticketRoute = computed(() => !!route.params.itemNumber || !!route.params.itemId)
const creatingItem = computed(() => route.name === 'new-item')
const standalone = computed(() => (ticketRoute.value || creatingItem.value) && route.query.view !== 'panel')
const q = ref(''), status = ref<string[]>([...defaultStatuses]), label = ref<string[]>([]), sort = ref('updated')
const priority = ref<string[]>([]), type = ref<string[]>([]), assignee = ref<string[]>([]), direction = ref('desc')
const sortOptions = computed(() => [
  { label: 'Updated date', value: 'updated' }, { label: 'Created date', value: 'created' },
  { label: 'Title', value: 'title' }, { label: 'Priority', value: 'priority' }, { label: 'Due date', value: 'due_date' },
].map(option => ({ ...option, label: t(option.label) })))
const filters = computed<Filters>(() => ({ status: status.value, label: label.value, priority: priority.value, type: type.value, assignee: assignee.value }))
const hasFilters = computed(() => !!q.value || !isDefaultStatusFilter(status.value) || label.value.length > 0 || priority.value.length > 0 || type.value.length > 0 || assignee.value.length > 0)
const page = computed(() => Number(route.query.page) || 1)
let sequence = 0

async function load() {
  const current = ++sequence
  loading.value = true; error.value = ''
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
    direction.value = String(route.query.direction || defaultDirection(sort.value))
    if (projectId.value && !standalone.value) {
      const [definitions, people] = await Promise.all([
        api<LabelDefinition[]>(`/projects/${projectId.value}/labels`),
        api<Assignee[]>(`/projects/${projectId.value}/item-assignees`),
      ])
      if (current !== sequence) return
      labels.value = definitions
      assignees.value = people
      const params = new URLSearchParams({ q: q.value, sort: sort.value, direction: direction.value, page: String(page.value) })
      status.value.forEach(value => params.append('status', value))
      label.value.forEach(value => params.append('label', value))
      for (const key of ['priority', 'type', 'assignee'] as const) filters.value[key].forEach(value => params.append(key, value))
      const result = await api<{ items: WorkItem[]; total: number }>(`/projects/${projectId.value}/items?${params}`)
      if (current !== sequence) return
      items.value = result.items; total.value = result.total
    }
  } catch (e) { if (current === sequence) error.value = (e as Error).message }
  finally { if (current === sequence) loading.value = false }
}
onMounted(load)
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
  for (const key of ['priority', 'type', 'assignee'] as const) if (filters.value[key].length) query[key] = filters.value[key]
  if (!reset && page.value > 1) query.page = String(page.value)
  router.push({ path: projectPath.value, query })
}
function defaultDirection(value: string) { return ['title', 'due_date'].includes(value) ? 'asc' : 'desc' }
function changeFilter(key: FilterKey, values: string[]) {
  const targets = { status, label, priority, type, assignee }
  targets[key].value = values
  filter()
}
function changeSort() { direction.value = defaultDirection(sort.value); filter() }
function resetFilters() {
  q.value = ''; status.value = [...defaultStatuses]; label.value = []; priority.value = []; type.value = []; assignee.value = []
  filter()
}
function closeItem() {
  const query = { ...route.query }
  delete query.view
  delete query.item
  router.push({ path: projectPath.value, query })
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
  <div class="workspace" :class="{ 'with-detail-panel': (itemId || (creatingItem && project)) && !standalone }">
    <WorkspaceSidebar :projects="projects" :project-id="projectId" :loading="loading" :can-create-project="auth.user?.role === 'administrator'" @create-project="showProject = true" />
    <main class="main-content" :class="{ 'standalone-content': standalone }">
      <PMessage v-if="error" severity="error" closable @close="error = ''">{{ t(error) }}</PMessage>
      <template v-if="!standalone">
        <div class="breadcrumbs">{{ t('Organization') }} <span>/</span> {{ project?.name || t('Projects') }}</div>
        <header class="page-heading"><div><span class="eyebrow">{{ project?.key || t('YOUR WORKSPACE') }}</span><h1>{{ t('Work items') }} <span v-if="project" class="count">{{ total }}</span></h1><p>{{ project?.description || t('Track ideas, move work forward, and keep everyone in the loop.') }}</p></div><div class="heading-actions"><PButton v-if="project?.can_manage" severity="secondary" outlined @click="showSettings = true">{{ t('⚙ Settings') }}</PButton><PButton v-if="project?.can_write" @click="newItem">{{ t('＋ New work item') }}</PButton><PButton v-else-if="!projects.length && auth.user?.role === 'administrator'" @click="showProject = true">{{ t('＋ Create project') }}</PButton></div></header>
        <template v-if="project">
          <div class="work-item-toolbar">
            <WorkItemFilters v-model:query="q" :filters="filters" :labels="labels" :assignees="assignees" @change="changeFilter" @search="filter()" />
            <div class="work-item-sort">
              <PSelect v-model="sort" :options="sortOptions" option-label="label" option-value="value" @change="changeSort" :aria-label="t('Sort work items')" />
              <PButton type="button" severity="secondary" outlined :aria-label="t(direction === 'asc' ? 'Sort descending' : 'Sort ascending')" :title="t(direction === 'asc' ? 'Ascending · click to reverse' : 'Descending · click to reverse')" @click="direction = direction === 'asc' ? 'desc' : 'asc'; filter()">{{ direction === 'asc' ? '↑' : '↓' }}</PButton>
            </div>
          </div>
          <div class="list-caption"><span>{{ itemCount(total) }}</span><PButton v-if="hasFilters" class="quiet" @click="resetFilters">{{ t('Reset filters') }}</PButton></div>
          <div v-if="loading" class="empty-state">{{ t('Loading work items…') }}</div>
          <section v-else-if="items.length" class="item-list" :aria-label="t('Work items')"><RouterLink v-for="item in items" :key="item.id" class="item-row" :to="{ path: item.web_url, query: { ...route.query, view: 'panel' } }"><StatusBadge :status="item.status" icon-only /><span class="item-info"><strong>{{ item.title }}</strong><span class="item-meta">{{ item.reference }} <span>·</span> {{ t(item.type) }} <span>·</span> {{ t(item.status) }} <span v-if="item.due_date">· {{ t('Due') }} {{ dateOnly(item.due_date) }}</span></span><span v-if="item.labels.length" class="labels"><LabelBadge v-for="tag in item.labels" :key="tag" :name="tag" :definition="labels.find(label => label.name === tag)" /></span></span><span class="priority" :class="item.priority.toLowerCase()">{{ t(item.priority) }}</span><span class="row-arrow">↗</span></RouterLink></section>
          <div v-else class="empty-state"><span class="empty-icon">▤</span><h2>{{ t(hasFilters ? 'No matching work items' : 'No active work items') }}</h2><p>{{ t(hasFilters ? 'Try adjusting your filters or search terms.' : 'Done and canceled work items are hidden by default. Change the status filter to see them, or create a new work item.') }}</p><PButton v-if="project.can_write && !hasFilters" @click="newItem">{{ t('Create work item') }}</PButton></div>
          <Paginator v-if="total > 25" :first="(page - 1) * 25" :rows="25" :total-records="total" @page="router.push({ query: { ...route.query, page: $event.page + 1 } })" />
        </template>
        <div v-else-if="!loading" class="empty-state"><span class="empty-icon">▦</span><h2>{{ t(hasProjectRoute ? 'Project not found' : 'Welcome to your workspace') }}</h2><p>{{ t(hasProjectRoute ? 'This project does not exist or you do not have access to it.' : auth.user?.role === 'administrator' ? 'A project brings your team’s work together. Create one to get started.' : 'Ask an application admin or project owner to grant you access to a project.') }}</p></div>
      </template>
      <div v-if="ticketRoute && !itemId && loading" class="empty-state">{{ t('Loading work item…') }}</div>
      <ItemDetail v-if="itemId" :key="itemId" :item-id="itemId" :can-write="project?.can_write || false" :standalone="standalone" @close="closeItem" @updated="load" />
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
  <ProjectSettings v-if="showSettings && project?.can_manage" :key="project.id" :project="project" @close="showSettings = false" @labels-updated="load" @permissions-updated="load" @updated="updated => projects = projects.map(p => p.id === updated.id ? updated : p)" />
</template>

<style scoped>
@layer app {
  .work-item-toolbar { display: flex; align-items: flex-start; gap: 12px; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--subtle); }
  .work-item-sort { display: flex; gap: 6px; flex-shrink: 0; }
  .work-item-sort .p-select { width: 160px; min-height: 44px; }
  .work-item-sort .p-button { min-height: 44px; }
  .with-detail-panel .work-item-toolbar { flex-wrap: wrap; }
  .with-detail-panel .work-item-search { flex-basis: 100%; }
  .with-detail-panel .work-item-sort { margin-left: auto; }
  @media (max-width: 1100px) {
    .work-item-toolbar { flex-wrap: wrap; }
    .work-item-search { flex-basis: 100%; }
    .work-item-sort { margin-left: auto; }
  }
}
</style>
