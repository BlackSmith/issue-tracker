<script setup lang="ts">
import { auth } from '../api'
import type { Project } from '../types'
import { t } from '../i18n'

defineProps<{ projects: Project[]; projectId?: string; loading?: boolean; canCreateProject?: boolean; settingsActive?: boolean }>()
const emit = defineEmits<{ createProject: [] }>()
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-heading">{{ t('WORKSPACE') }}</div>
    <div class="sidebar-heading project-heading">{{ t('PROJECTS') }} <PButton v-if="canCreateProject" class="quiet" @click="emit('createProject')" :aria-label="t('Create project')">+</PButton></div>
    <nav :aria-label="t('Projects')"><RouterLink v-for="p in projects" :key="p.id" :to="`/${p.slug}/`" class="project-link" :class="{ active: p.id === projectId }"><span class="project-icon"><img v-if="p.logo_url" :src="p.logo_url" alt="" /><template v-else>{{ p.key.slice(0, 2) }}</template></span><span>{{ p.name }}<small>{{ p.visibility === 'private' ? t('Private project') : p.key }}</small></span></RouterLink></nav>
    <p v-if="!projects.length && !loading" class="sidebar-empty">{{ t('Your projects will appear here.') }}</p>
    <RouterLink v-if="auth.user?.role === 'administrator'" to="/admin/settings" class="project-link application-settings-link" :class="{ active: settingsActive }" :aria-current="settingsActive ? 'page' : undefined"><span aria-hidden="true">⚙</span><span>{{ t('Organization settings') }}</span></RouterLink>
    <div class="sidebar-footer"><span class="green-dot"></span> {{ t('Connected to your workspace') }}<a href="/api/v1/docs" target="_blank" rel="noopener">{{ t('API documentation ↗') }}</a></div>
  </aside>
</template>

<style scoped>
.project-icon { flex-shrink: 0; aspect-ratio: 1; overflow: hidden; }
.project-icon img { display: block; width: 100%; height: 100%; object-fit: contain; }
.application-settings-link { margin-top: auto; margin-bottom: 16px; font-size: 12px; }
.application-settings-link + .sidebar-footer { margin-top: 0; padding-top: 12px; }
@media (max-width: 720px) {
  .application-settings-link { margin-top: 8px; margin-bottom: 0; width: fit-content; }
}
</style>
