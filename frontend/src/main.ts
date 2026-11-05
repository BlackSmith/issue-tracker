import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Workspace from './Workspace.vue'
import Settings from './Settings.vue'
import UserProfile from './UserProfile.vue'
import Bots from './Bots.vue'
import OrganizationSettings from './OrganizationSettings.vue'
import './style.css'
import './theme.css'
import './references.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Workspace },
    { path: '/settings', component: Settings },
    { path: '/admin/bots', component: Bots },
    { path: '/admin/organization', component: OrganizationSettings },
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
createApp(App).use(router).mount('#app')
