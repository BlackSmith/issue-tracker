<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, ref } from 'vue'
import type { LabelDefinition } from '../types'
import LabelPicker from './LabelPicker.vue'
import { t } from '../i18n'
import StatusBadge from './StatusBadge.vue'
const RichTextEditor = defineAsyncComponent(() => import('./RichTextEditor.vue'))

const props = withDefaults(defineProps<{
  label: string; value: string; canWrite: boolean; disabled: boolean
  kind?: 'text' | 'select' | 'status' | 'date' | 'labels' | 'description'
  options?: readonly (string | { value: string; label: string; disabled?: boolean })[]; itemId?: string; projectId?: string
  labelDefinitions?: LabelDefinition[]
  save: (value: string) => Promise<boolean>
}>(), { kind: 'text' })
const emit = defineEmits<{ editing: [value: boolean]; uploaded: [] }>()
const editing = ref(false), draft = ref(''), uploading = ref(false)
const labelDraft = computed<string[]>({ get: () => JSON.parse(draft.value || '[]'), set: value => { draft.value = JSON.stringify(value) } })
const form = ref<HTMLFormElement | null>(null)
const selectOptions = computed(() => props.options?.map(option => typeof option === 'string' ? { value: option, label: t(option), disabled: false } : option))
async function edit() {
  draft.value = props.value
  editing.value = true
  emit('editing', true)
  await nextTick()
  form.value?.querySelector<HTMLElement>('input, [role="combobox"], [contenteditable="true"]')?.focus()
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
      <PButton v-if="canWrite && !editing" class="quiet item-field-edit" :disabled="disabled" :aria-label="t('Edit {label}', { label })" @click="edit">{{ t('Edit') }}</PButton>
    </div>
    <form v-if="editing" ref="form" class="item-field-form" :aria-label="t('Edit {label}', { label })" @submit.prevent="submit" @keydown.esc.stop.prevent="cancel">
      <LabelPicker v-if="kind === 'labels'" v-model="labelDraft" :definitions="labelDefinitions || []" :disabled="disabled" :show-label="false" />
      <label v-else-if="kind !== 'description'">
        <span class="sr-only">{{ label }}</span>
        <PSelect v-if="kind === 'select' || kind === 'status'" v-model="draft" :options="selectOptions" option-label="label" option-value="value" option-disabled="disabled" :placeholder="selectOptions?.find(option => option.value === '')?.label" :aria-label="label" :disabled="disabled" filter @keydown.esc.stop>
          <template v-if="kind === 'status'" #value="{ value }"><StatusBadge :status="value" /></template>
          <template v-if="kind === 'status'" #option="{ option }"><StatusBadge :status="option.value" /></template>
        </PSelect>
        <InputText v-else v-model="draft" :type="kind === 'date' ? 'date' : 'text'" :required="kind === 'text'" :maxlength="kind === 'text' ? 250 : undefined" :disabled="disabled" />
      </label>
      <RichTextEditor v-else v-model="draft" :label="label" :item-id="itemId" :project-id="projectId" :disabled="disabled" @uploading="uploading = $event" @uploaded="emit('uploaded')" />
      <div class="item-field-actions"><PButton type="button" severity="secondary" outlined :disabled="disabled || uploading" @click="cancel">{{ t('Cancel') }}</PButton><PButton type="submit" :disabled="disabled || uploading">{{ t('Save') }}</PButton></div>
    </form>
    <slot v-else />
  </div>
</template>
