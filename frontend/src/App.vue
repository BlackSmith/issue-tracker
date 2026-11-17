<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, auth, refreshAuth, signOut } from './api'
import UserAvatar from './components/UserAvatar.vue'

const error = ref('')
const signingOut = ref(false)
const providers = ref<{ id: string; name: string; url: string }[]>([])
onMounted(async () => {
  try {
    await refreshAuth()
    providers.value = await api('/auth/providers')
  } catch (e) { error.value = (e as Error).message }
})
async function logout() {
  if (signingOut.value) return
  signingOut.value = true; error.value = ''
  try { await signOut() }
  catch (e) { error.value = (e as Error).message }
  finally { signingOut.value = false }
}
</script>

<template>
  <PMessage v-if="error" severity="error" closable @close="error = ''">{{ error }}</PMessage>
  <div v-if="!auth.ready" class="login-page"><p>{{ error ? 'Unable to connect to the API. Please try refreshing.' : 'Loading your workspace…' }}</p></div>
  <div v-else-if="!auth.user" class="login-page">
    <div class="login-card">
      <div class="brand-mark">▣</div><span class="eyebrow">ISSUE TRACKER</span>
      <h1>Good work starts<br>with a clear view.</h1>
      <p>One place for your team's ideas, issues, and next steps.</p>
      <p v-if="$route.query.auth_error" class="error" role="alert">Sign-in could not be verified. Please start again.</p>
      <PButton v-for="provider in providers" :key="provider.id" as="a" :href="provider.url" class="login-button">Continue with {{ provider.name }} <span>→</span></PButton>
      <p v-if="!providers.length" class="error">No sign-in provider is configured. Contact your administrator.</p>
      <small>Access is managed by your organization.</small>
    </div>
  </div>
  <div v-else-if="!auth.user.role && $route.path !== '/settings'" class="login-page">
    <div class="login-card"><h1>You're signed in.</h1><p>Your account does not have organization membership yet. Ask an administrator to grant access.</p><RouterLink to="/settings" class="button">Personal settings</RouterLink> <PButton :disabled="signingOut" :loading="signingOut" @click="logout">Sign out</PButton></div>
  </div>
  <div v-else class="app-shell">
    <header class="topbar">
      <RouterLink to="/" class="brand"><span>▣</span> Issue Tracker</RouterLink>
      <span class="topbar-note">Your team's work, in focus</span>
      <div class="account">
        <RouterLink to="/settings" class="account-profile" aria-label="Open personal settings" title="Personal settings">
          <UserAvatar :name="auth.user.name" :src="auth.user.avatar_url" />
          <span class="account-name">{{ auth.user.name }}<small>{{ auth.user.role || 'Pending membership' }}</small></span>
          <span class="settings-icon" aria-hidden="true">⚙</span>
        </RouterLink>
        <PButton class="quiet on-dark" :disabled="signingOut" :loading="signingOut" @click="logout">Sign out</PButton>
      </div>
    </header>
    <RouterView :key="auth.user.id" />
  </div>
</template>
