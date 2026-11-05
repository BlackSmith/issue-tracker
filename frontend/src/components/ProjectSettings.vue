<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import type { Project } from '../types'
import ProjectMembers from './ProjectMembers.vue'
import LabelManager from './LabelManager.vue'

const props = defineProps<{ project: Project }>()
const emit = defineEmits<{ close: []; updated: [project: Project]; labelsUpdated: [] }>()
const tab = ref('general'), busy = ref(false), error = ref(''), message = ref('')
const form = ref({ name: props.project.name, description: props.project.description, visibility: props.project.visibility })

async function save() {
  busy.value = true; error.value = ''; message.value = ''
  try {
    const updated = await api<Project>(`/projects/${props.project.id}`, { method: 'PUT', body: JSON.stringify(form.value) })
    form.value = { name: updated.name, description: updated.description, visibility: updated.visibility }
    emit('updated', updated)
    message.value = 'Project settings saved.'
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="!busy && emit('close')" @keydown.esc.stop="!busy && emit('close')">
    <section class="modal project-settings-modal" role="dialog" aria-modal="true" aria-labelledby="project-settings-heading" :aria-busy="busy">
      <header><div><h2 id="project-settings-heading">Project settings</h2><p class="hint">{{ project.name }}</p></div><button type="button" class="quiet" :disabled="busy" aria-label="Close project settings" @click="emit('close')">×</button></header>
      <nav class="settings-tabs" aria-label="Project settings sections">
        <button type="button" :class="{ primary: tab === 'general' }" :aria-pressed="tab === 'general'" :disabled="busy" @click="tab = 'general'">General</button>
        <button type="button" :class="{ primary: tab === 'members' }" :aria-pressed="tab === 'members'" :disabled="busy" @click="tab = 'members'">Members</button>
        <button type="button" :class="{ primary: tab === 'labels' }" :aria-pressed="tab === 'labels'" @click="tab = 'labels'">Labels</button>
      </nav>
      <form v-show="tab === 'general'" @submit.prevent="save">
        <label>Project name<input v-model="form.name" required maxlength="150" :disabled="busy" /></label>
        <label>Description<textarea v-model="form.description" rows="4" maxlength="10000" :disabled="busy" /></label>
        <label>Visibility<select v-model="form.visibility" :disabled="busy"><option value="organization">Organization — visible to all members</option><option value="private">Private — project members only</option></select></label>
        <p class="hint">Private projects are accessible only to explicit project members and organization administrators. Bots always require explicit membership.</p>
        <div class="form-grid"><label>Project key<input :value="project.key" readonly /></label><label>Project URL<input :value="`/${project.slug}/`" readonly /></label></div>
        <p class="hint">The project key and URL stay stable when you rename the project.</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="message" class="hint" role="status">{{ message }}</p>
        <footer><button type="button" :disabled="busy" @click="emit('close')">Close</button><button class="primary" :disabled="busy">{{ busy ? 'Saving…' : 'Save changes' }}</button></footer>
      </form>
      <ProjectMembers v-if="tab === 'members'" :project="project" embedded />
      <LabelManager v-if="tab === 'labels'" :project-id="project.id" @updated="emit('labelsUpdated')" />
    </section>
  </div>
</template>

<style scoped>
.project-settings-modal { width: 780px; max-width: 100%; }
.project-settings-modal > header { align-items: flex-start; }
.project-settings-modal > header h2 { margin-bottom: 4px; }
.settings-tabs { display: flex; gap: 8px; padding-bottom: 20px; margin-bottom: 20px; border-bottom: 1px solid var(--border); }
</style>
