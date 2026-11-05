<script setup lang="ts">
import type { LabelDefinition } from '../types'
defineProps<{ name: string; definition?: LabelDefinition; tooltip?: string }>()
</script>

<template>
  <span class="tag" :title="tooltip ?? definition?.description" :style="{ borderLeft: `5px solid ${definition?.color || '#16a34a'}` }">{{ name }}</span>
</template>
