# Issue Tracker

A standalone, organization-scoped issue tracker inspired by GitLab Work Items.
Built with FastAPI, PostgreSQL, and Vue 3. The interface and API use English.

## Current increment

- Generic OIDC login through Authlib with server-side sessions, session rotation,
  CSRF protection, state, nonce, and S256 PKCE.
- Stable internal accounts and separate issuer/subject identities. Matching email
  addresses never merge accounts or confer organization membership.
- Organization administrator, member, and reader roles; organization-visible and
  private projects; administrator project settings for name, description, visibility,
  and membership management, available from the work item list.
- Personal settings for display name, contact email, profile picture, interface
  accent color, and application background. Green is the default accent.
- Project-scoped work item numbers, visually edited descriptions, types, fixed statuses,
  priorities, labels, due dates, editing, and activity history.
- Metadata activity records previous and new values, including assignee names,
  first-time values, and explicit clearing of dates, labels, and assignees.
- Explicit organization and project label definitions with names, colors, and
  descriptions; projects automatically inherit all organization labels. Ticket
  creation, editing, and filtering use existing definitions.
- Search, status/label filtering, sorting, pagination, and shareable filter URLs.
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

This is an initial development increment. Assignees, invitations and identity
linking in the UI, multiple simultaneously configured providers, trusted-provider
automatic membership, hierarchy/relationships, milestones, Kanban, saved views,
webhooks/worker, and production Docker deployment are planned.
Facebook Login is outside the current scope. The provider protocol allows a later
provider-specific OAuth adapter without changing internal account management.

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
  --name 'Development Reader' --email reader@example.test --role reader
```

`provision-user` also updates the role of an existing issuer/subject identity.
It does not match accounts by email. For an already signed-in pending account,
use the same verified issuer and subject to grant membership to that account.
Project access can then be set with the **Members** button by an administrator.
A global reader cannot gain write access through a project role.

### Label management

Administrators manage shared labels in **Organization settings → Labels** and
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
when running in the backend directory. Compose sets the development defaults.
An example is provided at `backend/.env.example`.

For another OIDC provider, configure `OIDC_ISSUER`, `OIDC_CLIENT_ID`,
`OIDC_CLIENT_SECRET`, `OIDC_NAME`, and `OIDC_REDIRECT_URI`. Register that exact
callback URI at the provider. Use HTTPS and `COOKIE_SECURE=true` outside local
HTTP development. The browser session stores no provider tokens; Authlib's
temporary authorization state and PKCE verifier live in server-side sessions.
Sessions expire after 12 hours by default; logout revokes the local session.
Provider-wide logout is not performed.

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

### Personal settings

Open **Personal settings** using the profile/gear link in the top-right corner,
or go to `/settings`. Every authenticated user can edit their own profile,
including readers and users awaiting organization membership.

Choose from six interface colors (green, blue, purple, teal, amber, rose) and five
backgrounds (white, mist, mint, sand, slate). Colors preview immediately; **Save
settings** persists the profile and appearance on the account for other sessions
and devices. **Discard changes** or leaving the page restores the saved theme.
Signing out restores green/white so preferences never leak to another account.

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

Administrators can open **Bots** in the header or **Manage bot accounts** in
settings. Bots have their own name, reader/member role, and API tokens, with no
password or OIDC/browser login. Explicitly assign projects before using a bot:
organization-visible projects are not granted automatically. Tokens and project
permissions are both enforced, so a bot needs a write-capable account, project
membership, and token to make changes. Bot comments and activity display a **Bot**
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
