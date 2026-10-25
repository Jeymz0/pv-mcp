# pv-mcp

Read-only [Model Context Protocol](https://modelcontextprotocol.io) server for public
pharmacovigilance data. It serves three openFDA tools over stdio or Streamable HTTP:

- `search_adverse_events` — compact FAERS reports and the matching total
- `top_reactions` — MedDRA reaction counts
- `get_label_section` — one section of a drug label

It also exposes the resource `pv://faers/methodology` and the prompt
`safety_signal_summary`. A report does not establish causality, and the server
does not give medical advice.

The same process serves both transports. stdio is for local clients. Streamable
HTTP is for Docker and remote clients, and it requires a bearer token.
Decisions that are easy to miss are in `docs/adr/`.

## Run the tests

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

The tests use recorded HTTP responses. They do not call openFDA.

## Serve it over stdio

```bash
uv run pv-mcp
```

Optional: copy `.env.example` to `.env` and set `OPENFDA_API_KEY`. The key is sent
to openFDA and removed from every tool result. stdio does not check `PV_MCP_TOKEN`.

Cursor, with this repository as the working directory:

```json
{
  "mcpServers": {
    "pv-mcp": {
      "command": "uv",
      "args": ["run", "pv-mcp"]
    }
  }
}
```

MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uv run pv-mcp
```

## Serve Streamable HTTP

Put a long random value in `PV_MCP_TOKEN` in `.env`. The HTTP process exits
immediately when that variable is empty.

```bash
uv run pv-mcp http
```

The endpoint is `http://127.0.0.1:8000/mcp`. Send `Authorization: Bearer <PV_MCP_TOKEN>`.
A second identical tool call is served from `.cache/openfda.sqlite` for one hour.
`source.cached` is true and `source.retrieved_at` stays at the original fetch.
Audit lines are JSON on stderr. They include the caller `pv-mcp-dev` and never
the bearer token or the openFDA key.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{}'
```

That call has no token, so the status is `401`.

MCP Inspector can connect to `http://127.0.0.1:8000/mcp` with the same
`Authorization` header.

## Docker Compose

```bash
cp .env.example .env
# set PV_MCP_TOKEN, and OPENFDA_API_KEY if you have one
docker compose up --build
```

The container listens on `0.0.0.0:8000` as user `pv` (uid 10001) and stores the
cache in the `pv-mcp-cache` volume. Clients on the host use
`http://127.0.0.1:8000/mcp`. A request whose `Host` header is not localhost or
the configured resource host is rejected.

## What to check by hand

1. `POST /mcp` without a bearer token returns 401.
2. The same call with `Authorization: Bearer $PV_MCP_TOKEN` is accepted, and
   `top_reactions` for a real drug name returns counts.
3. Calling that tool again with the same arguments returns `source.cached: true`
   and the same `source.retrieved_at`. stderr shows two JSON audit lines and
   does not contain the token.
