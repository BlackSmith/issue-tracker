<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { t } from '../i18n'

const props = defineProps<{ title: string; busy?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const headingId = useId()
const panel = ref<HTMLElement | null>(null)
let previousFocus: HTMLElement | null = null
function close() { if (!props.busy) emit('close') }
function onEscape(event: KeyboardEvent) {
  // Let an open select consume Escape before considering the surrounding panel.
  if (event.target instanceof Element && event.target.closest('[role="combobox"][aria-expanded="true"]')) return
  event.preventDefault()
  event.stopPropagation()
  close()
}
onMounted(() => {
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  panel.value?.focus()
})
onBeforeUnmount(() => { if (previousFocus?.isConnected) previousFocus.focus() })
</script>

<template>
  <Teleport to="body">
    <div class="panel-shade" @click="close"></div>
    <section ref="panel" class="detail-panel settings-detail-panel" role="dialog" :aria-labelledby="headingId" :aria-busy="busy" tabindex="-1" @keydown.esc.capture="onEscape">
      <header class="detail-top"><h2 :id="headingId">{{ title }}</h2><PButton type="button" class="quiet" :disabled="busy" :aria-label="t('Close settings detail')" :title="t('Close panel')" @click="close">×</PButton></header>
      <div class="detail-body"><slot /></div>
    </section>
  </Teleport>
</template>

<style scoped>
.settings-detail-panel { outline: none; }
.settings-detail-panel .detail-top { gap: 12px; }
.settings-detail-panel .detail-top h2 { margin: 0; overflow-wrap: anywhere; }
</style>
