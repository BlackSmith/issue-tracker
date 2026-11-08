import type { App } from 'vue'
import PrimeVue from 'primevue/config'
import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import SelectButton from 'primevue/selectbutton'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import MultiSelect from 'primevue/multiselect'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import ProgressBar from 'primevue/progressbar'
import Paginator from 'primevue/paginator'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'

const preset = definePreset(Aura, {
  semantic: {
    primary: {
      50: 'var(--accent-soft)', 100: 'var(--accent-soft)', 200: 'var(--accent-border)',
      300: 'var(--accent-border)', 400: 'var(--accent-muted)', 500: 'var(--accent)',
      600: 'var(--accent)', 700: 'var(--accent-hover)', 800: 'var(--accent-hover)', 900: 'var(--header)', 950: 'var(--header)',
    },
    colorScheme: { light: {
      primary: { color: 'var(--accent)', contrastColor: '#ffffff', hoverColor: 'var(--accent-hover)', activeColor: 'var(--accent-hover)' },
      highlight: { background: 'var(--accent-soft)', focusBackground: 'var(--accent-border)', color: 'var(--accent)', focusColor: 'var(--accent)' },
      formField: { background: 'var(--surface)', color: 'var(--text)', borderColor: 'var(--border)', hoverBorderColor: 'var(--accent-muted)', focusBorderColor: 'var(--accent)' },
      content: { background: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text)' },
    } },
    formField: { paddingX: '0.7rem', paddingY: '0.55rem', borderRadius: '6px' },
  },
})

export function installPrimeVue(app: App) {
  app.use(PrimeVue, { theme: { preset, options: { darkModeSelector: false, cssLayer: { name: 'primevue', order: 'legacy, primevue, app' } } } })
  app.component('PButton', Button)
  app.component('InputText', InputText)
  app.component('PTextarea', Textarea)
  app.component('PSelect', Select)
  app.component('SelectButton', SelectButton)
  app.component('DataTable', DataTable)
  app.component('PColumn', Column)
  app.component('PTag', Tag)
  app.component('MultiSelect', MultiSelect)
  app.component('PDialog', Dialog)
  app.component('PMessage', Message)
  app.component('ProgressBar', ProgressBar)
  app.component('Paginator', Paginator)
  app.component('PTabs', Tabs)
  app.component('PTabList', TabList)
  app.component('PTab', Tab)
  app.component('PTabPanels', TabPanels)
  app.component('PTabPanel', TabPanel)
}
