# Changelog

## Unreleased

### Added

- Multi-stage Docker images for the API and compiled frontend, an example Compose deployment with PostgreSQL and automatic migrations, and deployment/environment configuration documentation.
- Owner-configurable default project access (Reporter or Read-only) for active human application members, with explicit-role precedence, consistent API/reference/attachment/notification permissions, English/Czech settings, and migration `0016` preserving closed access for existing projects.
- Owner-managed publication of individual tickets to all project members in restricted projects, with reversible detail controls, activity history, and migration `0015` defaulting existing tickets to unpublished.
- Opt-in project setting restricting Reporter and Read-only ticket visibility to authored or assigned tickets, enforced across API access, references, attachments, and email notifications; migration `0014` preserves unrestricted defaults.
- Configurable OIDC and Facebook providers through TOML with environment overrides, alongside administrator-created local password accounts with Argon2id, single-use invitations, password changes, and administrator-controlled recovery.
- Encrypted SMTP outboxes with bounded delivery retries, development Mailpit support, and migrations `0010`/`0011` for local credentials, password links, session revocation versions, and login throttling.
- English and Czech interface localization with account-scoped language preferences, localized validation/activity rendering, and migration `0012`.
- Transactional ticket email notifications for project Owners, authors, assignees, comment/activity participants, and stable user mentions, with recipient deduplication, delivery-time access checks, and migration `0013`.
- PrimeVue 4 controls with an Aura-based theme that follows account appearance preferences.
- Application settings with Organization, Users, and Bots tabs, accessible only to application administrators.
- Searchable, sortable, paginated human account overview, including inactive and pending accounts, application roles, account status, and last successful OIDC sign-in.
- Migration `0008` for nullable user sign-in timestamps, without inferring historical sign-ins.
- Project Admin permissions for project settings, memberships, and local labels, separate from Member contribution permissions.
- Automatic explicit Admin membership for the creator of a new project.
- Multiple status and label filters with shareable repeated URL parameters and icons.
- GitLab-style search with editable filter tokens for status, labels, assignee (Me and Unassigned included), priority, and type; keyboard navigation and shareable filter URLs.
- Bidirectional work item sorting by updated date, created date, title, semantic priority, and due date, with undated items always last.

### Changed

- Replace the placeholder brand mark with a ticket-and-check SVG logo and favicon, and redesign sign-in with a responsive split layout, English/Czech copy, and accessible text contrast.
- Project settings initially focuses the project name instead of the close button, avoiding the automatic circle around X while preserving keyboard focus indicators.
- Personal settings include language selection and local password management; organization user details include authentication method, login email, and invitation/recovery delivery state.
- Status badges and assignee avatars/icons are shared across ticket displays and filter controls.
- Labels use rounded, solid-color badges throughout the interface, with white text on green and darker backgrounds and dark text on light backgrounds.
- Application roles are Admin and Member; project roles are Owner, Reporter, and Read-only. Migration `0009` converts existing roles without adding memberships. Project access requires explicit membership, while application admins are permanent owners of all projects.
- Organization settings is anchored at the bottom of the sidebar and restricted to application admins, including Users and Bots. User details support application-role/status management while preserving at least one active admin.
- Application Settings keeps Labels, Users, and Bots in lists and opens label editors, editable user permissions, and bot management in ticket-style right panels. Panels support direct links, browser history, and full-width mobile presentation.
- Canonical project and ticket URLs use the stable uppercase project key; authorized legacy slug URLs remain supported and redirect while preserving filters and hashes.
- Priority filter options and tokens reuse ticket priority colors; type values use blue for Task, red for Bug, and purple for Feature.
- Project and organization label lists omit redundant source captions; inherited project labels retain the Inherited indicator.
- Default work item lists show Open and In progress; Done and Canceled are hidden until selected.
- Project settings use accessible General, Members, and Labels tabs.
- Member and label creation forms appear above their lists and expand only when requested.
- Token creation forms expand from Create token and collapse after successful creation or cancellation.
- Project roles and visibility use SelectButton controls.
- Application Settings is a standalone sidebar entry; former organization and bot URLs redirect to the corresponding settings tab.
- Ticket panel close buttons have a larger clickable area, and label editing avoids a duplicated field heading.

### Fixed

- Opening another password setup link in the same browser document refreshes the setup form and discards the previous token and draft.
- Password resets, login-email changes, and account disabling revoke browser sessions through account authentication versions while preserving independent API token lifecycles.
- Expired browser sessions now return the interface to sign-in instead of leaving a stale user and failing Sign out with Invalid CSRF token. Authentication failures synchronize through a shared session refresh; logout refreshes CSRF first, and failed writes are never automatically replayed.
- Project administrators immediately lose settings access after removing or demoting their own membership.
- Project dialogs close when browser navigation changes the route.
- Search icon spacing and responsive control layouts remain usable with PrimeVue styling.
- Empty filter values retain their intended meaning across reloads, history navigation, and ticket panel transitions.

### Verification

- Backend: 180 tests passed.
- Frontend: 22 tests passed; TypeScript checks and production build passed.
- PostgreSQL migration and model alignment verified without changing existing user counts.
- Shared-browser verification covered desktop/mobile layouts, real OIDC sign-in, authorization boundaries, filters, project settings, forms, and application user administration.
- Shared-browser verification also covered local password invitation/recovery, account language persistence, Czech ticket flows, and actual ticket notification SMTP delivery to Mailpit for creation, mentions, comments, reassignment, and status changes.
