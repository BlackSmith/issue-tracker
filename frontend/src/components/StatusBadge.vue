<script setup lang="ts">
import { t } from '../i18n'

defineProps<{ status: string; iconOnly?: boolean }>()
const classes: Record<string, string> = { Open: 'open', 'In progress': 'in-progress', Done: 'done', Canceled: 'canceled' }
</script>

<template>
  <span class="work-item-status" :class="[classes[status], { 'icon-only': iconOnly }]" :title="t(status)"
    :role="iconOnly ? 'img' : undefined" :aria-label="iconOnly ? t(status) : undefined">
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="10" cy="10" r="7.5" />
      <path v-if="status === 'In progress'" d="M10 5a5 5 0 0 1 0 10Z" fill="currentColor" stroke="none" />
      <path v-else-if="status === 'Done'" d="m6.5 10 2.3 2.3 4.7-4.6" />
      <path v-else-if="status === 'Canceled'" d="m5 15 10-10" />
    </svg>
    <span v-if="!iconOnly">{{ t(status) }}</span>
  </span>
</template>

<style scoped>
@layer app {
  .work-item-status { display: inline-flex; align-items: center; gap: 5px; max-width: 100%; padding: 3px 7px; border-radius: 4px; font-size: 11px; font-weight: 550; line-height: 1.4; color: #596579; background: #eef1f5; vertical-align: middle; }
  .work-item-status.open { color: #24704a; background: #e9f5ed; }
  .work-item-status.in-progress { color: #245fa6; background: #eaf2fc; }
  .work-item-status.done { color: #6941a5; background: #f2ebfa; }
  .work-item-status.canceled { color: #596579; background: #eef1f5; }
  .work-item-status svg { width: 16px; height: 16px; flex-shrink: 0; }
  .work-item-status > span { min-width: 0; overflow-wrap: anywhere; }
  .work-item-status.icon-only { padding: 0; background: transparent; flex-shrink: 0; }
  .work-item-status.icon-only svg { width: 20px; height: 20px; }
}
</style>
