# pv-mcp

Read-only [Model Context Protocol](https://modelcontextprotocol.io) server for public
pharmacovigilance data. This milestone serves three openFDA tools over stdio:

- `search_adverse_events` — compact FAERS reports and the matching total
- `top_reactions` — MedDRA reaction counts
- `get_label_section` — one section of a drug label

It also exposes the resource `pv://faers/methodology` and the prompt
`safety_signal_summary`. A report does not establish causality, and the server
does not give medical advice.

HTTP transport, authentication, caching, and the review agent come in later milestones.
The project brief is `PROJECT_BRIEF.md`.

## Run the tests

```bash
uv sync
uv run pytest
```

The tests use recorded HTTP responses. They do not call openFDA.

## Serve it over stdio

```bash
uv run pv-mcp
```

Optional: copy `.env.example` to `.env` and set `OPENFDA_API_KEY`. The key is sent to
openFDA and removed from every tool result.

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

Try one search, one reaction count, and one label section. Then open the methodology
resource and render `safety_signal_summary` for a drug name.
