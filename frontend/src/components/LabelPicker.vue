<script setup lang="ts">
import { computed, ref } from 'vue'
import type { LabelDefinition } from '../types'
import LabelBadge from './LabelBadge.vue'
const props = defineProps<{ definitions: LabelDefinition[]; disabled?: boolean }>()
const model = defineModel<string[]>({ required: true })
const search = ref('')
const visible = computed(() => props.definitions.filter(label => `${label.name} ${label.description}`.toLowerCase().includes(search.value.toLowerCase())))
</script>

<template>
  <fieldset class="label-picker" :disabled="disabled">
    <legend>Labels</legend>
    <input v-model="search" type="search" aria-label="Search labels" placeholder="Search labels…" />
    <div class="label-options">
      <label v-for="label in visible" :key="label.id" class="label-option">
        <input v-model="model" type="checkbox" :value="label.name" />
        <span class="label-option-content"><LabelBadge :name="label.name" :definition="label" :tooltip="[label.project_id ? 'Project label' : 'Organization label', label.description].filter(Boolean).join('\n')" /><small v-if="label.description">{{ label.description }}</small></span>
      </label>
      <p v-if="!visible.length" class="hint">{{ definitions.length ? 'No matching labels.' : 'No labels defined. Ask an administrator to add labels in organization or project settings.' }}</p>
    </div>
  </fieldset>
</template>

<style scoped>
.label-picker { border: 0; padding: 0; margin: 0; min-width: 0; }
legend { font-weight: 600; margin-bottom: 8px; }
.label-options { max-height: 250px; overflow-y: auto; }
.label-option { display: flex; flex-direction: row; align-items: flex-start; gap: 8px; margin: 10px 0; overflow-wrap: anywhere; }
.label-option input { width: 16px; height: 16px; flex: 0 0 16px; margin: 4px 0 0; }
.label-option-content { min-width: 0; }
.label-option small { display: block; margin-top: 3px; }
</style>
