<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import { t } from '../i18n'
import { ticketRevision } from '../realtime'
import UserAvatar from './UserAvatar.vue'

const props = defineProps<{ projectId?: string; itemId?: string }>()
const route = useRoute()
interface Preference {
  enabled: boolean | null
  project_enabled?: boolean
  participants?: { id: string; name: string; avatar_url: string | null }[]
}
const preference = ref<Preference | null>(null), busy = ref(false), error = ref('')
const root = ref<HTMLElement | null>(null)
const endpoint = computed(() => props.itemId ? `/items/${props.itemId}/notifications` : `/projects/${props.projectId}/notifications`)
const enabled = computed(() => preference.value?.enabled ?? preference.value?.project_enabled ?? true)
async function load() {
  const path = endpoint.value
  try {
    const result = await api<Preference>(path)
    if (path === endpoint.value) preference.value = result
  } catch (e) { error.value = (e as Error).message }
}
async function save(value: boolean | null) {
  busy.value = true; error.value = ''
  try { preference.value = await api<Preference>(endpoint.value, { method: 'PUT', body: JSON.stringify({ enabled: value }) }) }
  catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function focusSettings() {
  if (route.hash === (props.itemId ? '#notifications' : '#project-notifications')) {
    await nextTick()
    root.value?.scrollIntoView({ block: 'center' })
    root.value?.focus({ preventScroll: true })
  }
}
onMounted(async () => { await load(); await focusSettings() })
watch(endpoint, load)
watch(ticketRevision, load)
watch(() => route.hash, focusSettings)
</script>

<template>
  <section :id="itemId ? 'notifications' : 'project-notifications'" ref="root" tabindex="-1" :aria-label="t(itemId ? 'Ticket notifications' : 'Project notifications')" class="notification-settings">
    <h3>{{ t(itemId ? 'Ticket notifications' : 'Project notifications') }}</h3>
    <PMessage v-if="error" severity="error">{{ t(error) }}</PMessage>
    <template v-if="preference">
      <p role="status">{{ t(preference.enabled === null ? enabled ? 'Following project: notifications on' : 'Following project: notifications off' : enabled ? 'Notifications on' : 'Notifications off') }}</p>
      <div class="notification-actions">
        <PButton v-if="itemId && preference.enabled === null && enabled" type="button" severity="secondary" outlined :disabled="busy" @click="save(true)">{{ t('Follow ticket') }}</PButton>
        <PButton type="button" severity="secondary" outlined :disabled="busy" @click="save(!enabled)">{{ t(enabled ? 'Turn off notifications' : 'Turn on notifications') }}</PButton>
        <PButton v-if="itemId && preference.enabled !== null" type="button" severity="secondary" text :disabled="busy" @click="save(null)">{{ t('Use project setting') }}</PButton>
      </div>
      <p class="hint">{{ t('Assignment and direct mentions may still notify you when notifications are disabled.') }}</p>
      <p v-if="itemId" class="hint">{{ t('Turning on ticket notifications subscribes you to all changes and adds you to participants.') }}</p>
      <template v-if="itemId && preference.participants">
        <h3>{{ t('Participants') }} <span class="count">{{ preference.participants.length }}</span></h3>
        <div class="detail-participants"><span v-for="person in preference.participants" :key="person.id" :title="person.name"><UserAvatar :name="person.name" :src="person.avatar_url" /></span></div>
      </template>
    </template>
  </section>
</template>

<style scoped>
.notification-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.notification-settings { scroll-margin: 24px; }
</style>
