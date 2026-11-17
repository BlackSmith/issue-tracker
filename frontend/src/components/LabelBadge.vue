<script setup lang="ts">
import { computed } from 'vue'
import type { LabelDefinition } from '../types'
const props = defineProps<{ name: string; definition?: LabelDefinition; tooltip?: string }>()
const color = computed(() => /^#[0-9a-f]{6}$/i.test(props.definition?.color || '') ? props.definition!.color : '#16a34a')
const textColor = computed(() => {
  const channels = [1, 3, 5].map(offset => {
    const value = parseInt(color.value.slice(offset, offset + 2), 16) / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  })
  const luminance = 0.2126 * channels[0]! + 0.7152 * channels[1]! + 0.0722 * channels[2]!
  return luminance > 0.45 ? '#111111' : '#ffffff'
})
</script>

<template>
  <PTag rounded class="label-badge" :value="name" :title="tooltip ?? definition?.description" :style="{ background: color, color: textColor }" />
</template>

<style scoped>
.label-badge { max-width: 100%; padding: 2px 9px; border: 1px solid rgb(0 0 0 / 12%); font-size: 11px; font-weight: 600; line-height: 1.5; vertical-align: middle; }
.label-badge :deep(.p-tag-label) { min-width: 0; white-space: normal; overflow-wrap: anywhere; }
</style>
