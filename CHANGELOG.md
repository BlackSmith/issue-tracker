# Changelog

## Unreleased

### Added

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

- Expired browser sessions now return the interface to sign-in instead of leaving a stale user and failing Sign out with Invalid CSRF token. Authentication failures synchronize through a shared session refresh; logout refreshes CSRF first, and failed writes are never automatically replayed.
- Project administrators immediately lose settings access after removing or demoting their own membership.
- Project dialogs close when browser navigation changes the route.
- Search icon spacing and responsive control layouts remain usable with PrimeVue styling.
- Empty filter values retain their intended meaning across reloads, history navigation, and ticket panel transitions.

### Verification

- Backend: 136 tests passed.
- Frontend: 17 tests passed; TypeScript checks and production build passed.
- PostgreSQL migration and model alignment verified without changing existing user counts.
- Shared-browser verification covered desktop/mobile layouts, real OIDC sign-in, authorization boundaries, filters, project settings, forms, and application user administration.
