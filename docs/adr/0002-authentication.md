# 0002. Authentication

## Status

Accepted for milestone M2. The production identity provider is a decision, not
an implementation.

## Context

The MCP authorization model treats the HTTP server as a resource server. The
Python SDK asks for a `TokenVerifier` and `AuthSettings` together. stdio has no
place to put a bearer token. This project has no budget for a hosted identity
provider during local development.

## Decision

Development HTTP uses one static bearer token from `PV_MCP_TOKEN`.

- Comparison uses `secrets.compare_digest` after a length check.
- A match becomes an `AccessToken` for client id `pv-mcp-dev`, scope `pv:read`,
  and resource equal to `PV_MCP_RESOURCE_URL` (or `http://<host>:<port>/mcp`).
- `AuthSettings.validate_token_resource` is true, so a token issued for another
  resource is rejected.
- The issuer URL defaults to `https://pv-mcp.invalid/dev`. That name is not a
  real authorization server. It only fills the metadata document the SDK exposes.
- Missing or invalid bearer tokens get HTTP 401. The process refuses to start
  HTTP when `PV_MCP_TOKEN` is empty.
- stdio ignores the token.

Production would replace `StaticTokenVerifier` with a verifier that introspects
or locally validates OAuth 2.1 access tokens from Microsoft Entra ID:

- Entra is the authorization server. pv-mcp stays a resource server and does
  not collect passwords.
- The client uses the MCP OAuth flow with a resource indicator (RFC 8707) set
  to the public URL of this server. Entra (or an intermediary that speaks the
  MCP authorization metadata) issues a token whose audience is that URL.
- The verifier checks signature, expiry, issuer, audience, and the `pv:read`
  scope, then returns an `AccessToken` whose `subject` is the Entra user id.
- The dev token's single shared client id goes away. Rate limits and audit
  caller ids then follow the subject, not `pv-mcp-dev`.
- No client secret and no long-lived Azure secret belong in the image. A
  deployed verifier would use the platform's managed identity to read
  configuration.

## Consequences

Everyone who knows `PV_MCP_TOKEN` shares one rate-limit bucket and one audit
caller. That is acceptable for a local demo and unacceptable for a shared
deployment. Do not publish the token or the port beyond localhost until the
Entra verifier exists.
