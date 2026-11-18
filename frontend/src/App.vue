<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api, auth, refreshAuth, signOut } from './api'
import UserAvatar from './components/UserAvatar.vue'
import PasswordSetup from './components/PasswordSetup.vue'
import { useRoute, useRouter } from 'vue-router'
import { t } from './i18n'
import LanguagePicker from './components/LanguagePicker.vue'

const error = ref('')
const route = useRoute(), router = useRouter()
const setupToken = ref(new URLSearchParams(window.location.hash.slice(1)).get('token') || '')
watch(() => route.hash, hash => {
  const token = new URLSearchParams(hash.slice(1)).get('token')
  if (route.query.password_setup && token) {
    setupToken.value = token
    router.replace({ path: '/', query: { password_setup: '1' }, hash: '' })
  }
})
const email = ref(''), password = ref(''), loggingIn = ref(false)
const signingOut = ref(false)
const providers = ref<{ id: string; name: string; url: string | null }[]>([])
onMounted(async () => {
  if (setupToken.value) await router.replace({ path: '/', query: { password_setup: '1' }, hash: '' })
  try {
    await refreshAuth()
    providers.value = await api('/auth/providers')
  } catch (e) { error.value = (e as Error).message }
})
async function passwordLogin() {
  loggingIn.value = true; error.value = ''
  try {
    await api('/auth/password/login', { method: 'POST', body: JSON.stringify({ email: email.value, password: password.value }) })
    password.value = ''
    await refreshAuth()
  } catch (e) { error.value = (e as Error).message }
  finally { loggingIn.value = false }
}
async function logout() {
  if (signingOut.value) return
  signingOut.value = true; error.value = ''
  try { await signOut() }
  catch (e) { error.value = (e as Error).message }
  finally { signingOut.value = false }
}
</script>

<template>
  <PMessage v-if="error" severity="error" closable @close="error = ''">{{ t(error) }}</PMessage>
  <div v-if="!auth.ready" class="login-page"><p>{{ t(error ? 'Unable to connect to the API. Please try refreshing.' : 'Loading your workspace…') }}</p></div>
  <PasswordSetup v-else-if="route.query.password_setup" :key="setupToken" :token="setupToken" @done="setupToken = ''; router.replace('/')" />
  <div v-else-if="!auth.user" class="login-page">
    <div class="login-card">
      <div class="brand-mark">▣</div><span class="eyebrow">ISSUE TRACKER</span>
      <LanguagePicker />
      <h1>{{ t('Good work starts') }}<br>{{ t('with a clear view.') }}</h1>
      <p>{{ t("One place for your team's ideas, issues, and next steps.") }}</p>
      <p v-if="$route.query.auth_error" class="error" role="alert">{{ t('Sign-in could not be verified. Please start again.') }}</p>
      <form v-if="providers.some(p => p.id === 'password')" @submit.prevent="passwordLogin">
        <label>{{ t('Email') }}<InputText v-model="email" type="email" autocomplete="username" required :disabled="loggingIn" /></label>
        <label>{{ t('Password') }}<InputText v-model="password" type="password" autocomplete="current-password" required maxlength="1024" :disabled="loggingIn" /></label>
        <PButton type="submit" :loading="loggingIn" :disabled="loggingIn">{{ t('Sign in') }}</PButton>
        <p class="hint">{{ t('Forgot your password? Contact your administrator.') }}</p>
      </form>
      <template v-for="provider in providers" :key="provider.id"><PButton v-if="provider.url" as="a" :href="provider.url" class="login-button">{{ t('Continue with {provider}', { provider: provider.name }) }} <span>→</span></PButton></template>
      <p v-if="!providers.length" class="error">{{ t('No sign-in provider is configured. Contact your administrator.') }}</p>
      <small>{{ t('Access is managed by your organization.') }}</small>
    </div>
  </div>
  <div v-else-if="!auth.user.role && $route.path !== '/settings'" class="login-page">
    <div class="login-card"><LanguagePicker /><h1>{{ t("You're signed in.") }}</h1><p>{{ t('Your account does not have organization membership yet. Ask an administrator to grant access.') }}</p><RouterLink to="/settings" class="button">{{ t('Personal settings') }}</RouterLink> <PButton :disabled="signingOut" :loading="signingOut" @click="logout">{{ t('Sign out') }}</PButton></div>
  </div>
  <div v-else class="app-shell">
    <header class="topbar">
      <RouterLink to="/" class="brand"><span>▣</span> Issue Tracker</RouterLink>
      <span class="topbar-note">{{ t("Your team's work, in focus") }}</span>
      <div class="account">
        <RouterLink to="/settings" class="account-profile" :aria-label="t('Open personal settings')" :title="t('Personal settings')">
          <UserAvatar :name="auth.user.name" :src="auth.user.avatar_url" />
          <span class="account-name">{{ auth.user.name }}<small>{{ t(auth.user.role || 'Pending membership') }}</small></span>
          <span class="settings-icon" aria-hidden="true">⚙</span>
        </RouterLink>
        <PButton class="quiet on-dark" :disabled="signingOut" :loading="signingOut" @click="logout">{{ t('Sign out') }}</PButton>
      </div>
    </header>
    <RouterView :key="auth.user.id" />
  </div>
</template>
