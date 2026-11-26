<script lang="ts">
import type { InjectionKey, ShallowRef } from 'vue'

interface Preference {
  enabled: boolean | null
  default_enabled?: boolean
  project_enabled?: boolean
  participants?: { id: string; name: string; avatar_url: string | null }[]
}

export const notificationPreferenceUpdate: InjectionKey<ShallowRef<{ path: string; preference: Preference } | null>> =
  Symbol('notification preference update')
</script>

<script setup lang="ts">
import { computed, inject, nextTick, onMounted, ref, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import { t } from '../i18n'
import { ticketRevision } from '../realtime'
import UserAvatar from './UserAvatar.vue'

const props = defineProps<{ projectId?: string; itemId?: string; compact?: boolean; toggleTarget?: HTMLElement | null }>()
const route = useRoute()
const preferenceUpdate = inject(notificationPreferenceUpdate, () => shallowRef(null), true)
const preference = ref<Preference | null>(null), busy = ref(false), error = ref('')
const endpoint = computed(() => props.itemId ? `/items/${props.itemId}/notifications` : `/projects/${props.projectId}/notifications`)
const anchor = computed(() => props.projectId ? 'project-notifications' : props.compact ? undefined : 'notifications')
const enabled = computed(() => preference.value?.enabled ?? preference.value?.default_enabled ?? preference.value?.project_enabled ?? true)
let loadSequence = 0

async function load() {
  const path = endpoint.value
  const sequence = ++loadSequence
  try {
    const result = await api<Preference>(path)
    if (path === endpoint.value && sequence === loadSequence) preference.value = result
  } catch (e) {
    if (path === endpoint.value && sequence === loadSequence) error.value = (e as Error).message
  }
}
async function save(value: boolean | null) {
  const path = endpoint.value
  busy.value = true; error.value = ''
  try {
    const result = await api<Preference>(path, { method: 'PUT', body: JSON.stringify({ enabled: value }) })
    preferenceUpdate.value = { path, preference: result }
  } catch (e) {
    if (path === endpoint.value) error.value = (e as Error).message
  } finally { busy.value = false }
}
async function focusSettings() {
  const id = anchor.value
  if (id && route.hash === `#${id}`) {
    await nextTick()
    const button = document.getElementById(id)
    button?.scrollIntoView({ block: 'center' })
    button?.focus({ preventScroll: true })
  }
}
onMounted(async () => { await load(); await focusSettings() })
watch(preferenceUpdate, update => {
  if (update?.path === endpoint.value) {
    loadSequence++
    preference.value = update.preference
    error.value = ''
  }
}, { flush: 'sync' })
watch(endpoint, load)
watch(ticketRevision, load)
watch(() => route.hash, focusSettings)
</script>

<template>
  <section :aria-label="t(itemId ? 'Ticket notifications' : 'Project notifications')">
    <h3 v-if="!compact">{{ t(itemId ? 'Ticket notifications' : 'Project notifications') }}</h3>
    <PMessage v-if="error" severity="error">{{ t(error) }}</PMessage>
    <template v-if="preference">
      <Teleport :to="toggleTarget ?? undefined" :disabled="!toggleTarget">
        <PButton :id="anchor" type="button" class="notification-toggle" severity="secondary" outlined :disabled="busy" :aria-pressed="enabled" :aria-label="t(itemId ? enabled ? 'Unsubscribe from ticket notifications' : 'Subscribe to ticket notifications' : enabled ? 'Unsubscribe from new ticket notifications' : 'Subscribe to new ticket notifications')" :title="t(itemId ? 'Assignment and direct mentions may still notify you when notifications are disabled.' : 'Project subscriptions notify you about newly created tickets only.')" @click="save(!enabled)">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /><path v-if="!enabled" d="m3 3 18 18" /></svg>
        </PButton>
      </Teleport>
      <p v-if="!compact" role="status">{{ t(preference.enabled === null ? enabled ? 'On by default' : 'Off by default' : enabled ? 'Notifications on' : 'Notifications off') }}</p>
      <div v-if="!compact && itemId" class="notification-actions">
        <PButton v-if="preference.enabled === null && enabled" type="button" severity="secondary" outlined :disabled="busy" @click="save(true)">{{ t('Follow ticket') }}</PButton>
        <PButton v-if="preference.enabled !== null" type="button" severity="secondary" text :disabled="busy" @click="save(null)">{{ t('Use ticket default') }}</PButton>
      </div>
      <p v-if="!compact" class="hint">{{ t('Assignment and direct mentions may still notify you when notifications are disabled.') }}</p>
      <p v-if="!compact && itemId" class="hint">{{ t('Turning on ticket notifications subscribes you to all changes and adds you to participants.') }}</p>
      <template v-if="!compact && itemId && preference.participants">
        <h3>{{ t('Participants') }} <span class="count">{{ preference.participants.length }}</span></h3>
        <div class="detail-participants"><span v-for="person in preference.participants" :key="person.id" :title="person.name"><UserAvatar :name="person.name" :src="person.avatar_url" /></span></div>
      </template>
    </template>
  </section>
</template>

<style scoped>
.notification-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.notification-toggle { scroll-margin: 24px; }
</style>
