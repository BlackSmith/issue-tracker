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
  <main v-else-if="!auth.user" class="sign-in-page">
    <section class="sign-in-story" aria-labelledby="sign-in-intro">
      <div class="sign-in-brand"><img src="/logo.svg" width="40" height="40" alt="" /><span>Issue Tracker</span></div>
      <div class="sign-in-intro">
        <p class="sign-in-kicker">{{ t("Your team's work, in focus") }}</p>
        <h1 id="sign-in-intro">{{ t('Good work starts') }}<br><span>{{ t('with a clear view.') }}</span></h1>
        <p class="sign-in-description">{{ t("One place for your team's ideas, issues, and next steps.") }}</p>
        <div class="work-illustration" aria-hidden="true">
          <div class="illustration-heading"><i></i><span></span><b></b></div>
          <div v-for="row in 3" :key="row" class="illustration-row" :class="{ 'is-complete': row === 3 }">
            <svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" /><path v-if="row === 3" d="m8 12 3 3 5-6" /><path v-else-if="row === 2" d="M12 7v5l3 2" /></svg>
            <div><span></span><span></span></div><i></i>
          </div>
        </div>
      </div>
      <p class="sign-in-story-footer">{{ t('Ideas, organized. Progress, shared.') }}</p>
    </section>
    <section class="sign-in-access" aria-labelledby="sign-in-title">
      <div class="sign-in-language"><LanguagePicker /></div>
      <div class="sign-in-form">
      <div class="sign-in-form-mark"><img src="/logo.svg" width="48" height="48" alt="" /></div>
      <h2 id="sign-in-title">{{ t('Sign in') }}</h2>
      <p class="sign-in-subtitle">{{ t('Continue to your workspace.') }}</p>
      <p v-if="$route.query.auth_error" class="error" role="alert">{{ t('Sign-in could not be verified. Please start again.') }}</p>
      <form v-if="providers.some(p => p.id === 'password')" @submit.prevent="passwordLogin">
        <label>{{ t('Email') }}<InputText v-model="email" type="email" autocomplete="username" required :disabled="loggingIn" /></label>
        <label>{{ t('Password') }}<InputText v-model="password" type="password" autocomplete="current-password" required maxlength="1024" :disabled="loggingIn" /></label>
        <PButton class="sign-in-submit" type="submit" :loading="loggingIn" :disabled="loggingIn">{{ t('Sign in') }}</PButton>
        <p class="hint">{{ t('Forgot your password? Contact your administrator.') }}</p>
      </form>
      <div v-if="providers.some(p => p.id === 'password') && providers.some(p => p.url)" class="sign-in-divider"><span>{{ t('or') }}</span></div>
      <div class="sign-in-providers">
        <template v-for="provider in providers" :key="provider.id"><PButton v-if="provider.url" as="a" :href="provider.url" class="sign-in-provider" :outlined="providers.some(p => p.id === 'password')">{{ t('Continue with {provider}', { provider: provider.name }) }} <span aria-hidden="true">→</span></PButton></template>
      </div>
      <p v-if="!providers.length" class="error">{{ t('No sign-in provider is configured. Contact your administrator.') }}</p>
      <p class="sign-in-note"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="6" y="10" width="12" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>{{ t('Access is managed by your organization.') }}</p>
      </div>
    </section>
  </main>
  <div v-else-if="!auth.user.role && $route.path !== '/settings'" class="login-page">
    <div class="login-card"><LanguagePicker /><h1>{{ t("You're signed in.") }}</h1><p>{{ t('Your account does not have organization membership yet. Ask an administrator to grant access.') }}</p><RouterLink to="/settings" class="button">{{ t('Personal settings') }}</RouterLink> <PButton :disabled="signingOut" :loading="signingOut" @click="logout">{{ t('Sign out') }}</PButton></div>
  </div>
  <div v-else class="app-shell">
    <header class="topbar">
      <RouterLink to="/" class="brand"><img class="brand-logo" src="/logo.svg" width="32" height="32" alt="" /> Issue Tracker</RouterLink>
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

<style scoped>
.brand-logo { display: block; flex-shrink: 0; background: #fff; border-radius: 9px; }
.brand-mark img { display: block; margin: 0 auto; }
.sign-in-page { min-height: 100vh; min-height: 100svh; display: grid; grid-template-columns: 1fr 1fr; background: #fff; color: #283630; }
.sign-in-story { padding: 48px clamp(36px, 5vw, 88px) 30px; display: flex; flex-direction: column; background: #edf4ef; position: relative; overflow: hidden; }
.sign-in-story::before { content: ''; position: absolute; width: 580px; height: 580px; border: 1px solid #26734d0d; border-radius: 50%; left: -260px; bottom: -380px; box-shadow: 0 0 0 70px #26734d04, 0 0 0 140px #26734d03; pointer-events: none; }
.sign-in-brand { display: flex; align-items: center; gap: 12px; font-size: 19px; font-weight: 650; letter-spacing: -.5px; }
.sign-in-intro { margin: auto 0; padding: 64px 0 44px; max-width: 480px; position: relative; }
.sign-in-kicker { color: #46745a; font-size: 12px; font-weight: 600; letter-spacing: .5px; margin-bottom: 22px; }
.sign-in-intro h1 { font-size: clamp(34px, 3.5vw, 54px); font-weight: 650; line-height: 1.15; letter-spacing: -1.8px; margin-bottom: 24px; }
.sign-in-intro h1 span { color: #26734d; }
.sign-in-description { max-width: 340px; font-size: 16px; line-height: 1.8; color: #596e60; }
.work-illustration { max-width: 380px; margin-top: 42px; padding: 20px; border: 1px solid #d9e6dc; border-radius: 14px; background: #ffffffb8; box-shadow: 0 16px 40px #244d3010; transform: rotate(-2deg); }
.illustration-heading { display: flex; align-items: center; gap: 8px; padding-bottom: 18px; }
.illustration-heading i { width: 8px; height: 8px; background: #26734d; border-radius: 50%; }
.illustration-heading span { height: 6px; width: 90px; background: #a4bcad; border-radius: 4px; }
.illustration-heading b { margin-left: auto; width: 28px; height: 6px; background: #e0e9e2; border-radius: 4px; }
.illustration-row { display: flex; align-items: center; gap: 12px; padding: 14px 0; border-top: 1px solid #e6ede8; }
.illustration-row svg { width: 21px; height: 21px; flex-shrink: 0; stroke: #9aaa9f; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
.illustration-row > div { flex: 1; }
.illustration-row div span { display: block; width: 80%; height: 6px; background: #b7c7bc; border-radius: 4px; }
.illustration-row div span + span { width: 45%; height: 4px; margin-top: 8px; background: #e0e8e2; }
.illustration-row > i { width: 36px; height: 15px; border-radius: 5px; background: #e9eee9; }
.illustration-row:nth-child(3) > i { background: #ede5cc; }
.illustration-row.is-complete svg { stroke: #26734d; }
.illustration-row.is-complete > i { background: #d6e9db; }
.sign-in-story-footer { color: #596e60; font-size: 12px; margin: 0; position: relative; }
.sign-in-access { display: flex; flex-direction: column; padding: 32px clamp(28px, 5vw, 88px); }
.sign-in-language { align-self: flex-end; }
.sign-in-language :deep(.language-picker) { margin: 0; }
.sign-in-form { width: 100%; max-width: 360px; margin: auto; padding: 56px 0 96px; }
.sign-in-form-mark { margin-bottom: 24px; }
.sign-in-form-mark img { display: block; }
.sign-in-form h2 { font-size: 30px; letter-spacing: -.8px; margin-bottom: 10px; }
.sign-in-subtitle { color: #647168; line-height: 1.6; margin-bottom: 32px; }
.sign-in-form form { margin: 0; }
.sign-in-form label { font-size: 13px; margin-bottom: 20px; }
.sign-in-form .hint { margin: 14px 0 0; color: #647168; }
.sign-in-providers { display: grid; gap: 12px; }
.sign-in-providers:empty { display: none; }
.sign-in-note { display: flex; align-items: flex-start; gap: 8px; color: #647168; font-size: 12px; line-height: 1.6; margin: 28px 0 0; }
.sign-in-note svg { width: 16px; height: 18px; flex-shrink: 0; stroke: currentColor; stroke-width: 1.5; }
.sign-in-divider { display: flex; align-items: center; gap: 14px; margin: 24px 0; color: #647168; font-size: 12px; }
.sign-in-divider::before, .sign-in-divider::after { content: ''; height: 1px; background: #e3eae5; flex: 1; }
@layer app {
  .sign-in-submit, .sign-in-provider { width: 100%; min-height: 46px; border-radius: 8px; }
  .sign-in-provider { justify-content: space-between; text-decoration: none; padding: 12px 16px; }
  .sign-in-form input { min-height: 44px; border-radius: 8px; }
}
@media (min-width: 1600px) { .sign-in-story { align-items: center; } .sign-in-brand, .sign-in-story-footer { width: 480px; } }
@media (max-width: 900px) {
  .sign-in-story { padding: 32px; }
  .sign-in-intro h1 { font-size: 36px; }
  .sign-in-access { padding: 24px 32px; }
}
@media (max-width: 640px) {
  .sign-in-page { grid-template-columns: 1fr; }
  .sign-in-story { padding: 28px 24px; }
  .sign-in-brand { font-size: 17px; }
  .sign-in-brand img { width: 32px; height: 32px; }
  .sign-in-intro { padding: 32px 0 0; max-width: none; }
  .sign-in-kicker, .work-illustration, .sign-in-story-footer { display: none; }
  .sign-in-intro h1 { font-size: 32px; letter-spacing: -1px; margin-bottom: 14px; }
  .sign-in-description { font-size: 14px; line-height: 1.6; margin-bottom: 0; max-width: 340px; }
  .sign-in-access { padding: 20px 24px 36px; }
  .sign-in-form { padding: 20px 0 0; }
  .sign-in-form-mark { display: none; }
  .sign-in-form h2 { font-size: 26px; }
  .sign-in-subtitle { margin-bottom: 24px; }
}
</style>
