<script setup lang="ts">
import { ref } from 'vue'
import PCheckbox from 'primevue/checkbox'
import { api } from '../api'
import type { Project } from '../types'
import ProjectMembers from './ProjectMembers.vue'
import LabelManager from './LabelManager.vue'
import { t } from '../i18n'

const props = defineProps<{ project: Project }>()
const emit = defineEmits<{ close: []; updated: [project: Project]; labelsUpdated: []; permissionsUpdated: [] }>()
const tab = ref('general'), busy = ref(false), error = ref(''), message = ref('')
const form = ref({ name: props.project.name, description: props.project.description, visibility: props.project.visibility, restrict_ticket_visibility: props.project.restrict_ticket_visibility })

async function save() {
  busy.value = true; error.value = ''; message.value = ''
  try {
    const updated = await api<Project>(`/projects/${props.project.id}`, { method: 'PUT', body: JSON.stringify(form.value) })
    form.value = { name: updated.name, description: updated.description, visibility: updated.visibility, restrict_ticket_visibility: updated.restrict_ticket_visibility }
    emit('updated', updated)
    message.value = 'Project settings saved.'
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
</script>

<template>
  <PDialog :visible="true" modal :header="t('Project settings')" class="project-settings-modal" :closable="!busy" :dismissable-mask="!busy" :close-on-escape="!busy" @update:visible="!$event && emit('close')">
      <p class="hint">{{ project.name }}</p>
      <PTabs v-model:value="tab">
        <PTabList :aria-label="t('Project settings sections')">
          <PTab value="general" :disabled="busy">{{ t('General') }}</PTab>
          <PTab value="members" :disabled="busy">{{ t('Members') }}</PTab>
          <PTab value="labels" :disabled="busy">{{ t('Labels') }}</PTab>
        </PTabList>
        <PTabPanels>
          <PTabPanel value="general">
      <form @submit.prevent="save">
        <label>{{ t('Project name') }}<InputText v-model="form.name" required maxlength="150" autofocus :disabled="busy" /></label>
        <label>{{ t('Description') }}<PTextarea v-model="form.description" rows="4" maxlength="10000" :disabled="busy" /></label>
        <p class="hint">{{ t('Only assigned project members and application admins can access this project.') }}</p>
        <label class="ticket-visibility-option"><PCheckbox v-model="form.restrict_ticket_visibility" binary :disabled="busy" input-id="restrict-ticket-visibility" /><span>{{ t('Reporters and read-only members can only see their own tickets') }}</span></label>
        <p class="hint">{{ t('Own tickets are tickets they created or are assigned to. Owners and application admins can see all tickets.') }}</p>
        <div class="form-grid"><label>{{ t('Project key') }}<InputText :model-value="project.key" readonly /></label><label>{{ t('Project URL') }}<InputText :model-value="`/${project.slug}/`" readonly /></label></div>
        <p class="hint">{{ t('The project key and URL stay stable when you rename the project.') }}</p>
        <PMessage v-if="error" severity="error">{{ t(error) }}</PMessage><PMessage v-if="message" severity="success">{{ t(message) }}</PMessage>
        <footer><PButton type="button" severity="secondary" outlined :disabled="busy" @click="emit('close')">{{ t('Close') }}</PButton><PButton type="submit" :loading="busy" :disabled="busy">{{ t('Save changes') }}</PButton></footer>
      </form>
          </PTabPanel>
          <PTabPanel value="members"><ProjectMembers v-if="tab === 'members'" :project="project" embedded @updated="emit('permissionsUpdated')" /></PTabPanel>
          <PTabPanel value="labels"><LabelManager v-if="tab === 'labels'" :project-id="project.id" @updated="emit('labelsUpdated')" /></PTabPanel>
        </PTabPanels>
      </PTabs>
  </PDialog>
</template>

<style scoped>
.project-settings-modal { width: 780px; max-width: 100%; }
.project-settings-modal > header { align-items: flex-start; }
.project-settings-modal > header h2 { margin-bottom: 4px; }
.ticket-visibility-option { display: flex; flex-direction: row; align-items: center; gap: 8px; }
</style>
