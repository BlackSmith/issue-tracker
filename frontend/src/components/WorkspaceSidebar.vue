<script setup lang="ts">
import { auth } from '../api'
import type { Project } from '../types'

defineProps<{ projects: Project[]; projectId?: string; loading?: boolean; canCreateProject?: boolean; settingsActive?: boolean }>()
const emit = defineEmits<{ createProject: [] }>()
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-heading">WORKSPACE</div>
    <div class="sidebar-heading project-heading">PROJECTS <PButton v-if="canCreateProject" class="quiet" @click="emit('createProject')" aria-label="Create project">+</PButton></div>
    <nav aria-label="Projects"><RouterLink v-for="p in projects" :key="p.id" :to="`/${p.slug}/`" class="project-link" :class="{ active: p.id === projectId }"><span class="project-icon">{{ p.key.slice(0, 2) }}</span><span>{{ p.name }}<small>{{ p.visibility === 'private' ? 'Private project' : p.key }}</small></span></RouterLink></nav>
    <p v-if="!projects.length && !loading" class="sidebar-empty">Your projects will appear here.</p>
    <RouterLink v-if="auth.user?.role === 'administrator'" to="/admin/settings" class="project-link application-settings-link" :class="{ active: settingsActive }" :aria-current="settingsActive ? 'page' : undefined"><span aria-hidden="true">⚙</span><span>Organization settings</span></RouterLink>
    <div class="sidebar-footer"><span class="green-dot"></span> Connected to your workspace<a href="/api/v1/docs" target="_blank" rel="noopener">API documentation ↗</a></div>
  </aside>
</template>

<style scoped>
.application-settings-link { margin-top: auto; margin-bottom: 16px; font-size: 12px; }
.application-settings-link + .sidebar-footer { margin-top: 0; padding-top: 12px; }
@media (max-width: 720px) {
  .application-settings-link { margin-top: 8px; margin-bottom: 0; width: fit-content; }
}
</style>
