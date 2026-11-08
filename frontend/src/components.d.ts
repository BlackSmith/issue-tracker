export {}

declare module 'vue' {
  export interface GlobalComponents {
    PButton: typeof import('primevue/button')['default']
    InputText: typeof import('primevue/inputtext')['default']
    PTextarea: typeof import('primevue/textarea')['default']
    PSelect: typeof import('primevue/select')['default']
    SelectButton: typeof import('primevue/selectbutton')['default']
    DataTable: typeof import('primevue/datatable')['default']
    PColumn: typeof import('primevue/column')['default']
    PTag: typeof import('primevue/tag')['default']
    MultiSelect: typeof import('primevue/multiselect')['default']
    PDialog: typeof import('primevue/dialog')['default']
    PMessage: typeof import('primevue/message')['default']
    ProgressBar: typeof import('primevue/progressbar')['default']
    Paginator: typeof import('primevue/paginator')['default']
    PTabs: typeof import('primevue/tabs')['default']
    PTabList: typeof import('primevue/tablist')['default']
    PTab: typeof import('primevue/tab')['default']
    PTabPanels: typeof import('primevue/tabpanels')['default']
    PTabPanel: typeof import('primevue/tabpanel')['default']
  }
}
