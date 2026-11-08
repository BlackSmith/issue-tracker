<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, auth } from './api'
import type { LabelDefinition, Project, WorkItem } from './types'
import LabelBadge from './components/LabelBadge.vue'
import { statuses } from './types'
import ItemDetail from './components/ItemDetail.vue'
import ProjectSettings from './components/ProjectSettings.vue'
import NewItem from './components/NewItem.vue'
import WorkspaceSidebar from './components/WorkspaceSidebar.vue'
import { defaultStatuses, isDefaultStatusFilter, readFilterValues, statusFilterQuery } from './itemFilters'

const route = useRoute(), router = useRouter()
const projects = ref<Project[]>([]), items = ref<WorkItem[]>([]), total = ref(0)
const labels = ref<LabelDefinition[]>([])
const loading = ref(true), error = ref(''), busy = ref(false)
const showProject = ref(false), showSettings = ref(false)
const projectForm = ref({ key: '', name: '', slug: '', description: '', visibility: 'organization' })
const resolvedItem = ref<WorkItem | null>(null), resolvedPath = ref('')
const projectId = computed(() => String(route.params.projectId
  || projects.value.find(p => p.slug === route.params.projectSlug)?.id
  || (resolvedPath.value === route.path ? resolvedItem.value?.project_id : '') || ''))
const project = computed(() => projects.value.find(p => p.id === projectId.value))
const projectPath = computed(() => project.value ? `/${project.value.slug}/` : '/')
const hasProjectRoute = computed(() => !!route.params.projectSlug || !!route.params.projectId)
const itemId = computed(() => resolvedPath.value === route.path ? resolvedItem.value?.id || '' : '')
const ticketRoute = computed(() => !!route.params.itemNumber || !!route.params.itemId)
const creatingItem = computed(() => route.name === 'new-item')
const standalone = computed(() => (ticketRoute.value || creatingItem.value) && route.query.view !== 'panel')
const q = ref(''), status = ref<string[]>([...defaultStatuses]), label = ref<string[]>([]), sort = ref('updated')
const hasFilters = computed(() => !!q.value || !isDefaultStatusFilter(status.value) || label.value.length > 0)
const labelOptions = computed(() => [...new Set([...labels.value.map(tag => tag.name), ...label.value])])
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
        await router.replace({ path: item.web_url, query: route.query })
        return
      }
      resolvedItem.value = item
      resolvedPath.value = route.path
    } else if (route.params.itemId || route.query.item) {
      const oldId = String(route.params.itemId || route.query.item)
      const item = await api<WorkItem>(`/items/${encodeURIComponent(oldId)}`)
      if (current !== sequence) return
      if (route.params.projectId && item.project_id !== route.params.projectId) throw new Error('Work item not found in this project')
      if (route.params.projectSlug && item.project_slug !== route.params.projectSlug) throw new Error('Work item not found in this project')
      const query = { ...route.query }
      if (query.item) { delete query.item; query.view = 'panel' }
      await router.replace({ path: item.web_url, query })
      return
    }
    if (current !== sequence) return
    if (route.params.projectId) {
      if (!project.value) throw new Error('Project not found')
      await router.replace({ path: projectPath.value, query: route.query, hash: route.hash })
      return
    }
    if (hasProjectRoute.value && !project.value) throw new Error('Project not found')
    if (route.path === '/' && projects.value.length) {
      await router.replace({ path: `/${projects.value[0]!.slug}/`, query: route.query, hash: route.hash })
      return
    }
    q.value = String(route.query.q || ''); status.value = readFilterValues(route.query.status, defaultStatuses)
    label.value = readFilterValues(route.query.label); sort.value = String(route.query.sort || 'updated')
    if (projectId.value && !standalone.value) {
      const definitions = await api<LabelDefinition[]>(`/projects/${projectId.value}/labels`)
      if (current !== sequence) return
      labels.value = definitions
      const params = new URLSearchParams({ q: q.value, sort: sort.value, page: String(page.value) })
      status.value.forEach(value => params.append('status', value))
      label.value.forEach(value => params.append('label', value))
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
  if (!reset && page.value > 1) query.page = String(page.value)
  router.push({ path: projectPath.value, query })
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
    const created = await api<Project>('/projects', { method: 'POST', body: JSON.stringify({ ...projectForm.value, slug: projectForm.value.slug || null }) })
    showProject.value = false; projectForm.value = { key: '', name: '', slug: '', description: '', visibility: 'organization' }
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
      <PMessage v-if="error" severity="error" closable @close="error = ''">{{ error }}</PMessage>
      <template v-if="!standalone">
        <div class="breadcrumbs">Organization <span>/</span> {{ project?.name || 'Projects' }}</div>
        <header class="page-heading"><div><span class="eyebrow">{{ project?.key || 'YOUR WORKSPACE' }}</span><h1>Work items <span v-if="project" class="count">{{ total }}</span></h1><p>{{ project?.description || 'Track ideas, move work forward, and keep everyone in the loop.' }}</p></div><div class="heading-actions"><PButton v-if="project?.can_manage" severity="secondary" outlined @click="showSettings = true">⚙ Settings</PButton><PButton v-if="project?.can_write" @click="newItem">＋ New work item</PButton><PButton v-else-if="!projects.length && auth.user?.role === 'administrator'" @click="showProject = true">＋ Create project</PButton></div></header>
        <template v-if="project">
          <form class="filters" @submit.prevent="filter()">
            <label class="search-field"><span>⌕</span><InputText v-model="q" aria-label="Search work items" placeholder="Search work items…" type="search" /><kbd>↵</kbd></label>
            <MultiSelect :model-value="status" :options="statuses" placeholder="All statuses" :max-selected-labels="2" selected-items-label="{0} statuses selected" show-clear @update:model-value="status = $event || []" @change="filter()" aria-label="Filter by status">
              <template #option="{ option }"><span class="filter-option"><span class="status-icon" :class="option.toLowerCase().replace(' ', '-')" aria-hidden="true">{{ option === 'Done' ? '✓' : option === 'Canceled' ? '−' : '◉' }}</span>{{ option }}</span></template>
            </MultiSelect>
            <MultiSelect :model-value="label" class="label-filter" :options="labelOptions" placeholder="All labels" :max-selected-labels="1" selected-items-label="{0} labels selected" filter show-clear @update:model-value="label = $event || []" @change="filter()" aria-label="Filter by label">
              <template #option="{ option }"><span class="filter-option"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M3 3h7l11 11-7 7L3 10Z" /><circle cx="7.5" cy="7.5" r="1" /></svg><LabelBadge :name="option" :definition="labels.find(tag => tag.name === option)" /></span></template>
            </MultiSelect>
            <PSelect v-model="sort" :options="[{ label: 'Last updated', value: 'updated' }, { label: 'Newest first', value: 'created' }, { label: 'Title A–Z', value: 'title' }]" option-label="label" option-value="value" @change="filter()" aria-label="Sort work items" />
            <PButton type="submit" class="quiet">Apply</PButton>
          </form>
          <div class="list-caption"><span>{{ total }} work {{ total === 1 ? 'item' : 'items' }}</span><PButton v-if="hasFilters" class="quiet" @click="q = ''; status = [...defaultStatuses]; label = []; filter()">Reset filters</PButton></div>
          <div v-if="loading" class="empty-state">Loading work items…</div>
          <section v-else-if="items.length" class="item-list" aria-label="Work items"><RouterLink v-for="item in items" :key="item.id" class="item-row" :to="{ path: item.web_url, query: { ...route.query, view: 'panel' } }"><span class="status-icon" :class="item.status.toLowerCase().replace(' ', '-')">{{ item.status === 'Done' ? '✓' : item.status === 'Canceled' ? '−' : '◉' }}</span><span class="item-info"><strong>{{ item.title }}</strong><span class="item-meta">{{ item.reference }} <span>·</span> {{ item.type }} <span>·</span> {{ item.status }} <span v-if="item.due_date">· Due {{ item.due_date }}</span></span><span v-if="item.labels.length" class="labels"><LabelBadge v-for="tag in item.labels" :key="tag" :name="tag" :definition="labels.find(label => label.name === tag)" /></span></span><span class="priority" :class="item.priority.toLowerCase()">{{ item.priority }}</span><span class="row-arrow">↗</span></RouterLink></section>
          <div v-else class="empty-state"><span class="empty-icon">▤</span><h2>{{ hasFilters ? 'No matching work items' : 'No active work items' }}</h2><p>{{ hasFilters ? 'Try adjusting your filters or search terms.' : 'Done and canceled work items are hidden by default. Change the status filter to see them, or create a new work item.' }}</p><PButton v-if="project.can_write && !hasFilters" @click="newItem">Create work item</PButton></div>
          <Paginator v-if="total > 25" :first="(page - 1) * 25" :rows="25" :total-records="total" @page="router.push({ query: { ...route.query, page: $event.page + 1 } })" />
        </template>
        <div v-else-if="!loading" class="empty-state"><span class="empty-icon">▦</span><h2>{{ hasProjectRoute ? 'Project not found' : 'Welcome to your workspace' }}</h2><p>{{ hasProjectRoute ? 'This project does not exist or you do not have access to it.' : 'A project brings your team’s work together. Create one to get started.' }}</p></div>
      </template>
      <div v-if="ticketRoute && !itemId && loading" class="empty-state">Loading work item…</div>
      <ItemDetail v-if="itemId" :key="itemId" :item-id="itemId" :can-write="project?.can_write || false" :standalone="standalone" @close="closeItem" @updated="load" />
      <NewItem v-if="creatingItem && project" :key="project.id" :project="project" :standalone="standalone" @close="closeItem" @toggle-view="setCreationView" @created="itemCreated" />
      <div v-else-if="creatingItem && standalone" class="empty-state"><h2>{{ loading ? 'Loading project…' : 'Project not found' }}</h2><p v-if="!loading">This project does not exist or you do not have access to it.</p></div>
    </main>
  </div>

  <PDialog v-model:visible="showProject" modal header="Create a project" :closable="!busy" :dismissable-mask="!busy">
      <form @submit.prevent="createProject">
        <label>Project name<InputText v-model="projectForm.name" required maxlength="150" autofocus placeholder="e.g. Product development" :disabled="busy" /></label>
        <label>Project key<InputText v-model="projectForm.key" required pattern="[A-Z][A-Z0-9]{1,9}" maxlength="10" placeholder="APP" :disabled="busy" @update:model-value="projectForm.key = projectForm.key.toUpperCase()" /><small>2–10 uppercase letters or numbers, starting with a letter.</small></label>
        <label>Project URL slug<InputText v-model="projectForm.slug" maxlength="100" pattern="[a-z0-9]+(-[a-z0-9]+)*" placeholder="Automatically generated from the name" :disabled="busy" /><small>Optional. Used in ticket URLs such as /product-development/123. Lowercase letters, numbers, and hyphens.</small></label>
        <label>Description<PTextarea v-model="projectForm.description" rows="3" :disabled="busy" /></label>
        <label>Visibility<SelectButton v-model="projectForm.visibility" :options="[{ label: 'Organization', value: 'organization' }, { label: 'Private', value: 'private' }]" option-label="label" option-value="value" :allow-empty="false" aria-label="Visibility" :disabled="busy" /><small>Organization: visible to all organization members. Private: project members only.</small></label>
        <PMessage v-if="error" severity="error">{{ error }}</PMessage><footer><PButton type="button" severity="secondary" outlined :disabled="busy" @click="showProject = false">Cancel</PButton><PButton type="submit" :loading="busy" :disabled="busy">Create project</PButton></footer>
      </form>
  </PDialog>
  <ProjectSettings v-if="showSettings && project?.can_manage" :key="project.id" :project="project" @close="showSettings = false" @labels-updated="load" @permissions-updated="load" @updated="updated => projects = projects.map(p => p.id === updated.id ? updated : p)" />
</template>
