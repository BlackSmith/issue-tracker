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
const form = ref({ name: props.project.name, description: props.project.description, visibility: props.project.visibility, default_access: props.project.default_access, restrict_ticket_visibility: props.project.restrict_ticket_visibility })
const logoInput = ref<HTMLInputElement | null>(null)

async function uploadLogo(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const body = new FormData()
  body.append('file', file)
  busy.value = true; error.value = ''; message.value = ''
  try {
    emit('updated', await api<Project>(`/projects/${props.project.id}/logo`, { method: 'PUT', body }))
    message.value = 'Project logo saved.'
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false; input.value = '' }
}

async function removeLogo() {
  busy.value = true; error.value = ''; message.value = ''
  try {
    emit('updated', await api<Project>(`/projects/${props.project.id}/logo`, { method: 'DELETE' }))
    message.value = 'Project logo removed.'
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}

async function save() {
  busy.value = true; error.value = ''; message.value = ''
  try {
    const updated = await api<Project>(`/projects/${props.project.id}`, { method: 'PUT', body: JSON.stringify(form.value) })
    form.value = { name: updated.name, description: updated.description, visibility: updated.visibility, default_access: updated.default_access, restrict_ticket_visibility: updated.restrict_ticket_visibility }
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
        <section class="project-logo-settings" :aria-label="t('Project logo')">
          <h3>{{ t('Project logo') }}</h3>
          <div class="project-logo-controls">
            <span class="project-logo-preview"><img v-if="project.logo_url" :src="project.logo_url" :alt="t('Project logo')" /><span v-else>{{ project.key.slice(0, 2) }}</span></span>
            <PButton type="button" severity="secondary" outlined :disabled="busy" @click="logoInput?.click()">{{ t('Upload logo') }}</PButton>
            <PButton v-if="project.logo_url" type="button" severity="secondary" text :disabled="busy" @click="removeLogo">{{ t('Remove logo') }}</PButton>
            <input ref="logoInput" type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden :disabled="busy" :aria-label="t('Upload project logo')" @change="uploadLogo" />
          </div>
          <p class="hint">{{ t('PNG, JPEG, GIF or WebP, up to 5 MB. The logo is saved immediately; its proportions are preserved.') }}</p>
        </section>
        <label>{{ t('Description') }}<PTextarea v-model="form.description" rows="4" maxlength="10000" :disabled="busy" /></label>
        <label>{{ t('Default access') }}<PSelect v-model="form.default_access" :options="[{ label: t('No default access'), value: null }, { label: t('Reporter'), value: 'reporter' }, { label: t('Read-only'), value: 'read-only' }]" option-label="label" option-value="value" :placeholder="t('No default access')" :aria-label="t('Default access')" :disabled="busy" /></label>
        <p class="hint">{{ t('Applies to all active application members without an explicit project role. Explicit roles take precedence. Application admins remain Owners; bots require explicit access.') }}</p>
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
.project-logo-controls { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.project-logo-preview { display: inline-flex; align-items: center; justify-content: center; flex: 0 0 64px; width: 64px; height: 64px; aspect-ratio: 1; overflow: hidden; border: 1px solid var(--border); border-radius: 8px; background: var(--subtle); color: var(--accent); font-weight: 650; }
.project-logo-preview img { display: block; width: 100%; height: 100%; object-fit: contain; }
</style>
