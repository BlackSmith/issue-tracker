<script setup lang="ts">
import { computed } from 'vue'
import { language, languages, setLanguage, t, type Language } from '../i18n'

defineProps<{ disabled?: boolean }>()
const model = defineModel<Language>()
const selected = computed(() => model.value ?? language.value)
function choose(value: Language) {
  if (model.value !== undefined) model.value = value
  else setLanguage(value)
}
</script>

<template>
  <div class="language-picker" role="group" :aria-label="t('Language')">
    <PButton v-for="option in languages" :key="option.value" type="button" severity="secondary" outlined
      class="language-flag" :class="{ selected: selected === option.value }" :disabled="disabled"
      :aria-label="option.label" :title="option.label" :aria-pressed="selected === option.value"
      @click="choose(option.value)">
      <svg v-if="option.value === 'en'" viewBox="0 0 60 40" aria-hidden="true" focusable="false">
        <path fill="#012169" d="M0 0h60v40H0z" />
        <path stroke="#fff" stroke-width="8" d="m0 0 60 40M60 0 0 40" />
        <path stroke="#c8102e" stroke-width="3" d="m0 0 60 40M60 0 0 40" />
        <path stroke="#fff" stroke-width="13" d="M30 0v40M0 20h60" />
        <path stroke="#c8102e" stroke-width="7" d="M30 0v40M0 20h60" />
      </svg>
      <svg v-else viewBox="0 0 60 40" aria-hidden="true" focusable="false">
        <path fill="#fff" d="M0 0h60v40H0z" />
        <path fill="#d7141a" d="M0 20h60v20H0z" />
        <path fill="#11457e" d="m0 0 30 20L0 40z" />
      </svg>
    </PButton>
  </div>
</template>

<style scoped>
.language-picker { display: flex; gap: 8px; margin: 16px 0; }
@layer app {
  .language-flag { width: 48px; min-height: 40px; padding: 8px; }
  .language-flag svg { display: block; width: 30px; height: 20px; border-radius: 2px; box-shadow: 0 0 0 1px #0002; overflow: hidden; }
  .language-flag.selected { border-color: var(--accent); background: var(--accent-soft); box-shadow: 0 0 0 1px var(--accent); }
}
</style>
