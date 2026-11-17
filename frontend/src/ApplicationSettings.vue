<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, auth } from './api'
import type { Project } from './types'
import LabelManager from './components/LabelManager.vue'
import WorkspaceSidebar from './components/WorkspaceSidebar.vue'

const Bots = defineAsyncComponent(() => import('./Bots.vue'))
const ApplicationUsers = defineAsyncComponent(() => import('./components/ApplicationUsers.vue'))
const route = useRoute(), router = useRouter()
const projects = ref<Project[]>([]), loading = ref(true), error = ref('')
const panelId = computed(() => typeof route.query.detail === 'string' ? route.query.detail : '')
const tab = computed({
  get: () => route.query.tab === 'bots' || route.query.tab === 'users' ? route.query.tab : 'organization',
  set: (value: string) => {
    const query = { ...route.query }
    delete query.detail
    if (value === 'bots' || value === 'users') query.tab = value
    else delete query.tab
    router.push({ path: '/admin/settings', query })
  },
})
function openPanel(id: string, replace = false) {
  const location = { path: route.path, query: { ...route.query, detail: id } }
  if (replace) router.replace(location)
  else router.push(location)
}
function closePanel() {
  const query = { ...route.query }
  delete query.detail
  router.push({ path: route.path, query })
}
onMounted(async () => {
  try { projects.value = await api<Project[]>('/projects') }
  catch (e) { error.value = (e as Error).message }
  finally { loading.value = false }
})
</script>

<template>
  <div class="workspace" :class="{ 'with-detail-panel': panelId && auth.user?.role === 'administrator' }">
    <WorkspaceSidebar :projects="projects" :loading="loading" settings-active />
    <main class="main-content application-settings">
      <div class="breadcrumbs"><RouterLink to="/">Workspace</RouterLink><span>/</span> Organization settings</div>
      <header class="page-heading"><div><span class="eyebrow">APPLICATION</span><h1>Organization settings</h1><p>Manage application users, organization labels, and automation accounts.</p></div></header>
      <PMessage v-if="error" severity="error">{{ error }}</PMessage>
      <PTabs v-if="auth.user?.role === 'administrator'" v-model:value="tab">
        <PTabList aria-label="Application settings sections">
          <PTab value="organization">Organization</PTab>
          <PTab value="users">Users</PTab>
          <PTab value="bots">Bots</PTab>
        </PTabList>
        <PTabPanels>
          <PTabPanel value="organization"><h2>Labels</h2><LabelManager v-if="tab === 'organization'" :panel-id="panelId" @open="openPanel" @close="closePanel" /></PTabPanel>
          <PTabPanel value="users"><ApplicationUsers v-if="tab === 'users'" :panel-id="panelId" @open="openPanel" @close="closePanel" /></PTabPanel>
          <PTabPanel value="bots"><Bots v-if="tab === 'bots'" embedded :panel-id="panelId" @open="openPanel" @close="closePanel" /></PTabPanel>
        </PTabPanels>
      </PTabs>
      <PMessage v-else severity="error">Administrator access required.</PMessage>
    </main>
  </div>
</template>

<style scoped>
.application-settings { min-width: 0; }
</style>
