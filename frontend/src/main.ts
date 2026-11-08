import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Workspace from './Workspace.vue'
import Settings from './Settings.vue'
import UserProfile from './UserProfile.vue'
import ApplicationSettings from './ApplicationSettings.vue'
import { installPrimeVue } from './primevue'
import './style.css'
import './theme.css'
import './references.css'
import './primevue.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Workspace },
    { path: '/settings', component: Settings },
    { path: '/admin/settings', component: ApplicationSettings },
    { path: '/admin/bots', redirect: to => ({ path: '/admin/settings', query: { ...to.query, tab: 'bots' }, hash: to.hash }) },
    { path: '/admin/organization', redirect: to => ({ path: '/admin/settings', query: to.query, hash: to.hash }) },
    { path: '/users/:userId([a-fA-F0-9-]{36})', component: UserProfile },
    { path: '/projects/:projectId', component: Workspace },
    { path: '/items/:itemId', component: Workspace },
    { path: '/:projectSlug/new', name: 'new-item', component: Workspace },
    { path: '/:projectSlug/:itemNumber(\\d+)', component: Workspace },
    { path: '/:projectSlug/', component: Workspace, strict: true },
    { path: '/:projectSlug', strict: true, redirect: to => ({ path: `/${to.params.projectSlug}/`, query: to.query, hash: to.hash }) },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
createApp(App).use(installPrimeVue).use(router).mount('#app')
