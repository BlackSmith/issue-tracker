<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ name: string; src?: string | null }>()
const failed = ref(false)
watch(() => props.src, () => { failed.value = false })
</script>

<template>
  <span class="avatar" aria-hidden="true">
    <img v-if="src && !failed" :src="src" alt="" @error="failed = true" />
    <template v-else>{{ name.trim().charAt(0).toUpperCase() }}</template>
  </span>
</template>

<style scoped>
.avatar { overflow: hidden; }
img { width: 100%; height: 100%; object-fit: cover; }
</style>
