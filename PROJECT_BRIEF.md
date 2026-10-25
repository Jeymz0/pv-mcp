# pv-mcp

## Project

**pv-mcp** is a Model Context Protocol (MCP) server.

This repository is the empty starting point for that server. It contains this brief and no implementation.

## Purpose

Ship a server that an MCP client — Cursor, Claude, or any other compatible host — can connect to under the name `pv-mcp`. The tools, resources, and prompts it will expose are not defined yet.

## Current state

- Repository initialized for `pv-mcp`.
- No server process, package, or client configuration.
- No tools, resources, or prompts.

## Out of scope until the server's job is defined

- Runtime code and dependencies
- Transport choice (local stdio or remote Streamable HTTP)
- Authentication
- Deployment

## Open decisions

1. What `pv` stands for, and which capabilities the server must expose.
2. Transport: a local process over stdio, or a remote endpoint over Streamable HTTP.
3. Language and package layout.
4. Whether callers need authentication.

## Next step

Write down the server's job, then add the smallest implementation that speaks MCP.
