<script setup lang="ts">
import { computed, nextTick, ref, useId } from 'vue'
import type { Assignee, LabelDefinition } from '../types'
import { itemTypes, priorities, statuses } from '../types'
import LabelBadge from './LabelBadge.vue'

export type FilterKey = 'status' | 'label' | 'assignee' | 'priority' | 'type'
export type Filters = Record<FilterKey, string[]>
const props = defineProps<{ query: string; filters: Filters; labels: LabelDefinition[]; assignees: Assignee[] }>()
const emit = defineEmits<{ 'update:query': [value: string]; change: [key: FilterKey, values: string[]]; search: [] }>()
const fields: { key: FilterKey; name: string; hint: string }[] = [
  { key: 'status', name: 'Status', hint: 'Open, in progress, done…' },
  { key: 'label', name: 'Label', hint: 'Project and organization labels' },
  { key: 'assignee', name: 'Assignee', hint: 'Me, unassigned, or a person' },
  { key: 'priority', name: 'Priority', hint: 'Low, medium, high, urgent' },
  { key: 'type', name: 'Type', hint: 'Task, bug, feature' },
]
const field = ref<FilterKey | null>(null), open = ref(false), term = ref(''), active = ref(-1)
const input = ref<{ $el: HTMLInputElement }>()
const root = ref<HTMLElement>()
const menuId = useId()
const fieldName = computed(() => fields.find(option => option.key === field.value)?.name)
const inputValue = computed({
  get: () => field.value ? term.value : props.query,
  set: value => { if (field.value) term.value = value; else emit('update:query', value); active.value = -1; open.value = true },
})
const options = computed(() => {
  if (!field.value) return fields.map(option => ({ value: option.key, name: option.name, hint: option.hint }))
  let values: { value: string; name: string; hint?: string }[]
  switch (field.value) {
    case 'label': values = props.labels.map(label => ({ value: label.name, name: label.name })); break
    case 'assignee': values = [{ value: 'me', name: 'Me' }, { value: 'none', name: 'Unassigned' }, ...props.assignees.map(person => ({ value: person.id, name: person.name }))]; break
    default: values = ({ status: statuses, priority: priorities, type: itemTypes }[field.value]).map(value => ({ value, name: value }))
  }
  return values.filter(option => option.name.toLowerCase().includes(term.value.toLowerCase()))
})
function valueName(key: FilterKey, value: string) {
  if (key !== 'assignee') return value
  return value === 'me' ? 'Me' : value === 'none' ? 'Unassigned' : props.assignees.find(person => person.id === value)?.name || 'User unavailable'
}
function focus() { nextTick(() => input.value?.$el.focus()) }
function edit(key: FilterKey) { field.value = key; term.value = ''; active.value = -1; open.value = true; focus() }
function close() { open.value = false; field.value = null; term.value = ''; active.value = -1 }
function choose(value: string) {
  if (!field.value) { edit(value as FilterKey); return }
  const selected = props.filters[field.value]
  emit('change', field.value, selected.includes(value) ? selected.filter(item => item !== value) : [...selected, value])
  focus()
}
function remove(key: FilterKey, value: string) { emit('change', key, props.filters[key].filter(item => item !== value)) }
function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); return }
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault(); open.value = true
    if (!options.value.length) return
    active.value = (active.value + (event.key === 'ArrowDown' ? 1 : -1) + options.value.length) % options.value.length
    nextTick(() => document.getElementById(`${menuId}-${active.value}`)?.scrollIntoView({ block: 'nearest' }))
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const option = options.value[active.value]
    if (open.value && option) choose(option.value)
    else if (field.value && options.value.length === 1) choose(options.value[0]!.value)
    else if (field.value) close()
    else { close(); emit('search') }
  } else if (event.key === 'Backspace' && field.value && !term.value) {
    field.value = null; active.value = -1
  }
}
function onFocusOut(event: FocusEvent) {
  if (!root.value?.contains(event.relatedTarget as Node | null)) close()
}
</script>

<template>
  <div ref="root" class="work-item-search" @focusout="onFocusOut">
    <div class="token-search" @click.self="focus">
      <span class="search-symbol" aria-hidden="true">⌕</span>
      <template v-for="category in fields" :key="category.key">
        <span v-for="value in filters[category.key]" :key="value" class="filter-token">
          <button type="button" class="token-value" :aria-label="`Edit ${category.name} filter: ${valueName(category.key, value)}`" @click="edit(category.key)">
            <span class="token-key">{{ category.name }}</span><span class="token-operator">=</span>
            <LabelBadge v-if="category.key === 'label'" :name="value" :definition="labels.find(label => label.name === value)" />
            <span v-else-if="category.key === 'priority' || category.key === 'type'" :class="[category.key === 'priority' ? 'priority' : 'type-badge', value.toLowerCase()]">{{ value }}</span>
            <span v-else>{{ valueName(category.key, value) }}</span>
          </button>
          <button type="button" class="token-remove" :aria-label="`Remove ${category.name} filter: ${valueName(category.key, value)}`" @click="remove(category.key, value)">×</button>
        </span>
      </template>
      <span v-if="field" class="editing-field">{{ fieldName }} =</span>
      <InputText ref="input" v-model="inputValue" role="combobox" :aria-label="field ? `Search ${fieldName} options` : 'Search work items'" :placeholder="field ? 'Select or search values…' : 'Search or add a filter…'" :maxlength="field ? 200 : 200" :aria-expanded="open" :aria-controls="open ? menuId : undefined" :aria-activedescendant="open && active >= 0 ? `${menuId}-${active}` : undefined" aria-autocomplete="list" autocomplete="off" @focus="open = true" @keydown="onKey" />
      <PButton type="button" class="search-submit" severity="secondary" text aria-label="Apply search" title="Apply search" @click="close(); emit('search')">↵</PButton>
    </div>
    <div v-if="open" class="filter-menu">
      <div class="filter-menu-heading"><span>{{ field ? `${fieldName} · select one or more` : 'Add a filter' }}</span><button v-if="field" type="button" @click="field = null; active = -1; focus()">Back</button></div>
      <div :id="menuId" role="listbox" :aria-label="field ? `${fieldName} values` : 'Filter types'" :aria-multiselectable="field ? true : undefined" class="filter-options">
        <div v-for="(option, index) in options" :id="`${menuId}-${index}`" :key="option.value" role="option" :aria-selected="field ? filters[field].includes(option.value) : active === index" class="filter-menu-option" :class="{ active: active === index }" @mousedown.prevent @click="choose(option.value)">
          <span v-if="field" class="option-check" aria-hidden="true">{{ filters[field].includes(option.value) ? '✓' : '' }}</span>
          <LabelBadge v-if="field === 'label'" :name="option.value" :definition="labels.find(label => label.name === option.value)" />
          <span v-else-if="field === 'priority' || field === 'type'" :class="[field === 'priority' ? 'priority' : 'type-badge', option.value.toLowerCase()]">{{ option.name }}</span>
          <span v-else>{{ option.name }}</span><small v-if="option.hint">{{ option.hint }}</small>
        </div>
        <div v-if="!options.length" class="filter-menu-empty">No matching values</div>
      </div>
      <div class="filter-menu-footer"><span>{{ field ? 'Values match any selection in this filter.' : 'Type text to search titles and descriptions.' }}</span><PButton type="button" size="small" severity="secondary" text @click="close()">Done</PButton></div>
    </div>
  </div>
</template>

<style scoped>
@layer app {
  .work-item-search { flex: 1; min-width: 0; position: relative; }
  .token-search { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; padding: 6px 8px; min-height: 44px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
  .token-search:focus-within { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
  .search-symbol { color: var(--muted); font-size: 22px; line-height: 1; }
  .token-search .p-inputtext { flex: 1; width: 160px; min-width: 140px; padding: 4px; border: none; box-shadow: none; outline: none; background: transparent; font-size: 13px; }
  .filter-token { display: inline-flex; max-width: 100%; align-items: stretch; border: 1px solid var(--border); border-radius: 4px; background: var(--subtle); overflow: hidden; font-size: 12px; }
  .token-value, .token-remove { min-height: 28px; padding: 3px 6px; border: 0; border-radius: 0; background: transparent; color: var(--text); font-size: 12px; }
  .token-value { min-width: 0; gap: 5px; overflow-wrap: anywhere; }
  .token-value > span:last-child { overflow-wrap: anywhere; min-width: 0; }
  .token-key { font-weight: 650; }
  .token-operator { color: var(--muted); }
  .token-remove { border-left: 1px solid var(--border); flex-shrink: 0; }
  .token-value:hover, .token-remove:hover { background: var(--accent-soft); }
  .editing-field { font-size: 12px; font-weight: 650; }
  .search-submit { padding: 3px 6px; min-height: 28px; margin-left: auto; }
  .filter-menu { position: absolute; top: calc(100% + 5px); left: 0; width: min(440px, 100%); z-index: 10; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; box-shadow: 0 6px 20px #0002; color: var(--text); }
  .filter-menu-heading, .filter-menu-footer { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 8px 12px; font-size: 11px; color: var(--muted); }
  .filter-menu-heading { border-bottom: 1px solid var(--border); font-weight: 650; }
  .filter-menu-heading button { border: 0; background: transparent; color: var(--accent); padding: 2px 5px; min-height: 24px; font-size: 12px; }
  .filter-options { max-height: 260px; overflow-y: auto; padding: 4px; }
  .filter-menu-option { padding: 9px 8px; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; cursor: pointer; border-radius: 4px; font-size: 13px; overflow-wrap: anywhere; }
  .filter-menu-option small { margin-left: auto; color: var(--muted); font-size: 11px; }
  .filter-menu-option:hover, .filter-menu-option.active { background: var(--accent-soft); }
  .option-check { width: 16px; color: var(--accent); flex-shrink: 0; }
  .type-badge { font-size: 10px; padding: 4px 8px; border-radius: 4px; font-weight: 500; white-space: nowrap; }
  .type-badge.task { background: #eef3f7; color: #486a89; }
  .type-badge.bug { background: #fce9e9; color: #a94444; }
  .type-badge.feature { background: #f1eafa; color: #7952a3; }
  .filter-menu-empty { padding: 16px; color: var(--muted); font-size: 12px; }
  .filter-menu-footer { border-top: 1px solid var(--border); }
}
</style>
