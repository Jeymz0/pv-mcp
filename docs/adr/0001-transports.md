# 0001. Transports

## Status

Accepted for milestone M2.

## Context

Local clients (Cursor, Claude Desktop, MCP Inspector) speak stdio. A container
or a remote host needs Streamable HTTP on `/mcp`. The SDK takes the transport
as an argument of `run()`, so both modes share one `MCPServer`.

## Decision

- `pv-mcp` and `pv-mcp stdio` serve stdio. `PV_MCP_TRANSPORT=http` or
  `pv-mcp http` serves Streamable HTTP.
- The deprecated SSE transport is not used.
- stdio stays unauthenticated. HTTP requires the dev bearer token described in
  [0002](0002-authentication.md).
- DNS rebinding protection stays on even when the process binds `0.0.0.0`.
  Allowed `Host` values are localhost and the configured resource host.
  `Host: evil.com` is rejected.

## Consequences

Docker Compose publishes port 8000 and sets the resource URL to
`http://127.0.0.1:8000/mcp`. A client that sends another host name is refused
until that name is configured as `PV_MCP_RESOURCE_URL`.
