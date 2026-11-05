# Development environment

Open the workspace with VS Code Dev Containers and run **Dev Containers: Rebuild Container** after changing this configuration.

## Services and tools

- Python 3.13 development container with Node.js 24, npm, Git, and access to the host Docker daemon.
- PostgreSQL 18 with the existing persistent `db-data` volume.
- Adminer on the Compose network at `http://adminer:8080`.
- Keycloak Mockup with project-specific OIDC identities.
- Shared `chromium4devcontainer` browser and existing OpenCode volumes are preserved by `docker-compose.local.yml`.

The local override requires the host's `WAYLAND_DISPLAY` and `XDG_RUNTIME_DIR` environment variables. The Dev Container starts its dependent database and OIDC mock automatically.

The post-create script installs backend dependencies into `backend/.venv` when `backend/requirements.txt` exists, and frontend dependencies when `frontend/package.json` exists. Missing application directories are expected before bootstrapping. Node.js is installed by the Dev Container feature, not through the distribution's npm packages.

## Development addresses

| Purpose | Address |
| --- | --- |
| Frontend | `http://host.docker.internal:5374` |
| Backend | `http://host.docker.internal:5301` |
| OIDC mock | `http://host.docker.internal:5152` |
| OIDC issuer | `http://host.docker.internal:5152/realms/issue-tracker` |
| Discovery | `http://host.docker.internal:5152/realms/issue-tracker/.well-known/openid-configuration` |
| OIDC callback | `http://host.docker.internal:5301/api/v1/auth/oidc/callback` |

The frontend listens on `0.0.0.0:5374`; the backend listens on `0.0.0.0:5300` (published as host port `5301`). Start them using the commands in the root `README.md`. Vite proxies `/api` to the backend. Environment variables in Compose configure the backend.

Both the backend and shared browser resolve `host.docker.internal` through the host gateway. Use the same advertised issuer for discovery, token validation, and browser redirects; do not replace it with an internal service URL or browser localhost. Port `5152` avoids the existing mock on host port `5151` used by another project. A browser on the host may require its own `host.docker.internal` DNS/hosts mapping to the host address.

OIDC client ID: `issue-tracker`. The mock does not require a client secret. The development shim `oidc_mock.py` adds signed ID tokens with nonce, validates S256 PKCE and code/client/redirect binding, and permits the tracker callback above. The application independently verifies state, nonce, issuer, audience, expiry, and signature through Authlib. The upstream v0.1.0 image is pinned by digest because the shim uses its internals.

## Test identities

| Username | Password | Intended application role |
| --- | --- | --- |
| `admin` | `admin123` | Administrator |
| `member` | `member123` | Member |
| `reader` | `reader123` | Reader |

Subjects are stable UUIDs in `oidc-mock.yaml`. These identities do not automatically confer application roles or organization membership. Provision membership and roles with the CLI commands in the root `README.md`. Passwords and HTTP settings are for local development only.

## Verification

Validate Compose without modifying running services:

```sh
docker compose -f .devcontainer/docker-compose.yml config --quiet
```

Rebuild the Dev Container to apply features and container environment changes. Do not remove database volumes when rebuilding. Verify frontend flows with the existing shared Chromium via the browser agent.
