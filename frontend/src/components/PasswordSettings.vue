<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, refreshAuth } from '../api'
import { t } from '../i18n'
const account = ref<{ enabled: boolean; login_email: string | null }>()
const current = ref(''), password = ref(''), confirmation = ref(''), error = ref(''), success = ref(''), busy = ref(false)
onMounted(async () => {
  try { account.value = await api('/auth/password/account') }
  catch (e) { error.value = (e as Error).message }
})
async function save() {
  error.value = ''; success.value = ''
  if (password.value !== confirmation.value) { error.value = 'Passwords do not match'; return }
  busy.value = true
  try {
    await api('/auth/password/change', { method: 'POST', body: JSON.stringify({ current_password: current.value, password: password.value }) })
    current.value = ''; password.value = ''; confirmation.value = ''
    await refreshAuth()
    success.value = 'Password changed. Other browser sessions have been signed out.'
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
</script>
<template>
  <section v-if="account?.login_email || error" class="settings-card">
    <h2>{{ t('Password') }}</h2><PMessage v-if="error" severity="error">{{ t(error) }}</PMessage><PMessage v-if="success" severity="success">{{ t(success) }}</PMessage>
    <p>{{ t('Sign-in email: {email}. Contact your administrator to change it or request a password reset.', { email: account?.login_email || '' }) }}</p>
    <form v-if="account?.enabled" @submit.prevent="save">
      <label>{{ t('Current password') }}<InputText v-model="current" type="password" autocomplete="current-password" required maxlength="1024" :disabled="busy" /></label>
      <label>{{ t('New password') }}<InputText v-model="password" type="password" autocomplete="new-password" required minlength="12" maxlength="128" :disabled="busy" /></label>
      <label>{{ t('Confirm new password') }}<InputText v-model="confirmation" type="password" autocomplete="new-password" required minlength="12" maxlength="128" :disabled="busy" /></label>
      <PButton type="submit" :disabled="busy" :loading="busy">{{ t('Change password') }}</PButton>
    </form>
  </section>
</template>
