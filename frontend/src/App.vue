<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, auth, refreshAuth } from './api'
import UserAvatar from './components/UserAvatar.vue'

const error = ref('')
const providers = ref<{ id: string; name: string; url: string }[]>([])
onMounted(async () => {
  try {
    await refreshAuth()
    providers.value = await api('/auth/providers')
  } catch (e) { error.value = (e as Error).message }
})
async function logout() {
  try { await api('/auth/logout', { method: 'POST' }); await refreshAuth() }
  catch (e) { error.value = (e as Error).message }
}
</script>

<template>
  <div v-if="error" class="global-error" role="alert">{{ error }} <button @click="error = ''" aria-label="Dismiss error">×</button></div>
  <div v-if="!auth.ready" class="login-page"><p>{{ error ? 'Unable to connect to the API. Please try refreshing.' : 'Loading your workspace…' }}</p></div>
  <div v-else-if="!auth.user" class="login-page">
    <div class="login-card">
      <div class="brand-mark">▣</div><span class="eyebrow">ISSUE TRACKER</span>
      <h1>Good work starts<br>with a clear view.</h1>
      <p>One place for your team's ideas, issues, and next steps.</p>
      <p v-if="$route.query.auth_error" class="error" role="alert">Sign-in could not be verified. Please start again.</p>
      <a v-for="provider in providers" :key="provider.id" :href="provider.url" class="button primary login-button">Continue with {{ provider.name }} <span>→</span></a>
      <p v-if="!providers.length" class="error">No sign-in provider is configured. Contact your administrator.</p>
      <small>Access is managed by your organization.</small>
    </div>
  </div>
  <div v-else-if="!auth.user.role && $route.path !== '/settings'" class="login-page">
    <div class="login-card"><h1>You're signed in.</h1><p>Your account does not have organization membership yet. Ask an administrator to grant access.</p><RouterLink to="/settings" class="button">Personal settings</RouterLink> <button @click="logout">Sign out</button></div>
  </div>
  <div v-else class="app-shell">
    <header class="topbar">
      <RouterLink to="/" class="brand"><span>▣</span> Issue Tracker</RouterLink>
      <span class="topbar-note">Your team's work, in focus</span>
      <RouterLink v-if="auth.user.role === 'administrator'" to="/admin/organization" class="bots-link">Organization settings</RouterLink>
      <RouterLink v-if="auth.user.role === 'administrator'" to="/admin/bots" class="bots-link" aria-label="Bot accounts">Bots</RouterLink>
      <div class="account">
        <RouterLink to="/settings" class="account-profile" aria-label="Open personal settings" title="Personal settings">
          <UserAvatar :name="auth.user.name" :src="auth.user.avatar_url" />
          <span class="account-name">{{ auth.user.name }}<small>{{ auth.user.role || 'Pending membership' }}</small></span>
          <span class="settings-icon" aria-hidden="true">⚙</span>
        </RouterLink>
        <button class="quiet on-dark" @click="logout">Sign out</button>
      </div>
    </header>
    <RouterView />
  </div>
</template>
