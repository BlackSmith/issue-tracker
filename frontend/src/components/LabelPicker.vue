<script setup lang="ts">
import type { LabelDefinition } from '../types'
import LabelBadge from './LabelBadge.vue'
import { t } from '../i18n'
withDefaults(defineProps<{ definitions: LabelDefinition[]; disabled?: boolean; showLabel?: boolean }>(), { showLabel: true })
const model = defineModel<string[]>({ required: true })
</script>

<template>
  <div class="label-picker">
    <span v-if="showLabel" class="editor-field-label">{{ t('Labels') }}</span>
    <MultiSelect v-model="model" :options="definitions" option-label="name" option-value="name"
      :disabled="disabled" filter :filter-fields="['name', 'description']" :placeholder="t('Select labels')"
      :aria-label="t('Labels')" :max-selected-labels="2" :selected-items-label="t('{0} labels selected')" @keydown.esc.stop>
      <template #option="{ option }">
        <span class="label-option-content"><LabelBadge :name="option.name" :definition="option" /><small v-if="option.description">{{ option.description }}</small></span>
      </template>
      <template #empty>{{ t('No labels defined. Ask an administrator to add labels in organization or project settings.') }}</template>
    </MultiSelect>
  </div>
</template>

<style scoped>
.label-picker { min-width: 0; }
.label-option-content { min-width: 0; overflow-wrap: anywhere; }
.label-option-content small { display: block; margin-top: 3px; color: var(--muted); }
</style>
