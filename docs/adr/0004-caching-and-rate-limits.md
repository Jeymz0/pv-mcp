# 0004. Caching and rate limits

## Status

Accepted for milestone M2.

## Context

openFDA's anonymous quota is small, and a model will repeat the same question.
The server also needs a bound on its own work. Responses are public counts and
labels, not patient records, but the API key is a secret.

## Decision

Cache successful openFDA reads in SQLite.

- The key is a SHA-256 of the path and the sorted public query parameters.
  `api_key` is never part of the key, the stored body, or the source URL.
- Only HTTP 200 and HTTP 404 are stored. Timeouts, HTTP 429, and HTTP 5xx are
  retried and then left uncached so a later call can succeed.
- Each row keeps the original `retrieved_at`. A hit sets `source.cached` and
  does not pretend the data was fetched again.
- Default TTL is one hour (`OPENFDA_CACHE_TTL_SECONDS`).
- The cache is off unless a path is set. Tests leave it unset. `pv-mcp http`
  defaults the path to `.cache/openfda.sqlite`. Compose uses `/data/openfda.sqlite`
  on a named volume.

Tool calls are limited per caller with a one-minute sliding window
(`PV_MCP_RATE_LIMIT_PER_MINUTE`, default 60). Zero disables the limit.

- stdio's caller id is `local`.
- HTTP's caller id is the token client id. With the dev token that is one
  shared bucket named `pv-mcp-dev`.
- A refusal is a tool error, `Rate limit exceeded. Try again shortly.`, and it
  is still written to the audit log. It does not call openFDA.
- `tools/list` and other methods do not spend the budget.

Every `tools/call` appends one JSON object to stderr (stdio already owns
stdout). Fields are `event`, `caller`, `tool`, `params`, `latency_ms`,
`status`, and `result_size`. Parameter names `token`, `api_key`,
`authorization`, `password`, `secret`, `pv_mcp_token`, and `openfda_api_key`
are replaced with `[redacted]`. Strings longer than 200 characters are cut.
The bearer token and the openFDA key are not logged.

## Consequences

A cached row can outlive a label change for up to the TTL. The retrieval time
on the result tells the reader how old it is. Two API keys share one cache
entry for the same public query, which is what we want: the key only changes
the quota, not the data.
