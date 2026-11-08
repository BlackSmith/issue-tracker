<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { api, auth } from './api'
import { accentOptions, applyTheme, backgroundOptions, defaultAppearance } from './theme'
import type { User } from './types'
import UserAvatar from './components/UserAvatar.vue'
import TokenManager from './components/TokenManager.vue'

const form = reactive({
  name: auth.user?.name || '',
  email: auth.user?.email || '',
  theme_accent: auth.user?.theme_accent || defaultAppearance.theme_accent,
  theme_background: auth.user?.theme_background || defaultAppearance.theme_background,
})
const error = ref(''), success = ref(''), saving = ref(false), avatarBusy = ref(false)
const avatarInput = ref<HTMLInputElement | null>(null)
const busy = computed(() => saving.value || avatarBusy.value)
const dirty = computed(() => auth.user && Object.entries(form).some(([key, value]) => value !== auth.user![key as keyof User]))

watch(() => [form.theme_accent, form.theme_background], () => {
  applyTheme(form)
  success.value = ''
})
onBeforeUnmount(() => applyTheme(auth.user))

async function save() {
  saving.value = true; error.value = ''; success.value = ''
  try {
    auth.user = await api<User>('/users/me', { method: 'PUT', body: JSON.stringify(form) })
    Object.assign(form, { name: auth.user.name, email: auth.user.email })
    applyTheme(auth.user)
    success.value = 'Your settings have been saved.'
  } catch (e) { error.value = (e as Error).message }
  finally { saving.value = false }
}
function discard() {
  if (!auth.user) return
  Object.assign(form, {
    name: auth.user.name, email: auth.user.email,
    theme_accent: auth.user.theme_accent, theme_background: auth.user.theme_background,
  })
  error.value = ''; success.value = ''
  applyTheme(auth.user)
}
async function uploadAvatar(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  error.value = ''; success.value = ''
  if (file.size > 5 * 1024 * 1024) {
    error.value = 'Profile pictures must be smaller than 5 MB'
    if (avatarInput.value) avatarInput.value.value = ''
    return
  }
  const data = new FormData()
  data.append('file', file)
  avatarBusy.value = true
  try {
    auth.user = await api<User>('/users/me/avatar', { method: 'PUT', body: data })
    success.value = 'Your profile picture has been updated.'
  } catch (e) { error.value = (e as Error).message }
  finally {
    avatarBusy.value = false
    if (avatarInput.value) avatarInput.value.value = ''
  }
}
async function removeAvatar() {
  avatarBusy.value = true; error.value = ''; success.value = ''
  try {
    auth.user = await api<User>('/users/me/avatar', { method: 'DELETE' })
    success.value = 'Your profile picture has been removed.'
  } catch (e) { error.value = (e as Error).message }
  finally { avatarBusy.value = false }
}
</script>

<template>
  <main class="settings-page">
    <div class="breadcrumbs"><RouterLink to="/">Workspace</RouterLink><span>/</span> Personal settings</div>
    <header class="page-heading"><div><span class="eyebrow">YOUR ACCOUNT</span><h1>Personal settings</h1><p>Make your profile and workspace feel like you.</p></div></header>
    <form class="settings-form" @submit.prevent="save">
      <section class="settings-card" aria-labelledby="profile-heading">
        <header><h2 id="profile-heading">Profile</h2><p>Your name and picture appear beside your comments and activity.</p></header>
        <div class="profile-picture-row">
          <UserAvatar class="profile-picture" :name="form.name || auth.user?.name || '?'" :src="auth.user?.avatar_url" />
          <div>
            <div class="profile-picture-actions">
              <PButton type="button" severity="secondary" outlined :disabled="busy" @click="avatarInput?.click()">{{ avatarBusy ? 'Updating…' : 'Upload picture' }}</PButton>
              <PButton v-if="auth.user?.avatar_url" type="button" class="quiet" :disabled="busy" @click="removeAvatar">Remove picture</PButton>
            </div>
            <p class="hint">PNG, JPEG, GIF or WebP · up to 5 MB. Cropped to a square and saved immediately.</p>
            <input ref="avatarInput" type="file" accept="image/png,image/jpeg,image/gif,image/webp" aria-label="Profile picture" hidden :disabled="busy" @change="uploadAvatar" />
          </div>
        </div>
        <div class="profile-fields">
          <label>Display name<InputText v-model="form.name" name="name" autocomplete="name" required maxlength="200" :disabled="busy" /></label>
          <label>Contact email<InputText v-model="form.email" name="email" type="email" autocomplete="email" required maxlength="320" :disabled="busy" /><small>Sign-in is managed by your identity provider. Changing this address updates your profile contact email.</small></label>
        </div>
      </section>
      <section class="settings-card" aria-labelledby="appearance-heading">
        <header><h2 id="appearance-heading">Appearance</h2><p>Preview your colors immediately. Save to keep them across sessions and devices.</p></header>
        <fieldset :disabled="busy"><legend>Interface color</legend>
          <div class="appearance-options"><PButton v-for="option in accentOptions" :key="option.id" type="button" severity="secondary" outlined :disabled="busy" :aria-pressed="form.theme_accent === option.id" @click="form.theme_accent = option.id"><span class="color-swatch" :style="{ backgroundColor: option.color }" aria-hidden="true"></span>{{ option.name }}<span class="choice-check" aria-hidden="true">{{ form.theme_accent === option.id ? '✓' : '' }}</span></PButton></div>
        </fieldset>
        <fieldset :disabled="busy"><legend>Application background</legend>
          <div class="appearance-options background-options"><PButton v-for="option in backgroundOptions" :key="option.id" type="button" severity="secondary" outlined :disabled="busy" :aria-pressed="form.theme_background === option.id" @click="form.theme_background = option.id"><span class="color-swatch" :style="{ backgroundColor: option.color }" aria-hidden="true"></span>{{ option.name }}<span class="choice-check" aria-hidden="true">{{ form.theme_background === option.id ? '✓' : '' }}</span></PButton></div>
        </fieldset>
        <PButton type="button" class="quiet" :disabled="busy" @click="Object.assign(form, defaultAppearance)">Reset appearance to default</PButton>
      </section>
      <div class="settings-status" aria-live="polite"><PMessage v-if="error" severity="error">{{ error }}</PMessage><PMessage v-if="success" severity="success">{{ success }}</PMessage></div>
      <footer class="settings-footer"><span>{{ dirty ? 'You have unsaved changes.' : 'Your preferences are up to date.' }}</span><div><PButton type="button" severity="secondary" outlined :disabled="busy || !dirty" @click="discard">Discard changes</PButton><PButton type="submit" :loading="saving" :disabled="busy || !dirty">Save settings</PButton></div></footer>
    </form>
    <TokenManager v-if="auth.user?.role" :owner-role="auth.user.role" />
    <section v-if="auth.user?.role === 'administrator'" class="settings-card automation-settings"><h2>Automation accounts</h2><p class="hint">Give integrations and AI tools a dedicated bot identity with explicit project access.</p><RouterLink to="/admin/settings?tab=bots" class="button">Manage bot accounts →</RouterLink></section>
  </main>
</template>

<style scoped>
.settings-page { max-width: 1000px; margin: 0 auto; padding: 30px 40px 50px; }
.settings-page .page-heading h1 { margin-bottom: 10px; }
.settings-card { border: 1px solid var(--border); background: var(--surface); border-radius: 10px; padding: 26px; margin-bottom: 22px; }
.automation-settings { margin-top: 28px; }
.settings-card > header { border-bottom: 1px solid var(--border); padding-bottom: 17px; margin-bottom: 24px; }
.settings-card h2 { margin-bottom: 7px; }
.settings-card header p { color: var(--muted); font-size: 12px; line-height: 1.7; margin: 0; }
.profile-picture-row { display: flex; align-items: center; gap: 22px; margin-bottom: 26px; }
.profile-picture { width: 82px; height: 82px; font-size: 30px; }
.profile-picture-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.profile-picture-row .hint { margin: 8px 0 0; max-width: 440px; }
.profile-fields { max-width: 560px; }
.profile-fields label:last-child { margin-bottom: 0; }
.profile-fields small { line-height: 1.7; }
fieldset { border: 0; padding: 0; margin: 0 0 25px; min-width: 0; }
legend { font-weight: 550; font-size: 13px; margin-bottom: 12px; }
.appearance-options { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.appearance-options button { justify-content: flex-start; gap: 10px; font-size: 12px; padding: 12px; min-width: 0; }
.appearance-options button[aria-pressed="true"] { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
.color-swatch { width: 22px; height: 22px; flex-shrink: 0; border: 1px solid #00000015; border-radius: 50%; }
.background-options .color-swatch { border-radius: 5px; }
.choice-check { min-width: 12px; margin-left: auto; }
.settings-status p { margin-bottom: 16px; }
.success-message { border: 1px solid #c2e1cd; background: #edf8f1; color: #276d45; border-radius: 6px; padding: 12px; font-size: 12px; }
.settings-footer { display: flex; justify-content: space-between; align-items: center; gap: 15px; }
.settings-footer > span { color: var(--muted); font-size: 11px; }
.settings-footer > div { display: flex; gap: 8px; }
@media (max-width: 720px) {
  .settings-page { padding: 23px 16px 35px; }
  .settings-card { padding: 18px; }
  .profile-picture-row { gap: 14px; align-items: flex-start; }
  .profile-picture { width: 60px; height: 60px; font-size: 24px; }
  .profile-picture-actions button { font-size: 11px; }
  .appearance-options { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .settings-footer { align-items: stretch; flex-direction: column; }
  .settings-footer > div { justify-content: flex-end; }
}
</style>
