<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import { t } from '../i18n'
import LanguagePicker from './LanguagePicker.vue'
const props = defineProps<{ token: string }>()
const emit = defineEmits<{ done: [] }>()
const password = ref(''), confirmation = ref(''), error = ref(''), busy = ref(false), saved = ref(false)
async function save() {
  error.value = ''
  if (password.value !== confirmation.value) { error.value = 'Passwords do not match'; return }
  busy.value = true
  try {
    await api('/auth/password/setup', { method: 'POST', body: JSON.stringify({ token: props.token, password: password.value }) })
    password.value = ''; confirmation.value = ''; saved.value = true
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
</script>
<template>
  <main class="login-page"><section class="login-card">
    <LanguagePicker /><h1>{{ t('Set your password') }}</h1>
    <PMessage v-if="error" severity="error">{{ t(error) }}</PMessage>
    <template v-if="saved"><PMessage severity="success">{{ t('Your password has been set. You can now sign in.') }}</PMessage><PButton @click="emit('done')">{{ t('Continue to sign in') }}</PButton></template>
    <form v-else-if="token" @submit.prevent="save">
      <p>{{ t('Choose a password with at least 12 characters. The link can only be used once.') }}</p>
      <label>{{ t('New password') }}<InputText v-model="password" type="password" autocomplete="new-password" required minlength="12" maxlength="128" :disabled="busy" /></label>
      <label>{{ t('Confirm password') }}<InputText v-model="confirmation" type="password" autocomplete="new-password" required minlength="12" maxlength="128" :disabled="busy" /></label>
      <PButton type="submit" :loading="busy" :disabled="busy">{{ t('Set password') }}</PButton>
    </form>
    <template v-else><p>{{ t('The password link is missing. Open the complete link from your email, or ask your administrator to send a new one.') }}</p><PButton @click="emit('done')">{{ t('Back to sign in') }}</PButton></template>
  </section></main>
</template>
