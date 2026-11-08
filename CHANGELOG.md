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

### Changed

- Default work item lists show Open and In progress; Done and Canceled are hidden until selected.
- Project settings use accessible General, Members, and Labels tabs.
- Member and label creation forms appear above their lists and expand only when requested.
- Token creation forms expand from Create token and collapse after successful creation or cancellation.
- Project roles and visibility use SelectButton controls.
- Application Settings is a standalone sidebar entry; former organization and bot URLs redirect to the corresponding settings tab.
- Ticket panel close buttons have a larger clickable area, and label editing avoids a duplicated field heading.

### Fixed

- Project administrators immediately lose settings access after removing or demoting their own membership.
- Project dialogs close when browser navigation changes the route.
- Search icon spacing and responsive control layouts remain usable with PrimeVue styling.
- Empty filter values retain their intended meaning across reloads, history navigation, and ticket panel transitions.

### Verification

- Backend: 129 tests passed.
- Frontend: 9 tests passed; TypeScript checks and production build passed.
- PostgreSQL migration and model alignment verified without changing existing user counts.
- Shared-browser verification covered desktop/mobile layouts, real OIDC sign-in, authorization boundaries, filters, project settings, forms, and application user administration.
