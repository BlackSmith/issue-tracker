<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, ref } from 'vue'
import type { LabelDefinition } from '../types'
import LabelPicker from './LabelPicker.vue'
const RichTextEditor = defineAsyncComponent(() => import('./RichTextEditor.vue'))

const props = withDefaults(defineProps<{
  label: string; value: string; canWrite: boolean; disabled: boolean
  kind?: 'text' | 'select' | 'date' | 'labels' | 'description'
  options?: readonly (string | { value: string; label: string; disabled?: boolean })[]; itemId?: string; projectId?: string
  labelDefinitions?: LabelDefinition[]
  save: (value: string) => Promise<boolean>
}>(), { kind: 'text' })
const emit = defineEmits<{ editing: [value: boolean]; uploaded: [] }>()
const editing = ref(false), draft = ref(''), uploading = ref(false)
const labelDraft = computed<string[]>({ get: () => JSON.parse(draft.value || '[]'), set: value => { draft.value = JSON.stringify(value) } })
const form = ref<HTMLFormElement | null>(null)
const selectOptions = computed(() => props.options?.map(option => typeof option === 'string' ? { value: option, label: option, disabled: false } : option))
async function edit() {
  draft.value = props.value
  editing.value = true
  emit('editing', true)
  await nextTick()
  form.value?.querySelector<HTMLElement>('input, select, [contenteditable="true"]')?.focus()
}
function cancel() {
  if (props.disabled || uploading.value) return
  editing.value = false
  emit('editing', false)
}
async function submit() {
  if (props.disabled || uploading.value) return
  if (await props.save(draft.value)) {
    editing.value = false
    emit('editing', false)
  }
}
</script>

<template>
  <div class="item-field" :class="{ 'is-editing': editing }">
    <div class="item-field-heading">
      <span v-if="kind !== 'text'" class="item-field-label">{{ label }}</span>
      <button v-if="canWrite && !editing" class="quiet item-field-edit" :disabled="disabled" :aria-label="`Edit ${label}`" @click="edit">Edit</button>
    </div>
    <form v-if="editing" ref="form" class="item-field-form" :aria-label="`Edit ${label}`" @submit.prevent="submit" @keydown.esc.stop.prevent="cancel">
      <LabelPicker v-if="kind === 'labels'" v-model="labelDraft" :definitions="labelDefinitions || []" :disabled="disabled" />
      <label v-else-if="kind !== 'description'">
        <span class="sr-only">{{ label }}</span>
        <select v-if="kind === 'select'" v-model="draft" :disabled="disabled"><option v-for="option in selectOptions" :key="option.value" :value="option.value" :disabled="option.disabled">{{ option.label }}</option></select>
        <input v-else v-model="draft" :type="kind === 'date' ? 'date' : 'text'" :required="kind === 'text'" :maxlength="kind === 'text' ? 250 : undefined" :disabled="disabled" />
      </label>
      <RichTextEditor v-else v-model="draft" :label="label" :item-id="itemId" :project-id="projectId" :disabled="disabled" @uploading="uploading = $event" @uploaded="emit('uploaded')" />
      <div class="item-field-actions"><button type="button" :disabled="disabled || uploading" @click="cancel">Cancel</button><button class="primary" :disabled="disabled || uploading">Save</button></div>
    </form>
    <slot v-else />
  </div>
</template>
