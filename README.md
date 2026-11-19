# Issue Tracker

A standalone, organization-scoped issue tracker inspired by GitLab Work Items.
Built with FastAPI, PostgreSQL, Vue 3, and PrimeVue 4. The interface supports English
and Czech; API field names and enum values remain English.

## Current increment

- PrimeVue controls for buttons, text fields, selects, searchable label multi-selects,
  project dialogs, messages, pagination, and upload progress. The Aura-based theme
  follows the account's accent color; descriptions and comments retain the shared Tiptap editor.
- Generic OIDC login through Authlib with server-side sessions, session rotation,
  CSRF protection, state, nonce, and S256 PKCE.
- Multiple configurable OIDC providers, Facebook OAuth login, and local email/password
  accounts with administrator-controlled invitations, recovery, and SMTP delivery retries.
- Stable internal accounts and separate issuer/subject identities. Matching email
  addresses never merge accounts or confer organization membership.
- Application roles are Admin (API `administrator`) and Member (`member`). Only
  Admin can create projects and manage users, bots, and organization labels.
  Project roles are Owner (`owner`), Reporter (`reporter`), and Read-only (`read-only`).
  Owner manages settings, members, and local labels; Reporter contributes to work
  items and comments; Read-only can browse tickets. Members see only explicitly
  assigned projects. Application admins are permanent owners of every project,
  including projects without an explicit membership row. They cannot be removed
  or demoted through project membership APIs. Creators receive an explicit Owner row.
- Projects can restrict Reporter and Read-only access to authored or assigned tickets.
  With this option enabled, Owners and application admins can publish individual
  tickets to all project members from the ticket's visibility section and revoke
  publication later. Publication preserves each member's read/write role and never
  grants access outside the project. API tokens, references, attachments, and email
  notifications follow the same visibility rules.
- Personal settings for display name, contact email, profile picture, interface
  accent color, application background, and English/Czech interface language. Green is the default accent.
- Project-scoped work item numbers, visually edited descriptions, types, fixed statuses,
  priorities, labels, due dates, editing, and activity history.
- Metadata activity records previous and new values, including assignee names,
  first-time values, and explicit clearing of dates, labels, and assignees.
- Explicit organization and project label definitions with names, colors, and
  descriptions; projects automatically inherit all organization labels. Ticket
  creation, editing, and filtering use existing definitions.
- GitLab-style search bar with editable/removable filter tokens for status, labels,
  assignee (including Me and Unassigned), priority, and type. Text searches titles
  and descriptions. Multiple values within a filter match any selection; different
  filters are combined. Filter menus support Arrow Up/Down, Enter, and Escape.
  Updated date, created date, title, priority, and due date sorting support both
  directions; items without a due date remain last. Pagination and all filters/sort
  state use shareable URLs. Project lists default to Open and In progress, hiding
  Done and Canceled. Reset filters restores that default view while retaining sorting.
- Side-panel and standalone work item creation and detail, with draft-preserving
  switching between creation presentations and list filters preserved on return.
- Readable project URLs such as `/product-development/` and ticket URLs using
  the same stable slug plus project-scoped number, such as `/product-development/123`.
- WYSIWYG descriptions and comments with a formatting toolbar, headings, lists,
  checklists, links, quotes, code, tables, and undo/redo. Existing Markdown and API
  content remain compatible; displayed content is sanitized.
- Direct checklist toggles in descriptions and comments for users with write
  access, with each change recorded in the ticket activity.
- User mentions, ticket-reference suggestions, and pasted internal ticket URLs
  displayed as clickable chips with the current ticket title and status.
- File selection, drag-and-drop, image pasting, upload progress, and attachment
  access checks. Local storage under `var/attachments`, with a 20 MB file limit.
- REST endpoints at `/api/v1`, documented at `/api/v1/docs`.
- Personal API tokens and administrator-managed bot accounts with scoped bearer
  authentication, expiration, revocation, and last-used metadata.

This is an initial development increment. External identity invitations and identity
linking in the UI, trusted-provider
automatic membership, hierarchy/relationships, milestones, Kanban, saved views,
webhooks/worker, and production Docker deployment are planned.
Each account currently uses one authentication method. MFA is deferred; future
application-managed MFA is intended for local passwords only.

## Development setup

Use the existing VS Code Dev Container. See [environment details](.devcontainer/README.md)
for services, addresses, mock users, and browser configuration. The post-create
script installs Python and npm dependencies now that application manifests exist.
To install them in an already running container:

```sh
bash .devcontainer/post_script.sh
```

Apply migrations from `backend/`:

```sh
.venv/bin/alembic -c alembic.ini upgrade head
```

Start the API from `backend/`:

```sh
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 5300 --reload
```

Start the frontend in another terminal from `frontend/`:

```sh
npm run dev
```

Open **http://host.docker.internal:5374**. The frontend proxies `/api` to FastAPI.
The direct API and documentation are available at
**http://host.docker.internal:5301/api/v1/docs**.

Always use the configured frontend hostname when testing OIDC: the frontend and
callback must share the session cookie hostname. The shared browser resolves
`host.docker.internal`; a browser on the host may need a hosts/DNS mapping.

### Provision organization access

External sign-in alone does not grant membership. Before the first login,
bootstrap the administrator from `backend/`:

```sh
.venv/bin/python -m app.cli bootstrap-admin \
  --issuer http://host.docker.internal:5152/realms/issue-tracker \
  --subject 00000000-0000-0000-0000-000000000001 \
  --name 'Development Administrator' --email admin@example.test
```

Bootstrap refuses to run once an administrator exists. Provision the other mock
identities explicitly:

```sh
.venv/bin/python -m app.cli provision-user \
  --issuer http://host.docker.internal:5152/realms/issue-tracker \
  --subject 00000000-0000-0000-0000-000000000002 \
  --name 'Development Member' --email member@example.test --role member

.venv/bin/python -m app.cli provision-user \
  --issuer http://host.docker.internal:5152/realms/issue-tracker \
  --subject 00000000-0000-0000-0000-000000000003 \
  --name 'Development Reader' --email reader@example.test --role member
```

`provision-user` also updates the role of an existing issuer/subject identity.
It does not match accounts by email. For an already signed-in pending account,
use the same verified issuer and subject to grant membership to that account.
Project access can then be assigned in **Project settings → Members** by an
application admin or project owner. The mock identity named Reader is an application
Member; assign it Read-only separately in each desired project.

Migration `0009` maps project `administrator/member/reader` to
`owner/reporter/read-only` and application `reader` to `member`, preserving the
former read-only ceiling on existing assignments. It does not grant replacement
memberships for previously implicit access. The legacy API `visibility` field is
retained as metadata for compatibility; neither value grants access without membership.
The downgrade restores project role names but cannot infer former application readers.

### Application settings and users

Application administrators open **Organization settings** at the bottom of the left sidebar. The
application settings page at `/admin/settings` has **Organization**, **Users**, and
**Bots** tabs. Users and Bots are directly linkable with `?tab=users` and `?tab=bots`.
Existing `/admin/organization` and `/admin/bots` links redirect to the corresponding
tab. Project Owner does not grant access to application settings.

The Users tab lists all human accounts, including inactive accounts and accounts
awaiting membership, with name, email, application role (**Admin** or **Member**),
last successful browser sign-in, and account status. It supports search, sorting,
and pagination. Bots remain in their dedicated tab. Last sign-in is recorded on
successful browser authentication (OIDC, Facebook, or local password), not API requests or token usage. Older accounts
show **Not recorded** until their next sign-in; no historical times are inferred.
The administrator-only endpoints are `GET /api/v1/admin/users` and
`PUT /api/v1/admin/users/{id}` with `role` and `active`. At least one active
application admin must remain.

Settings lists remain visible while label creation/editing, user details, and bot
management open in a right-hand panel, matching ticket details. User details allow
admins to change application roles and enable/disable accounts. Panels reserve half the viewport on large screens and fill the content
width on smaller screens. The `detail` query parameter preserves the open record
across reloads and browser history; `detail=new` opens label or bot creation.
Closing a panel returns to its list, retaining the current search and page during
the mounted session. Project label editors inside project settings remain inline.

### Label management

Administrators manage shared labels in **Settings → Organization → Labels** and
project-specific labels in a project's **Settings → Labels**. Each definition has
a name (up to 50 characters), a color, and an optional description (up to 2,000
characters). Inherited organization labels are read-only in project settings and
are available in every current and future project.

Names are case-sensitive and must be unique within the combined organization and
project catalog. Independent projects may reuse local names. An organization
label cannot take a name already used by any project label. Renaming a definition
preserves all existing assignments; labels assigned to tickets cannot be deleted
until those assignments are removed.

Ticket writers select existing labels using a searchable checklist. Readers can
view labels but cannot change their assignments. Badge color accents and description
tooltips use the definition. The list filter offers the same inherited/local
catalog and preserves the selected name in the URL.

The public API exposes `GET`/`POST` at `/api/v1/organization/labels` and
`/api/v1/projects/{project_id}/labels`, with `PUT`/`DELETE` at the corresponding
`/{label_id}` paths. Project listing includes inherited definitions (`project_id:
null`); mutations require administrator permissions. Work item `labels` remains
an array of names for API compatibility, but undefined or out-of-scope names now
return HTTP 422. Duplicate definitions and deletion of assigned labels return
HTTP 409. Migration `0007` converts existing ticket labels into project definitions
with a green color and empty description, preserving assignments.

### Configuration

Settings are read from environment variables, optionally from `backend/.env`
when running in the backend directory. Select a TOML configuration file with
`TRACKER_CONFIG=/absolute/path/to/config.toml`; see `backend/config.example.toml`.
Environment variables override `.env`, which overrides TOML. Compose sets the
development defaults. An environment example is provided at `backend/.env.example`.

`providers` is a TOML array of tables (or the `PROVIDERS` JSON environment variable).
Each entry has a stable unique `id`, display `name`, `type` (`oidc` or `facebook`),
`client_id`, and optional `client_secret` or `client_secret_env`. The latter names
an environment variable containing that provider's secret. OIDC additionally
requires `issuer`. Facebook requires a secret and supports `graph_version`
(default `v24.0`). Register the exact callback
`<api_base_url>/api/v1/auth/<provider-id>/callback` with each provider. Keep provider
IDs stable; Facebook identities are namespaced by Meta app ID and app-scoped user ID.
The application requests Facebook `public_profile` and `email`; absence of an email
does not change how identities are identified. Configure Meta app availability,
test users, permissions, and allowed callback URLs in the Meta developer console.

An explicit nonempty provider list replaces legacy OIDC configuration. When no
list is supplied, the existing `OIDC_*` variables below remain supported. To run
password-only with development Compose defaults, also set `OIDC_ISSUER` to an empty
string in the API process environment. TOML alone cannot override Compose variables.

For another OIDC provider, configure `OIDC_ISSUER`, `OIDC_CLIENT_ID`,
`OIDC_CLIENT_SECRET`, `OIDC_NAME`, and `OIDC_REDIRECT_URI`. Register that exact
callback URI at the provider. Use HTTPS and `COOKIE_SECURE=true` outside local
HTTP development. The browser session stores no provider tokens; Authlib's
temporary authorization state and PKCE verifier live in server-side sessions.
Sessions expire after 12 hours by default; logout revokes the local session.
Provider-wide logout is not performed.

#### Local password accounts

Enable `password_enabled` and configure `smtp_host`, `smtp_port`, `smtp_from`, and
`smtp_security` (`starttls`, `tls`, or development-only `none`). Optional SMTP
credentials are `smtp_username` and `smtp_password`. `mail_encryption_key` must be
a Fernet key; generate it from `backend/` with:

```sh
.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Keep the key and provider/SMTP secrets outside version control. All API processes
must share the encryption key; changing it prevents delivery of already queued
messages, so drain the outbox or resend invitations after rotation. Password login
refuses to start without the required mail settings and valid encryption key.

In **Organization settings → Users**, administrators can create a local account
and email its setup link, resend setup invitations, reset a password, or change
the sign-in email. Sign-in emails are case-insensitive and unique among local
accounts, independent of editable profile contact addresses. Matching an external
account's email never merges accounts or identities. External sign-ins still
create pending accounts until an administrator grants membership.

Passwords use Argon2id and must contain 12–128 characters. Setup links are single-use,
expire after `invitation_ttl` (default 24 hours) or `password_reset_ttl` (default 1 hour),
and are invalidated by subsequent sends. Links carry their secret in the URL fragment,
which the frontend removes and retains in memory; refresh requires reopening the
complete email link. Opening a link does not consume it; submitting a valid new
password does. No self-service password recovery endpoint is provided.

An administrator reset or change of login email immediately invalidates the old
password and all browser sessions. The new address must be confirmed by setting
a password through its emailed link. Users can change their own password in
**Personal settings** by supplying the current password; other browser sessions
are revoked. Existing personal API tokens retain their independent lifecycle.
Disabling a human account also revokes its browser sessions permanently.

Credential management requires browser sessions and CSRF validation; API tokens
cannot create users, send recovery links, or set/change passwords. Password login
is limited to 10 attempts per account and 100 per direct client IP per 15 minutes.
Setup submissions and password changes are also limited. The direct peer address
is used; proxy-forwarded addresses are not blindly trusted, so proxy deployments
share that IP budget unless their trusted-proxy configuration supplies client IPs.

The database-backed email outbox is polled every 15 seconds by the API. Messages
are encrypted at rest, SMTP failures retry with exponential backoff up to eight
attempts, and bodies are erased on delivery, expiry/cancellation, or supersession.
User details show the latest delivery state; refresh to retrieve updates. Multiple
API processes coordinate with database locks. SMTP delivery is at-least-once: a
process crash after SMTP acceptance but before commit can cause a duplicate email
containing the same single-use link. Secrets are never included in API responses
or application log messages. Configure standard Python logging to retain INFO-level
credential lifecycle events with actor/user IDs.

For a new password-only instance, bootstrap the first administrator from `backend/`
after configuring mail and applying migrations:

```sh
.venv/bin/python -m app.cli bootstrap-admin --local \
  --name 'Administrator' --email admin@example.com
```

The command queues a setup email and refuses to run once an administrator exists.
`provision-user --local` similarly creates and invites a new local member. The API
must be running to deliver queued messages. Legacy external CLI provisioning is unchanged.

#### Ticket email notifications

Enable `notifications_enabled = true` (or `NOTIFICATIONS_ENABLED=true`) and configure
the SMTP settings and `mail_encryption_key` described above. Notifications work with
every authentication provider, independently of `password_enabled`. They are disabled
by default; enabling them requires valid mail configuration. Apply migrations and
restart the API after changing configuration.

- New tickets notify all project Owners, including inherited application administrators,
  as well as the author, assignee, and users mentioned in the description.
- Ticket changes notify the author, current assignee, discussion/activity participants,
  and users mentioned in the description or existing comments. Reassignment also
  notifies the previous assignee. Participants are comment and activity authors.
- Changes include metadata/title/description edits, comments, checklist toggles, and
  permanent attachment uploads. Draft uploads, failed writes, and no-op saves do not
  send notifications. Editor attachments are covered by the subsequent content save.
- Mentions use the editor's stable `@` user links, including links in comments. Plain
  names and code examples do not subscribe users. A removed mention stops contributing
  that recipient unless another recipient rule applies.
- Each user receives one email per event, including their own changes. Notifications
  go individually to current profile contact emails, independently of login addresses.
  Bots, inactive/pending users, and users without current project access are excluded.
  Eligibility is checked again immediately before delivery.

Emails contain the ticket reference/title, actor, change summary, and canonical link.
Comment notifications link to the discussion without copying the comment body.
They currently use English. Notification payloads are encrypted in a transactional
database outbox, so rolled-back changes never queue mail. The API polls every 15 seconds
and retries SMTP failures with exponential backoff for up to eight attempts. Payloads
are erased after delivery, cancellation, or final failure. Multiple API workers claim
separate rows with database locks. Delivery is at-least-once; a crash after SMTP
acceptance and before commit can cause a duplicate with the same Message-ID.

The upstream development mock v0.1.0 omits ID tokens and PKCE verification.
`.devcontainer/oidc_mock.py` adds these features in the mock, while keeping normal
ID-token verification in the application. Its image is digest-pinned because the
shim uses upstream internals. It permits only the configured tracker callback.

### Project and ticket URLs

Project lists use `/<project-slug>/`, for example `/product-development/`.
Sidebar navigation, project creation, filters, and returns from ticket details
all use this address. Requests without the trailing slash and old
`/projects/<uuid>` browser links redirect to the canonical path, preserving query
parameters and URL fragments. Unknown and inaccessible slugs show the same
project-not-found view without falling back to another project.

Ticket links use `/<project-slug>/<number>`, for example
`/product-development/1` for `APP-1`. The number is scoped to its project; UUIDs
remain internal API identifiers. Every work item API response includes `number`,
`project_slug`, and the canonical relative `web_url`.

Project slugs are unique and persisted. At project creation, optionally provide
**Project URL slug**, or leave it empty to generate one from the project name.
Automatic slugs normalize accents and punctuation and receive a numeric suffix
on collision. Slugs use lowercase ASCII letters, digits, and single hyphens;
application paths such as `api`, `items`, `projects`, and `settings` are reserved.
Migration `0003` backfills existing project slugs without changing ticket numbers
or IDs.

Opening a ticket from the list uses the same path with `?view=panel` and preserves
the list filters. Closing the panel returns to that filtered list. **Open page**
uses the canonical path without panel state. Old `/items/<uuid>` links and
`/projects/<uuid>?item=<uuid>` links redirect to the new paths.

The API resolves a readable link with
`GET /api/v1/projects/by-slug/<slug>/items/<number>` and checks project permissions.
Existing UUID-based API endpoints remain available.

### Work item filtering and sorting API

`GET /api/v1/projects/{project_id}/items` accepts `q` (title/description search),
repeated `status`, `label`, `priority`, `type`, and `assignee` parameters. Assignee
values are user UUIDs, `me` (the current authenticated user), or `none` (unassigned).
Values within each dimension use OR; dimensions combine with AND. Omitting a filter
means no restriction in the API. The browser applies its Open + In progress default
separately and preserves explicit all-status selection as `?status=` in browser URLs.

`sort` accepts `updated`, `created`, `title`, `priority`, or `due_date`; optional
`direction` accepts `asc` or `desc`. Without direction, title/due date default to
ascending and other fields to descending, preserving existing API behavior.
Priority sorts by Low, Medium, High, Urgent; due dates always put nulls last.
An ID tie-breaker keeps pagination deterministic for equal sort values.

`GET /api/v1/projects/{project_id}/item-assignees` supplies people currently assigned
to work items in that project, including historical assignees who can no longer
receive new assignments. It requires project read access and exposes the same
basic assignee representation as work items, without email addresses. It is separate
from the write-protected `/assignees` endpoint used to select new assignments.

### Personal settings

Open **Personal settings** using the profile/gear link in the top-right corner,
or go to `/settings`. Every authenticated user can edit their own profile,
including readers and users awaiting organization membership.

Choose from six interface colors (green, blue, purple, teal, amber, rose) and five
backgrounds (white, mist, mint, sand, slate). Colors preview immediately; **Save
settings** persists the profile and appearance on the account for other sessions
and devices. **Discard changes** or leaving the page restores the saved theme.
Signing out restores green/white so preferences never leak to another account.

Choose **Interface language → English / Čeština** to preview a language immediately,
then **Save settings** to keep it on your account across sessions and devices.
Discarding changes or leaving settings restores the saved language. English is
the default for existing and new accounts. The login and password-setup pages also
offer a language selector; their choice is remembered in this browser. Signing in
loads the account's language, while signing out keeps that language on the login page.
Apply migration `0012` before starting the updated backend.

Interface labels, enum display names, editor tools, dates, generated activity and
validation feedback are localized. Ticket content, comments, names, labels and
filenames keep their original text. URLs and API enum values are language-independent.
English source messages serve as translation keys and fallback text in
`frontend/src/i18n.ts`; Czech translations live in `frontend/src/locales/cs.json`.
Use `t()` for interface text and named placeholders for dynamic values. Translate
option labels without changing their values. Catalog and interface-coverage checks
run with `npm test` in `frontend/`.

Profile pictures accept PNG, JPEG, GIF, and WebP up to 5 MB and 16 megapixels.
They are cropped to a square, normalized to a 256×256 PNG, and saved immediately.
The avatar appears in the header, comments, and activity; removing it restores
the initial-letter icon. Avatar bytes are stored in PostgreSQL and served only
to authenticated users. Organization membership is required to view another
member's avatar.

Name and email are local profile/contact data. Changing them does not modify
OIDC identity or grant membership, and later sign-ins do not overwrite them.
The settings API is `/api/v1/users/me`; avatar upload/removal uses
`/api/v1/users/me/avatar`. Apply migration `0002` before starting updated code.

### API tokens and bot accounts

Every organization member can create personal tokens under **Personal settings →
Personal API tokens**. Each token has a name, read-only or read/write permissions,
expiration (30 days by default, up to one year), revocation, and last-used metadata.
Copy the full secret when it is created; later listings expose only its prefix
and metadata. The database stores only a SHA-256 hash of the random secret.

Application admins open **Organization settings → Bots**. Bots are application
members with their own name and API tokens, with no password or OIDC/browser login.
Only application admins manage bots and their project access. Assign Reporter or
Read-only per project; bots cannot be owners. Tokens and project permissions are
both enforced, so a bot needs Reporter membership and a write-scoped token to make
changes. Bot comments and activity display a **Bot**
badge. Disabling a bot revokes all its tokens; re-enabling does not restore them.

Use `Authorization: Bearer <token>` for API requests. Browser cookies and CSRF
tokens are not needed with valid bearer authentication. Tokens never exceed the
owner's current permissions, and invalid bearer credentials never fall back to
browser cookies. Credential and bot management require a browser session; tokens
cannot issue additional credentials. Browser logout does not revoke personal
tokens. Apply migration `0004` before starting updated application code.

See [API and AI integration examples](docs/api-integrations.md) for curl/Python
requests, endpoint details, and scope behavior. OpenAPI provides the **ApiToken**
bearer authorization scheme at `/api/v1/docs`.

### Visual editor

Work item descriptions (including the creation form) and comments use a shared
Tiptap WYSIWYG editor. Users format content directly with toolbar controls and
see images and links while editing, without needing Markdown syntax. Tables
provide contextual row/column controls; checklist boxes are interactive while
editing. The editor is loaded on demand.

The API and database continue to store Markdown. Existing content is parsed into
the visual editor and serialized back on edits; no database migration is needed.
Each editor and the read-only renderer use isolated Marked parsers to prevent
Tiptap's custom checklist tokens from leaking into normal Markdown rendering.

### Mentions and ticket references

In any description or comment editor:

- Type `@` and part of a person's display name, then choose a user.
- Type `#` to search for a ticket by number, reference (for example `APP-123`),
  or title. Numbers use the current project; a full reference can select another
  accessible project. Suggestions in a private project only offer users who
  have access to that project.
- Use the mouse, Arrow Up/Down, Enter, or Tab to choose a suggestion. Escape
  dismisses only the suggestion menu and preserves the draft.
- Paste a ticket URL from this instance to insert a chip showing its reference,
  title, and status. Canonical and legacy UUID/panel URLs are supported.

References work in the creation form, edit form, and comments. Saved `#123` and
`#APP-123` text also resolves when displayed. Code examples, email addresses,
external URL fragments, and custom link labels remain literal. Clicking a
mention opens the member's basic profile; clicking a ticket opens its canonical
ticket URL. Links in the editor open in another tab to preserve the draft.

The Markdown/API representation uses neutral labels and stable IDs:
`[@user](/users/<uuid>)` and `[Ticket](/items/<uuid>)`. Names, titles, statuses, and
canonical paths are resolved under the current viewer's permissions each time
the content is displayed. This keeps references current after renames and status
changes without storing private ticket metadata inside another ticket's text.
Unavailable or inaccessible references display a neutral placeholder.

Reference API endpoints:

- `GET /api/v1/references/users?q=...&project_id=...`
- `GET /api/v1/references/tickets?q=...&project_id=...`
- `GET /api/v1/references/users/<uuid>` for the organization-visible basic profile
- `POST /api/v1/references/resolve` with `tickets` and `users` UUID arrays, up to
  50 per array, for batched read-only resolution

Search and resolution require organization membership. User results contain
display name, role, avatar, and profile link, without contact email or personal
appearance preferences. No database migration is required.

### Checklist updates

Users with project write access can check or uncheck tasks directly in the
displayed description and in any comment, without opening the editor. Each
change saves immediately and adds an activity entry with the acting user, time,
checked/unchecked state, task label, and description/comment source. Comment
authorship is preserved even when another member toggles its checklist.
Readers see disabled checkboxes, and the API independently enforces write access.

Only the Markdown task marker changes; surrounding formatting, links, attachments,
and line endings remain intact. Nested, numbered, and quoted task lists work;
code examples and raw HTML inputs are not interactive tasks. Unsaved comment
drafts remain intact during quick updates. Quick toggles are disabled while the
description is being edited.

API routes use zero-based task indices:

- `PATCH /api/v1/items/<uuid>/checklist/<index>`
- `PATCH /api/v1/items/<uuid>/comments/<comment-uuid>/checklist/<index>`

Send `{ "checked": true, "version": "<content-sha256>" }`, using the work item's
`description_version` or the comment's `body_version` from the discussion API.
Updates are transactional with their activity entry. Stale content returns HTTP
409 instead of overwriting newer changes; the UI reloads the latest content so
the user can retry. A request that leaves the state unchanged adds no duplicate
activity. No database migration is needed for this feature.

### Attachments

Upload files when creating a work item, editing its description, or writing a
comment. File selection, drag-and-drop, and image paste insert visible images or
file links at the cursor. The insertion point survives typing during the upload.
Creation and save actions wait until uploads finish.

Editor uploads are temporary and visible only to their uploader until the
description or comment is saved. Saving atomically attaches referenced uploads
to that ticket and adds upload activity. Files removed from a draft, canceled
tickets, and unsubmitted comments remain temporary. The API automatically cleans
up unconfirmed uploads older than 24 hours at startup and once per hour. Confirmed
attachments are retained even if their link is later removed from saved content.
For a manual cleanup, run `.venv/bin/python -m app.attachments` from `backend/`.

Apply migration `0006` before starting the updated API. Integrations can upload
temporary files with `POST /api/v1/projects/<uuid>/attachments` before ticket
creation, or `POST /api/v1/items/<uuid>/attachments?pending=true` for an existing
ticket, then include the returned URL in the saved Markdown. The existing item
upload endpoint without `pending=true` still creates a permanent standalone
attachment for backwards compatibility. Existing attachments remain permanent.

Only PNG, JPEG, GIF, and WebP are served inline; other formats are downloads.
Attachment bytes are stored outside the web root and downloads always check
current organization/project access. Back up both PostgreSQL and `var/attachments`.

The shared Chromium currently blocks saving downloads from this local HTTP
origin, although the endpoint returns the correct file and headers. HTTPS is
required for an end-to-end browser download check. Image display and uploads are
verified in the current environment.

## Verification

Backend tests, from `backend/`:

```sh
.venv/bin/python -m pytest -q
```

Tests use isolated in-memory SQLite databases without touching development data.
They cover access isolation, CSRF, session expiry/revocation, account identity
separation, upload limits, and cryptographic OIDC validation including tampered
signatures, issuer, audience, nonce, state, and expiry.
Personal-settings tests additionally cover ownership, role/identity boundaries,
CSRF, profile validation, avatar decoding/resizing and rejected uploads, and
preservation of local profile changes after OIDC sign-in.
Checklist tests cover actor attribution, toggling another author's comment,
read-only/private-project isolation, CSRF, stale versions, no-op updates, task
indexing, and exact source preservation including Unicode and CR/LF boundaries.
Reference tests cover permission-filtered suggestions and batch resolution,
private metadata isolation, current titles/statuses, and basic profile exposure.
API-token tests cover one-time secrets/hashing, read/write restrictions, expiry,
revocation, last-used metadata, ownership, role changes, bearer/cookie isolation,
CSRF behavior, bot-only project access, and bot activity attribution.

Frontend editor regression tests (Node.js 24), type check, and production build,
from `frontend/`:

```sh
npm test
npm run build
```

Editor tests cover checklist parser isolation across multiple editors and
semantic Markdown round-trips for formatting, lists, checklists, code, tables,
and attachment URLs. Browser checks additionally cover visual formatting,
undo/redo, links, file selection/drop, image paste at the cursor, saved content,
reader access, and desktop/mobile layouts.
Reference regressions additionally cover stable-ID Markdown round-trips,
same-origin URL recognition, custom labels, and asynchronous paste ranges. Browser
verification includes keyboard suggestions, Escape/draft preservation, paste
while typing, undo or replacement before lookup completion, and reader isolation.

Real PostgreSQL migration/model alignment and the PostgreSQL JSONB label filter
are additionally checked against the development environment. Core UI flows are
verified in shared `chromium4devcontainer`; see `docs/agent-memory.md` for durable
environment findings.
