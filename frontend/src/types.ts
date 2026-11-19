export interface User {
  id: string; name: string; email: string; role: 'administrator' | 'member' | null
  avatar_url: string | null; theme_accent: string; theme_background: string
  is_bot: boolean
  language: 'en' | 'cs'
}
export interface Project { id: string; key: string; slug: string; legacy_slug?: string | null; name: string; description: string; visibility: string; default_access: 'reporter' | 'read-only' | null; restrict_ticket_visibility: boolean; can_write: boolean; can_manage: boolean }
export interface Assignee { id: string; name: string; avatar_url: string | null; is_bot: boolean }
export interface LabelDefinition { id: string; project_id: string | null; name: string; color: string; description: string }
export interface WorkItem {
  id: string; project_id: string; project_slug: string; number: number; web_url: string
  reference: string; title: string; description: string; description_version: string
  type: string; status: string; priority: string; labels: string[]; due_date: string | null
  assignee_id: string | null; assignee: Assignee | null
  is_project_public: boolean
  created_at: string; updated_at: string
}
export interface Discussion { id: string; kind: string; author: string; author_is_bot: boolean; avatar_url: string | null; body: string; body_version: string | null; created_at: string }
export interface ApiToken {
  id: string; user_id: string; name: string; prefix: string; scopes: string[]
  status: 'active' | 'expired' | 'revoked'; created_at: string; expires_at: string
  revoked_at: string | null; last_used_at: string | null
}
export interface BotAccount { id: string; name: string; role: 'member'; active: boolean; is_bot: true; avatar_url: string | null }
export interface BotProject { project_id: string; name: string; key: string; slug: string; role: string; effective_role: string }
export interface Attachment { id: string; filename: string; size: number; url: string }
export const statuses = ['Open', 'In progress', 'Done', 'Canceled']
export const priorities = ['Low', 'Medium', 'High', 'Urgent']
export const itemTypes = ['Task', 'Bug', 'Feature']
