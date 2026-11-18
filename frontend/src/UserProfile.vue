<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from './api'
import type { UserReference } from './references'
import UserAvatar from './components/UserAvatar.vue'
import { t } from './i18n'

const route = useRoute()
const person = ref<UserReference | null>(null), error = ref('')
let request = 0
watch(() => route.params.userId, async id => {
  const current = ++request
  person.value = null; error.value = ''
  try {
    const result = await api<UserReference>(`/references/users/${id}`)
    if (current === request) person.value = result
  } catch (e) { if (current === request) error.value = (e as Error).message }
}, { immediate: true })
</script>

<template>
  <main class="public-profile">
    <RouterLink to="/">{{ t('← Back to workspace') }}</RouterLink>
    <section v-if="person" class="profile-card"><UserAvatar :name="person.name" :src="person.avatar_url" /><div><span class="eyebrow">{{ t(person.is_bot ? 'BOT ACCOUNT' : 'TEAM MEMBER') }}</span><h1>{{ person.name }}</h1><p>{{ t(person.role) }}</p></div></section>
    <p v-else-if="error" class="error" role="alert">{{ t(error) }}</p>
    <p v-else class="hint">{{ t('Loading profile…') }}</p>
  </main>
</template>

<style scoped>
.public-profile { max-width: 850px; margin: 0 auto; padding: 35px 20px; }
.public-profile > a { font-size: 12px; }
.profile-card { display: flex; align-items: center; gap: 25px; padding: 30px; margin-top: 25px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
.profile-card .avatar { width: 70px; height: 70px; font-size: 28px; }
.profile-card h1 { margin: 8px 0; overflow-wrap: anywhere; }
.profile-card p { color: var(--muted); text-transform: capitalize; margin-bottom: 0; }
@media(max-width: 720px) { .profile-card { padding: 20px; gap: 16px; } .profile-card h1 { font-size: 22px; } }
</style>
