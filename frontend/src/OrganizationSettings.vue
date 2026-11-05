<script setup lang="ts">
import { auth } from './api'
import LabelManager from './components/LabelManager.vue'
</script>

<template>
  <main class="organization-settings">
    <RouterLink to="/">← Back to workspace</RouterLink>
    <h1>Organization settings</h1>
    <template v-if="auth.user?.role === 'administrator'"><h2>Labels</h2><LabelManager /></template>
    <p v-else class="error">Administrator access required.</p>
  </main>
</template>

<style scoped>
.organization-settings { max-width: 850px; padding: 32px 20px; margin: 0 auto; }
</style>
