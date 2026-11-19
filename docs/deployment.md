# Deployment and configuration

## Container layout

The root `Dockerfile` has two runtime targets:

- `api`: Python 3.13, installed backend requirements, FastAPI/Uvicorn, Alembic,
  and the administration CLI. It runs as UID/GID `10001`, listening on port 8000.
- `frontend` (the default target): a Vue production build made with Node.js 22,
  served by unprivileged Nginx on port 8080. Nginx proxies `/api/` to `api:8000`
  and falls back to `index.html` for client-side routes, including direct ticket URLs.

`docker-compose.yml` adds PostgreSQL 18 and a one-shot `migrate` service. Startup
waits for PostgreSQL, successful migrations, and then API health before exposing
the frontend. Only the frontend port is published. The API also runs email delivery
every 15 seconds and pending-attachment cleanup at startup and hourly; the current
increment does not require a separate worker. Use one API instance with this example.

Build the images independently, if desired:

```sh
docker build --target api -t issue-tracker-api:local .
docker build --target frontend -t issue-tracker-frontend:local .
```

The frontend uses relative `/api/v1` requests. There are no frontend build-time
environment variables; the same images can be used with different public hostnames.
Do not run the frontend target alone without an API reachable as `api`.

## First startup

Use Docker Engine with the Docker Compose v2 plugin. Run commands from the repository root.

1. Copy `.env.example` to `.env`:

   ```sh
   cp .env.example .env
   docker compose build
   docker compose run --rm --no-deps api python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
   ```

2. Edit `.env`. Set a strong PostgreSQL password in both `POSTGRES_PASSWORD` and
   `DATABASE_URL`, configure an actual SMTP server, and paste the generated key into
   `MAIL_ENCRYPTION_KEY`. The initial example enables local password accounts, which
   require SMTP for invitations and administrator-initiated recovery. No default
   administrator or password is installed.
3. For local testing, keep both public URLs at `http://localhost:8080` and
   `COOKIE_SECURE=false`. For deployment, configure the public HTTPS origin as
   described below before inviting users.
4. Validate and start:

   ```sh
   docker compose config --quiet
   docker compose up -d
   docker compose ps -a
   docker compose logs migrate api
   ```

5. Create the first local administrator:

   ```sh
   docker compose exec api python -m app.cli bootstrap-admin --local --name "Administrator" --email admin@example.com
   ```

   The command queues an invitation email. Follow its single-use link to set a
   password, then sign in at `http://localhost:8080` (or your configured public URL).
   `bootstrap-admin` refuses to run again once an administrator exists. Further
   local users can be created by an administrator in Organization settings.

API documentation is at `/api/v1/docs`; the health endpoint is `/api/v1/health`.
The API health check verifies HTTP availability; it does not query the database or
verify SMTP or identity-provider availability. `/healthz` checks Nginx only.

For an external-provider-only installation, set `PASSWORD_ENABLED=false`, configure
OIDC or Facebook, and use external identity provisioning below. SMTP and the Fernet
key are optional only when both password login and ticket notifications are disabled.

## Configuration sources

Application settings use this precedence: process environment, backend working-directory
`.env`, TOML selected by `TRACKER_CONFIG`, then application defaults. Settings are read
at process startup; recreate services after configuration changes.

The root `.env` is read by Compose for interpolation and passed to `api` and `migrate`
via `env_file`. It is not copied into either image. Compose-only variables are ignored
by application settings. Quote values containing `$` with single quotes in `.env`
when they must be literal. Keep the file private and out of version control.

### Compose settings

| Variable | Example default | Meaning |
| --- | --- | --- |
| `POSTGRES_DB` | `tracker` | Database created on the first start of an empty PostgreSQL volume. |
| `POSTGRES_USER` | `tracker` | PostgreSQL owner created on first start. |
| `POSTGRES_PASSWORD` | Required | Initial database password; keep it consistent with `DATABASE_URL`. |
| `DATABASE_URL` | Required | SQLAlchemy URL, such as `postgresql+psycopg://tracker:password@db:5432/tracker`. Percent-encode URL-special characters in credentials. |
| `BIND_ADDRESS` | `127.0.0.1` | Host interface for the published frontend port. |
| `HTTP_PORT` | `8080` | Host frontend port. |
| `IMAGE_TAG` | `local` | Tag for both locally built application images. |

Changing `POSTGRES_*` does not update credentials inside an existing database volume.
The application supports an external PostgreSQL server through `DATABASE_URL`; adapt
the example Compose dependencies and remove its `db` service when using one.

### Application settings

All environment variable names below map to lowercase TOML keys, for example
`COOKIE_SECURE` becomes `cookie_secure = true`. Defaults here are application
defaults unless a Compose override is noted.

| Variable | Default | Meaning |
| --- | --- | --- |
| `TRACKER_CONFIG` | Unset | Absolute container path to a mounted TOML file. |
| `DATABASE_URL` | Development placeholder | PostgreSQL SQLAlchemy URL; explicitly required by the deployment Compose file. |
| `APP_BASE_URL` | `http://host.docker.internal:5374` | Public frontend origin, without a trailing slash; used for links, redirects, and CSRF origin checks. Set explicitly for deployment. |
| `API_BASE_URL` | `http://host.docker.internal:5301` | Public API origin, without `/api/v1` or trailing slash. In this Compose layout use exactly the same origin as `APP_BASE_URL`. |
| `SESSION_COOKIE` | `issue_tracker_session` | Browser session cookie name. |
| `COOKIE_SECURE` | `false` | Send the session cookie only over HTTPS when true. Enable for HTTPS deployments. |
| `SESSION_TTL` | `43200` | Browser session lifetime in seconds (12 hours). |
| `ATTACHMENT_DIR` | Repository `var/attachments` | Local attachment directory; Compose overrides this to `/data/attachments` on a persistent volume. |
| `MAX_UPLOAD_BYTES` | `20971520` | Per-file upload limit (20 MiB). Nginx allows 25 MiB request bodies including multipart overhead; increase `client_max_body_size` in `deploy/nginx.conf` and rebuild the frontend image when raising this limit. |
| `PROVIDERS` | `[]` | JSON array of provider definitions; see below. |
| `PASSWORD_ENABLED` | `false` | Enable administrator-created local password accounts. Requires SMTP and a valid Fernet key. |
| `NOTIFICATIONS_ENABLED` | `false` | Enable ticket email notifications. Requires SMTP and a valid Fernet key independently of password login. |
| `SMTP_HOST` | Empty | SMTP hostname reachable from the API container. |
| `SMTP_PORT` | `587` | SMTP port. |
| `SMTP_SECURITY` | `starttls` | `starttls`, `tls` (implicit TLS), or `none`. |
| `SMTP_USERNAME` | Empty | Optional SMTP authentication username. |
| `SMTP_PASSWORD` | Empty | SMTP authentication password. |
| `SMTP_FROM` | Empty | Sender address, optionally with a display name. |
| `MAIL_ENCRYPTION_KEY` | Empty | Fernet key for encrypted password and notification outbox payloads. Preserve it across restarts and backups. |
| `INVITATION_TTL` | `86400` | Password setup link lifetime in seconds, from 300 to 604800. |
| `PASSWORD_RESET_TTL` | `3600` | Administrator-issued recovery link lifetime in seconds, from 300 to 86400. |

Password invitations use the account's separate login email; ticket notifications use
the profile contact email. Users cannot request password recovery themselves.
There is no automatic outbox key rotation: replacing `MAIL_ENCRYPTION_KEY` prevents
decryption of previously queued messages, so retain the key with your deployment secrets.

### Single OIDC provider (legacy environment configuration)

| Variable | Default | Meaning |
| --- | --- | --- |
| `OIDC_ISSUER` | Empty | Verified provider issuer/discovery URL base. |
| `OIDC_CLIENT_ID` | Empty | Registered client ID. Both issuer and client ID are required to enable this provider. |
| `OIDC_CLIENT_SECRET` | Empty | Secret for a confidential client, if applicable. |
| `OIDC_NAME` | `Company SSO` | Login button label. |
| `OIDC_REDIRECT_URI` | `http://host.docker.internal:5301/api/v1/auth/oidc/callback` | Exact registered public callback URL; set to `<API_BASE_URL>/api/v1/auth/oidc/callback`. |

The issuer must be reachable from both the browser and API container, and match the
provider's advertised issuer. `localhost` inside the container refers to that container.
The development mock is not part of this deployment Compose file.

### Multiple providers, Facebook, and TOML

A nonempty `PROVIDERS` list replaces the legacy `OIDC_*` provider configuration.
An empty list does not disable legacy OIDC: clear `OIDC_ISSUER` and `OIDC_CLIENT_ID`
for a password-only deployment. Each provider has these fields:

| Field | Meaning |
| --- | --- |
| `id` | Stable unique lowercase ID matching `^[a-z][a-z0-9_-]{0,39}$`; `password` is reserved. |
| `name` | Login button label. |
| `type` | `oidc` (default) or `facebook`. |
| `client_id` | Required client/Meta app ID. |
| `client_secret` | Optional OIDC secret; required for Facebook unless supplied through `client_secret_env`. |
| `client_secret_env` | Name of a process environment variable holding the secret; when set, that variable must contain a value. |
| `issuer` | Required OIDC issuer. |
| `graph_version` | Facebook Graph API version; default `v24.0`. |

For example, add these variables to `.env`:

```dotenv
PROVIDERS='[{"id":"company","name":"Company SSO","type":"oidc","issuer":"https://identity.example.com/realms/company","client_id":"issue-tracker","client_secret_env":"COMPANY_CLIENT_SECRET"},{"id":"facebook","name":"Facebook","type":"facebook","client_id":"your-meta-app-id","client_secret_env":"FACEBOOK_CLIENT_SECRET","graph_version":"v24.0"}]'
COMPANY_CLIENT_SECRET=replace-with-client-secret
FACEBOOK_CLIENT_SECRET=replace-with-meta-app-secret
```

Register `<API_BASE_URL>/api/v1/auth/company/callback` with the OIDC provider and
`<API_BASE_URL>/api/v1/auth/facebook/callback` with Meta. Facebook requests
`public_profile` and `email`. Configure Meta app availability, test users, and permissions
in the Meta developer console. Live Facebook verification requires your own Meta app.

Alternatively, copy `backend/config.example.toml` to `deploy/config.toml`, customize
the provider list, and add `TRACKER_CONFIG=/config/tracker.toml` to `.env`. Create a
`docker-compose.override.yml` with a read-only mount on **both** application services:

```yaml
services:
  api:
    volumes:
      - ./deploy/config.toml:/config/tracker.toml:ro
  migrate:
    volumes:
      - ./deploy/config.toml:/config/tracker.toml:ro
```

Remove variables from `.env` when TOML should control their values; environment always
takes precedence. `client_secret_env` reads process environment, so include the referenced
variables in `.env`. The example TOML enables both password login and notifications,
and includes Facebook; remove unused providers and supply the required mail/key settings.

External authentication alone does not grant organization membership. Bootstrap an
external administrator using the verified issuer and subject (never email matching):

```sh
docker compose exec api python -m app.cli bootstrap-admin --issuer https://identity.example.com/realms/company --subject verified-subject --name "Administrator" --email admin@example.com
docker compose exec api python -m app.cli provision-user --issuer https://identity.example.com/realms/company --subject another-verified-subject --name "Member" --email member@example.com --role member
```

Facebook identities use `https://www.facebook.com/<meta-app-id>` as issuer and the
Meta-app-scoped user ID as subject. Keep provider IDs and Meta app IDs stable.

## HTTPS and reverse proxy

For public deployment, terminate TLS at an external reverse proxy forwarding to
the published frontend port. Set `APP_BASE_URL` and `API_BASE_URL` to the same public
HTTPS origin (for example `https://tracker.example.com`), `COOKIE_SECURE=true`, and
update all registered authentication callbacks. Keep deployment at the origin root;
this example does not configure a URL subpath.

The default published address is loopback, suitable for a proxy on the Docker host.
If your proxy runs on another host or container, adapt networking or `BIND_ADDRESS`
so it can reach the frontend. API and PostgreSQL do not need published ports.
Uvicorn ignores forwarded headers in this example; authentication redirects use the
explicit configured public URLs. Ensure an outer proxy also permits your upload size.

## Operations, updates, and backups

Useful commands:

```sh
docker compose logs -f api
docker compose exec api python -m app.attachments
docker compose restart api
docker compose down
```

`restart` does not reload changed environment values; use `docker compose up -d
--force-recreate` to apply them. `docker compose down` keeps named volumes; adding
`--volumes` deletes the database and attachments.

Before upgrading, back up PostgreSQL, attachments, and deployment secrets, including
the Fernet key. Stop application traffic while taking a coordinated backup or restoring
so the database and attachment files represent the same state. Avatars are in PostgreSQL;
ticket attachments are in the `attachments` volume. Database backup example:

```sh
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > tracker.dump
```

Use your volume backup tooling for both named volumes, or pair the logical database
dump with an attachment-volume archive. Do not copy a live PostgreSQL data directory
as an ordinary filesystem backup. Test restores into a separate deployment.

Upgrade the source, then run:

```sh
docker compose stop frontend api
docker compose build
docker compose run --rm migrate
docker compose up -d
docker compose ps -a
```

Resolve migration failures before starting the application. The API does not migrate
the schema itself; Compose's `migrate` service runs `alembic upgrade head`. For deployments
outside Compose, run that command once with the API image and the same configuration
before starting the new API. Restoring an older image may require restoring the matching
database backup; do not assume schema migrations can safely be reversed.

Named attachment volumes are initialized with the image directory's UID/GID `10001`.
When replacing the volume with a host bind mount, create it with ownership writable
by that UID/GID. Keep the attachment path consistent between API and maintenance commands.
