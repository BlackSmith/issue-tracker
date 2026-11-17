# API tokens, automation, and AI integrations

The tracker exposes the same REST API used by its frontend, under `/api/v1`.
Use an individual token for each integration. OpenAPI documentation is available
at `/api/v1/docs`; its **Authorize** control accepts the token as an HTTP bearer
credential.

## Choose an identity

### Personal token

Open **Personal settings → Personal API tokens**. Choose a name, permissions, and
expiration, then copy the one-time secret. API changes are attributed to your
account. Reader accounts can create only read tokens. Later changes to the
account's membership, role, or project access also affect existing tokens.

### Bot account

An organization administrator opens **Bots** and:

1. Creates a named bot, for example `AI issue assistant`.
2. Assigns Reporter or Read-only access per project. Bots are application members and cannot be project owners or application admins.
3. Grants explicit project access, read-only or read/write.
4. Creates a named bot token with the needed scope and expiration.

Bot credentials authenticate the bot, not the administrator who issued them.
Bots have no OIDC identity or browser login and receive no implicit access to
organization-visible projects. Their comments, checklist updates, and ticket
changes use the bot's stable internal user ID and show a Bot badge in the UI.
Account and project role ceilings remain in effect even if the token has write
scope. Removing project access takes effect on subsequent requests.

Disabling the bot revokes all its credentials. After re-enabling, issue a new
token; old credentials remain revoked. Bot records and historical authorship are
preserved.

## Scopes and lifecycle

| Scope | Access |
| --- | --- |
| `read` | Read accessible projects, work items, comments, activity, attachments, and references |
| `write` | Includes read plus existing create/edit/comment/upload/checklist operations allowed by the owner's role |

The batched read-only `POST /references/resolve` accepts read scope. All other
mutations require write scope and the applicable resource permissions. Personal
tokens inherit the human owner's access; bot project access is explicitly
assigned. A scope never grants an organization or project role.

Expiration is required: the default is 30 days, and the maximum is one year.
Revocation is immediate for subsequent requests. Last-used metadata records
authenticated use. The secret is returned only by the creation response and is
stored only as a SHA-256 hash with a non-secret display prefix.

Bearer requests do not create browser cookies and do not require CSRF headers.
If Authorization is present but invalid, a browser session cannot substitute for
it. Browser sign-out does not revoke API tokens. Creating/revoking credentials
and managing bot accounts require an authenticated browser session; bearer
tokens cannot create more credentials or turn into a browser session.

## curl examples

Set the instance address and a token copied from the creation screen:

```sh
export TRACKER_URL="http://host.docker.internal:5301"
export TRACKER_TOKEN="<your token>"
```

List accessible projects:

```sh
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $TRACKER_TOKEN" \
  "$TRACKER_URL/api/v1/projects"
```

Resolve a browser ticket address to its API UUID:

```sh
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $TRACKER_TOKEN" \
  "$TRACKER_URL/api/v1/projects/by-slug/product-development/items/1"
```

Add an automation comment using the returned `id` and a write token:

```sh
export TICKET_ID="<work item UUID>"
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $TRACKER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body":"Automated analysis completed.\n\n- [ ] Review the proposed change"}' \
  "$TRACKER_URL/api/v1/items/$TICKET_ID/comments"
```

Send the bearer header on attachment requests as well. Tokens are accepted only
through Authorization, not URL query parameters. Use the HTTPS instance address
for deployed integrations; the HTTP address above is the local development API.

## Python example for an AI tool

An AI integration can use an HTTP tool with the bearer header and the documented
OpenAPI operations. A server-side connector can also use Python's standard
library without any tracker-specific SDK:

```python
import json
import os
from urllib.request import Request, urlopen

base_url = os.environ["TRACKER_URL"].rstrip("/") + "/api/v1"
token = os.environ["TRACKER_TOKEN"]


def api(method, path, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        base_url + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


ticket = api("GET", "/projects/by-slug/product-development/items/1")
api("POST", f"/items/{ticket['id']}/comments", {
    "body": "AI-assisted summary: review the reproduction steps and add a regression test."
})
```

Ticket descriptions and comment bodies use Markdown at the API boundary. Ticket
UUIDs remain the identifiers for update/comment/upload operations; browser URLs
use the project slug and project-scoped number. Checklist mutations additionally
require the current content version to prevent stale updates. Ticket `PUT`
updates use the complete work-item payload; retrieve the current item first and
preserve fields that the integration does not intend to change.

## Credential management endpoints

These endpoints are used by the browser UI with session cookies and CSRF:

| Endpoint | Purpose |
| --- | --- |
| `GET/POST /api/v1/tokens` | List/create the current human member's tokens |
| `DELETE /api/v1/tokens/<uuid>` | Revoke one of the current member's tokens |
| `GET/POST /api/v1/bots` | Administrator list/create bot accounts |
| `PUT /api/v1/bots/<uuid>` | Administrator rename/change role/enable/disable a bot |
| `GET /api/v1/bots/<uuid>/projects` | List assigned projects and effective roles |
| `PUT/DELETE /api/v1/bots/<uuid>/projects/<project-uuid>` | Grant/update/remove project access |
| `GET/POST /api/v1/bots/<uuid>/tokens` | Administrator list/create bot tokens |
| `DELETE /api/v1/bots/<uuid>/tokens/<token-uuid>` | Administrator revoke a bot token |

## Response codes

- **401:** missing, invalid, expired, or revoked credentials; inactive or
  deprovisioned token owner.
- **403:** insufficient token scope, read-only/project restrictions, or an
  operation requiring a browser session/administrator.
- **404:** missing or inaccessible resource, including an unassigned bot project.
- **409:** stale checklist content or an inactive account at token issuance.
- **422:** invalid input, scope, or expiration.
