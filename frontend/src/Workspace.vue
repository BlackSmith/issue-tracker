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
const q = ref(''), status = ref(''), label = ref(''), sort = ref('updated')
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
    q.value = String(route.query.q || ''); status.value = String(route.query.status || '')
    label.value = String(route.query.label || ''); sort.value = String(route.query.sort || 'updated')
    if (projectId.value && !standalone.value) {
      const definitions = await api<LabelDefinition[]>(`/projects/${projectId.value}/labels`)
      if (current !== sequence) return
      labels.value = definitions
      const params = new URLSearchParams({ q: q.value, sort: sort.value, page: String(page.value) })
      if (status.value) params.set('status', status.value)
      if (label.value) params.set('label', label.value)
      const result = await api<{ items: WorkItem[]; total: number }>(`/projects/${projectId.value}/items?${params}`)
      if (current !== sequence) return
      items.value = result.items; total.value = result.total
    }
  } catch (e) { if (current === sequence) error.value = (e as Error).message }
  finally { if (current === sequence) loading.value = false }
}
onMounted(load)
watch(() => route.fullPath, load)

function filter(reset = true) {
  const query: Record<string, string> = {}
  if (q.value) query.q = q.value
  if (status.value) query.status = status.value
  if (label.value) query.label = label.value
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
    <aside class="sidebar">
      <div class="sidebar-heading">WORKSPACE</div><RouterLink to="/" class="workspace-link">▦ <span>Organization</span></RouterLink>
      <div class="sidebar-heading project-heading">PROJECTS <button v-if="auth.user?.role === 'administrator'" class="quiet" @click="showProject = true" aria-label="Create project">+</button></div>
      <nav aria-label="Projects"><RouterLink v-for="p in projects" :key="p.id" :to="`/${p.slug}/`" class="project-link" :class="{ active: p.id === projectId }"><span class="project-icon">{{ p.key.slice(0, 2) }}</span><span>{{ p.name }}<small>{{ p.visibility === 'private' ? 'Private project' : p.key }}</small></span></RouterLink></nav>
      <p v-if="!projects.length && !loading" class="sidebar-empty">Your projects will appear here.</p>
      <div class="sidebar-footer"><span class="green-dot"></span> Connected to your workspace<a href="/api/v1/docs" target="_blank" rel="noopener">API documentation ↗</a></div>
    </aside>
    <main class="main-content" :class="{ 'standalone-content': standalone }">
      <div v-if="error" class="error banner" role="alert">{{ error }}<button class="quiet" @click="error = ''" aria-label="Dismiss error">×</button></div>
      <template v-if="!standalone">
        <div class="breadcrumbs">Organization <span>/</span> {{ project?.name || 'Projects' }}</div>
        <header class="page-heading"><div><span class="eyebrow">{{ project?.key || 'YOUR WORKSPACE' }}</span><h1>Work items <span v-if="project" class="count">{{ total }}</span></h1><p>{{ project?.description || 'Track ideas, move work forward, and keep everyone in the loop.' }}</p></div><div class="heading-actions"><button v-if="project && auth.user?.role === 'administrator'" @click="showSettings = true">⚙ Settings</button><button v-if="project?.can_write" class="primary" @click="newItem">＋ New work item</button><button v-else-if="!projects.length && auth.user?.role === 'administrator'" class="primary" @click="showProject = true">＋ Create project</button></div></header>
        <template v-if="project">
          <form class="filters" @submit.prevent="filter()"><label class="search-field"><span>⌕</span><input v-model="q" aria-label="Search work items" placeholder="Search work items…" type="search" /><kbd>↵</kbd></label><select v-model="status" @change="filter()" aria-label="Filter by status"><option value="">All statuses</option><option v-for="s in statuses" :key="s">{{ s }}</option></select><select v-model="label" class="label-filter" aria-label="Filter by label" @change="filter()"><option value="">All labels</option><option v-if="label && !labels.some(tag => tag.name === label)" :value="label">{{ label }}</option><option v-for="tag in labels" :key="tag.id" :value="tag.name">{{ tag.name }}</option></select><select v-model="sort" @change="filter()" aria-label="Sort work items"><option value="updated">Last updated</option><option value="created">Newest first</option><option value="title">Title A–Z</option></select><button type="submit" class="quiet">Apply</button></form>
          <div class="list-caption"><span>{{ total }} work {{ total === 1 ? 'item' : 'items' }}</span><button v-if="q || status || label" class="quiet" @click="q = ''; status = ''; label = ''; filter()">Clear filters</button></div>
          <div v-if="loading" class="empty-state">Loading work items…</div>
          <section v-else-if="items.length" class="item-list" aria-label="Work items"><RouterLink v-for="item in items" :key="item.id" class="item-row" :to="{ path: item.web_url, query: { ...route.query, view: 'panel' } }"><span class="status-icon" :class="item.status.toLowerCase().replace(' ', '-')">{{ item.status === 'Done' ? '✓' : item.status === 'Canceled' ? '−' : '◉' }}</span><span class="item-info"><strong>{{ item.title }}</strong><span class="item-meta">{{ item.reference }} <span>·</span> {{ item.type }} <span>·</span> {{ item.status }} <span v-if="item.due_date">· Due {{ item.due_date }}</span></span><span v-if="item.labels.length" class="labels"><LabelBadge v-for="tag in item.labels" :key="tag" :name="tag" :definition="labels.find(label => label.name === tag)" /></span></span><span class="priority" :class="item.priority.toLowerCase()">{{ item.priority }}</span><span class="row-arrow">↗</span></RouterLink></section>
          <div v-else class="empty-state"><span class="empty-icon">▤</span><h2>{{ q || status || label ? 'No matching work items' : 'A clear space for your next idea' }}</h2><p>{{ q || status || label ? 'Try adjusting your filters or search terms.' : 'Create your first work item to start moving things forward.' }}</p><button v-if="project.can_write && !q && !status && !label" class="primary" @click="newItem">Create work item</button></div>
          <footer v-if="total > 25" class="pagination"><button :disabled="page <= 1" @click="router.push({ query: { ...route.query, page: page - 1 } })">← Previous</button><span>Page {{ page }} of {{ Math.ceil(total / 25) }}</span><button :disabled="page * 25 >= total" @click="router.push({ query: { ...route.query, page: page + 1 } })">Next →</button></footer>
        </template>
        <div v-else-if="!loading" class="empty-state"><span class="empty-icon">▦</span><h2>{{ hasProjectRoute ? 'Project not found' : 'Welcome to your workspace' }}</h2><p>{{ hasProjectRoute ? 'This project does not exist or you do not have access to it.' : 'A project brings your team’s work together. Create one to get started.' }}</p></div>
      </template>
      <div v-if="ticketRoute && !itemId && loading" class="empty-state">Loading work item…</div>
      <ItemDetail v-if="itemId" :key="itemId" :item-id="itemId" :can-write="project?.can_write || false" :standalone="standalone" @close="closeItem" @updated="load" />
      <NewItem v-if="creatingItem && project" :key="project.id" :project="project" :standalone="standalone" @close="closeItem" @toggle-view="setCreationView" @created="itemCreated" />
      <div v-else-if="creatingItem && standalone" class="empty-state"><h2>{{ loading ? 'Loading project…' : 'Project not found' }}</h2><p v-if="!loading">This project does not exist or you do not have access to it.</p></div>
    </main>
  </div>

  <div v-if="showProject" class="modal-backdrop" @click.self="showProject = false">
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="project-heading">
      <form @submit.prevent="createProject">
        <header><h2 id="project-heading">Create a project</h2><button type="button" class="quiet" @click="showProject = false" aria-label="Close">×</button></header>
        <label>Project name<input v-model="projectForm.name" required maxlength="150" autofocus placeholder="e.g. Product development" /></label>
        <label>Project key<input v-model="projectForm.key" required pattern="[A-Z][A-Z0-9]{1,9}" maxlength="10" placeholder="APP" @input="projectForm.key = projectForm.key.toUpperCase()" /><small>2–10 uppercase letters or numbers, starting with a letter.</small></label>
        <label>Project URL slug<input v-model="projectForm.slug" maxlength="100" pattern="[a-z0-9]+(-[a-z0-9]+)*" placeholder="Automatically generated from the name" /><small>Optional. Used in ticket URLs such as /product-development/123. Lowercase letters, numbers, and hyphens.</small></label>
        <label>Description<textarea v-model="projectForm.description" rows="3" /></label>
        <label>Visibility<select v-model="projectForm.visibility"><option value="organization">Organization — visible to all members</option><option value="private">Private — project members only</option></select></label>
        <p v-if="error" class="error">{{ error }}</p><footer><button type="button" @click="showProject = false">Cancel</button><button class="primary" :disabled="busy">{{ busy ? 'Creating…' : 'Create project' }}</button></footer>
      </form>
    </section>
  </div>
  <ProjectSettings v-if="showSettings && project" :key="project.id" :project="project" @close="showSettings = false" @labels-updated="load" @updated="updated => projects = projects.map(p => p.id === updated.id ? updated : p)" />
</template>
