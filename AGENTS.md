# Issue Tracker — Project Instructions

## Project Status

The first development increment is implemented: FastAPI/Vue skeleton, PostgreSQL migrations, OIDC login and server-side sessions, CLI membership provisioning, personal profiles and appearance settings, project permissions, work items with URL filters, comments/activity, local attachments, personal API tokens, and administrator-managed bot accounts. See `README.md` for startup and current limitations and `docs/agent-memory.md` for verified environment findings. The full scope below includes planned capabilities; do not assume they all exist.

## Product Scope

- Build a standalone issue tracker inspired by GitLab Work Items, without Git hosting or CI/CD features.
- Deploy one instance per organization, with multiple projects within the instance.
- Prioritize a clear interface, powerful filtering, labels, convenient image and file uploads, a public integration API, API tokens, and webhooks.
- Use English for the initial application UI and all project files. Communicate with the user in Czech.

## Agreed Technology

- Backend: FastAPI, SQLAlchemy 2, Alembic, and PostgreSQL. Do not use Django.
- Frontend: Vue 3, TypeScript, and Vite.
- Use PrimeVue 4 as the primary UI component library. Shared registration and the Aura-based theme live in `frontend/src/primevue.ts`; retain account-scoped appearance variables and the `legacy`, `primevue`, `app` CSS layer order. Use explicit submit types on PrimeVue form buttons.
- Work item descriptions and comments use the shared Tiptap WYSIWYG editor. Keep Markdown as the database/API format for compatibility; users must not need Markdown syntax to format content. Preserve per-editor Marked parser isolation (see `docs/agent-memory.md`).
- Support `@` user mentions, `#` ticket suggestions, and pasted internal ticket URLs in the shared editor. Persist stable reference IDs with neutral Markdown labels and resolve current names/title/status under the viewer's permissions; never embed protected ticket titles in a public ticket's stored reference.
- API: versioned REST endpoints under `/api/v1`, with OpenAPI documentation. The frontend uses the same API exposed to integrations.
- Deployment: Docker Compose, with a reverse proxy, frontend, API, background worker, and PostgreSQL.
- Initial attachment storage: persistent local storage, designed to allow a later S3 adapter.
- PostgreSQL is sufficient initially for search and the webhook delivery queue; additional infrastructure is not required by default.

## Authentication and Authorization

- Use Authlib and generic OpenID Connect support rather than a Keycloak-specific integration. Compatible providers include Keycloak and Google.
- Keep provider communication separate from internal users, sessions, and authorization. Allow a future provider-specific OAuth adapter to return a normalized external identity.
- Do not implement Facebook Login in the current scope.
- Configure enabled providers per instance; only configured providers appear on the login screen.
- Identify OIDC identities by the verified `issuer` and `subject`, not by email address.
- Maintain stable internal user IDs and separate external identity records. A user may have multiple external identities.
- Every authenticated user can edit their own display name, contact email, avatar, and appearance. Profile email is not an authentication identifier. Preserve local profile changes across later OIDC sign-ins. Appearance is stored per account; default to a green accent and white background and reset to defaults on logout.
- Application Settings (`/admin/settings`) is available only to organization/application administrators, with Organization, Users, and Bots tabs. The Users overview includes inactive/pending human accounts, application Admin/User designation, and last successful OIDC sign-in; API/token requests do not count as sign-ins. Project Admin does not grant application settings access.
- Never automatically merge accounts by matching email. Linking an identity requires an authenticated user and verification of the additional identity.
- Handle login in the backend and use server-side sessions with secure, HttpOnly cookies. Use state, nonce, and PKCE for the applicable authorization flow.
- Manage organization roles and project permissions in the tracker.
- Successful external authentication alone does not grant organization membership. Default to invitation-based membership; allow explicitly configured automatic membership for trusted corporate OIDC providers.
- Provide a one-time administrative command to bootstrap the first administrator.
- Personal API tokens are issued by the tracker and have their own lifecycle, independent of browser login sessions.
- API tokens use scoped bearer authentication and current owner permissions. Never fall back to browser cookies for invalid Authorization or create browser sessions from tokens. Credential and bot management require browser sessions; tokens cannot issue more credentials.
- Bots are explicit internal user identities with reader/member roles, no OIDC/browser login, and administrator-managed tokens. They require explicit membership even in organization-visible projects. Disabling a bot revokes its tokens permanently; preserve historical bot authorship.

## Initial Functional Scope

- Projects with organization-visible or private access and administrator, member, and reader roles.
- Project Admin (API role `administrator`) manages project settings, memberships, and local label definitions. Project Member can contribute to work items but cannot configure the project. Organization administrators retain full access; project administration cannot elevate organization readers or bots. Use API-provided `can_manage` for the settings UI and enforce the same permission in backend endpoints.
- Work items with project-scoped identifiers such as `APP-123`, title, visually edited description (stored as Markdown), type, status, priority, assignee, due date, labels, and milestone.
- Labels are explicit administrator-managed definitions with name, color, and description at organization or project scope. Every project inherits all organization labels; ticket creation and editing must select existing definitions. Preserve assignments when renaming and reject deletion of assigned labels. Names are case-sensitive and unambiguous within each inherited/local catalog.
- Initial statuses: `Open`, `In progress`, `Done`, and `Canceled`. Per-project custom workflows are outside the initial scope.
- Work item list with filtering, sorting, pagination, and filter state preserved in the URL.
- Detail view available both in a side panel and at a standalone URL.
- Ticket URLs use `/<stable-project-slug>/<project-scoped-number>`. Preserve existing UUID-based API identifiers and old browser-link redirects. Slugs are unique, persisted, and generated or supplied at project creation.
- Project list URLs use `/<stable-project-slug>/` with a trailing slash. Sidebar links, filters, creation redirects, and returns from tickets use that path; old `/projects/<uuid>` browser links redirect while preserving query parameters.
- Comments and activity history.
- Users with project write access can toggle rendered checklists in descriptions and any comment. Record each actual change in the ticket activity with its actor, task label/state, and source; preserve comment authorship and reject stale content versions rather than overwriting concurrent edits.
- Image and file attachments in descriptions and comments, with upload progress, file selection, drag-and-drop, and image pasting from the clipboard.
- Enforce project access permissions when serving attachments.
- Editor uploads are temporary until description/comment save, including during ticket creation. Expire unconfirmed uploads after 24 hours with automatic startup/hourly cleanup; retain the permanent standalone item-upload API behavior for integrations.
- Parent/child hierarchy and relationships such as blocks and relates-to.
- Milestones, Kanban, and saved views.
- Personal API tokens with names, scopes, expiration, revocation, and last-used metadata. Show the secret only at creation and store only its hash. Tokens must not exceed their owner's permissions.
- Project webhooks with selectable events, HMAC signatures, event identifiers, background delivery, retries, delivery history, and manual redelivery.

## Development Environment

- Existing configuration lives in `.devcontainer/`; it may be adjusted as needed for this project.
- Preserve the local OpenCode runtime/configuration volumes and shared browser configuration when editing the Dev Container.
- Use `https://github.com/calcite/keycloak-mockup` as the development OIDC provider. The image is pinned by digest to v0.1.0 because `.devcontainer/oidc_mock.py` corrects its missing ID tokens and PKCE verification using upstream internals. Keep application-side OIDC validation intact.
- Provide project-specific mock configuration and administrator, member, and reader test accounts.
- Ensure the configured OIDC issuer and redirect URLs work from both the backend container and the external browser. Do not assume that browser localhost refers to the backend container.
- The shared browser service is `chromium4devcontainer`. Use it for frontend verification.
- Browser work must follow the global `chrome-playwright` skill and be delegated to the `browser` subagent. Do not launch an unrelated browser instance.
- PostgreSQL inspection and operations must follow the global PostgreSQL instructions and be delegated to the `postgresql` subagent.
- Development setup and planned application addresses are documented in `.devcontainer/README.md`. The OIDC mock advertises `http://host.docker.internal:5152/realms/issue-tracker`; host port 5151 is used by another project.
- The post-create script conditionally installs `backend/requirements.txt` into `backend/.venv` and frontend npm dependencies when manifests exist. Keep it aligned with actual dependency manifests when bootstrapping the application.

## Implementation and Verification

- Implement in usable increments: environment and skeleton; authentication and permissions; core tracker and attachments; planning features and integrations.
- Keep changes focused and consistent with established project patterns. Do not introduce unrelated cleanup or dependencies.
- Prioritize meaningful tests for authentication, permissions, private project isolation, attachment access, API token restrictions, and webhook retries.
- Verify OIDC login against the running mock, not only mocked application responses.
- Verify core UI flows in the shared browser: login, work item creation, filtering, comments, and attachment uploads.
- Record verified browser-visible application URLs and durable architectural or debugging findings in `docs/agent-memory.md` when that file is introduced. Avoid recording temporary progress or secrets.
- Keep these instructions accurate as decisions evolve; distinguish proposed capabilities from implemented behavior.

## Changes and Commits

- Summarize completed work and ask whether the user wants a Git commit. Do not initialize a repository or create commits without a request.
- Before a requested commit, follow global Git inspection instructions and update the existing project changelog. If no changelog convention exists, ask before introducing a changelog file.
- Use concise English commit messages, preserve unrelated user changes, and do not rewrite history unless explicitly requested.
