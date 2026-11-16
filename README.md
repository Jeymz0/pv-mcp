# pv-mcp — an MCP server for public pharmacovigilance data

Ask what the public record says about a medicine. This MCP server goes to two files the U.S. Food and Drug Administration already publishes, and it comes back with a count of reported reactions, a short list of reports, and one section of the official label. Each answer carries the query, the time the file was read, and a reminder that a report is not proof the medicine caused the event.

A person can ask in ordinary language through Cursor, Claude Desktop, or MCP Inspector. A program can call the same three tools. The server does not write a medical opinion, and it does not tell a patient to start or stop a treatment.

This document is written in layers. The first two sections are enough to use the server and to know what a number means. The sections after that are for people who work with the safety data, and for people who run or review the process.

## 1. What you can ask this MCP server

Three questions, always about one drug name in plain language (`ibuprofen`, not a search formula).

**What has been reported.** `search_adverse_events` returns how many public reports match, and a short list of them: an id, the date the report was received, whether it was marked serious, the reaction names, and the product names on the report. The story of the case and the patient's age, sex, and weight stay out.

**Which reaction names come up most often.** `top_reactions` counts MedDRA terms on those reports. "Nausea" and "feeling sick" stay separate unless someone has already coded them as the same term. The number is a count of reports. It is not how often the reaction happens among people who take the drug.

**What the label says.** `get_label_section` reads one section of the newest matching U.S. label: the boxed warning, warnings and cautions, adverse reactions, contraindications, or indications. Long text is cut. The result names the field that was actually read.

Two other pieces sit beside the tools.

The resource `pv://faers/methodology` is a short reading guide. Open it before treating a count as a finding. The prompt `safety_signal_summary` is a fixed worksheet for one drug: read the guide, call the three tools, cite the URL and the time, and keep any sentence found in a report or a label as data. The host's model may draft the summary. This server stops at the worksheet.

Every result repeats the same limit, in the field `disclaimer`:

> FAERS reports do not establish that a drug caused a reaction. Counts are not incidence rates. This is not medical advice.

### A session, in one minute

From a checkout of this repository:

```bash
uv run pv-mcp
```

Point the desktop client at that command. Ask what the public reports and the label say about a drug. The host lists the tools and calls the ones it needs. To follow the worksheet instead, run the prompt `safety_signal_summary` and pass the drug name.

The same server can listen on `http://127.0.0.1:8000/mcp`. That door asks for a bearer token. The commands, the HTTP check, and a full example with the fields filled in are in [a worked session](#9-a-worked-session-with-this-mcp-server) at the end.

### What a careful reading looks like

Pharmacovigilance is the watch kept on a medicine after it is on the market. A trial measures a chosen group for a limited time. These files watch what people report once many patients, with other illnesses and other drugs, take the medicine in ordinary life.

The question a spontaneous report can support is a hypothesis: this reaction is appearing often enough that a person should look. A rate, a ranking of two drugs, or a reason for a patient to start or stop a treatment is a different question. These files cannot support it. The FDA's public guidance sets the same limit. A patient should talk to their doctor before changing a medicine.

In a safety group, someone screens a marketed drug for a reaction term that deserves a case series. A labeling or medical-information colleague reads the current U.S. warning before answering. A regulatory team watches whether a label changed. This server is a way to fetch those public pieces, with the source attached, into a tool a model can call.

## 2. Where the answers come from

Two public datasets, both reached through openFDA, the FDA's API over files it has already released. openFDA converts those files to JSON. It states that the API does not contain direct patient identifiers. Anonymous calls share a small quota. An API key raises that quota. The key is a credential for the gateway. It is not part of the scientific result, and it never appears in a tool result.

**FAERS**, the FDA Adverse Event Reporting System, is the store of adverse-event reports. Manufacturers must send serious and unexpected cases. Health professionals and patients may report voluntarily. Each case is an individual case safety report (ICSR), shaped by the ICH E2B standard. openFDA republishes the publicly releasable part at `https://api.fda.gov/drug/event.json`. Updates are quarterly and can lag the underlying database by a few months. A query with no match comes back as HTTP 404, which this server turns into an empty success.

A report can list several drugs and several reactions. The record does not tie one drug to one reaction. The reporter may mark a drug as suspect, or the drug may only be concomitant, taken at the same time. That mark is the reporter's opinion. The FDA does not require proof of cause, and it does not medically confirm the story before storing the report. Duplicates are common, because the patient, the clinician, and the company can each file the same event. There is no count of how many people took the drug, so a tally of reports is not an incidence. Publicity, a label change, or a longer time on the market changes how often people report.

Reaction names are coded in MedDRA, the Medical Dictionary for Regulatory Activities. A count from `top_reactions` is a count of MedDRA preferred terms.

**The drug label** is submitted as Structured Product Labeling (SPL). It is a living document: boxed warning, warnings, adverse reactions, contraindications, indications. The wording changes as knowledge of the drug changes. It can differ from the carton in a pharmacy. Many over-the-counter labels were never approved line by line. openFDA republishes prescription and over-the-counter labels at `https://api.fda.gov/drug/label.json`, about weekly. It reformats the label and does not verify it. Sections vary from product to product. Older labels often store precautions under `warnings` rather than `warnings_and_cautions`.

The case the FDA holds includes a free-text narrative. That narrative can name a patient, a reporter, a hospital, or a date of birth, so FDA leaves it out of the public dashboard and the quarterly public files. A redacted narrative is released only after a Freedom of Information review. The public extract can still carry age, sex, weight, receive dates, and a narrative field when one remains. Age, a rare reaction, and a date can be enough to recognize a person. This server drops the narrative and the demographic fields before a model sees the report. Label text is not patient data. It can still contain sentences that read like instructions, so the server returns it as text and does not follow it.

These descriptions follow the FDA's public notes on the [drug-event API](https://open.fda.gov/apis/drug/event/), the [drug-label API](https://open.fda.gov/apis/drug/label/), [what the public dashboard withholds](https://www.fda.gov/drugs/cder-conversations/understanding-cders-postmarket-safety-surveillance-programs-and-public-data), and the [FOIA path for an individual narrative](https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems/instructions-requesting-individual-case-reports).

## 3. The functional surface of the MCP server

The whole surface is three tools, one resource, and one prompt. ClinicalTrials.gov is not part of it. The server reads openFDA drug events and drug labels, and nothing else.

Each tool is marked read-only, non-destructive, safe to repeat, and dependent on a system outside the server. An argument that fails the schema is rejected before openFDA is contacted. A failure comes back as a tool error the model can read, and the session stays open. Each success includes a `source` object:

| Field | Meaning |
| --- | --- |
| `endpoint` | `/drug/event.json` or `/drug/label.json` |
| `query` | The search string that was sent |
| `url` | The full request URL, with any API key removed |
| `retrieved_at` | UTC time openFDA was read. Unchanged when the row is served from cache |
| `cached` | `true` when this answer came from the local cache |
| `disclaimer` | The same three sentences on every result |

The drug name is quoted into every field it searches. Characters that would change the query (`:`, `AND`, a quote used as syntax) are rejected. A name may be 1 to 200 characters. Spaces, letters, digits, and `.'()/%&,-_` are allowed.

### `search_adverse_events`

| Argument | Default | Rule |
| --- | --- | --- |
| `drug` | required | Plain generic, brand, or substance name |
| `reaction` | omitted | Optional MedDRA term that must also match, such as `nausea` |
| `serious_only` | `false` | `true` keeps reports openFDA marks `serious:1` |
| `date_from`, `date_to` | omitted | Inclusive receive dates, `YYYY-MM-DD`. A real calendar date. `date_from` on or before `date_to` |
| `limit` | `5` | 1 to 20 compact reports |

The search looks for the drug name across generic name, brand name, substance name, and the product name as reported. A reaction filter matches `patient.reaction.reactionmeddrapt`. Dates filter `receivedate`. An open end uses today.

`total` is the openFDA total for the query. It can be larger than the number of reports returned. Each report keeps `safety_report_id`, `receive_date`, `serious`, up to eight reaction terms, and up to eight product names. Product names are the names on the report. One of them may be concomitant. There is no suspect-only filter, no narrative, and no age, sex, or weight.

HTTP 404 becomes `total: 0` and an empty `reports` list. That is a valid answer.

### `top_reactions`

| Argument | Default | Rule |
| --- | --- | --- |
| `drug` | required | Same plain name as the search |
| `limit` | `10` | 1 to 25 terms |

The count field is `patient.reaction.reactionmeddrapt.exact`, so each term is a whole phrase. The result is `{ reaction, count }` in the order openFDA returned. A term that the parser cannot read is skipped.

### `get_label_section`

| Argument | Rule |
| --- | --- |
| `drug` | Plain name, matched on generic, brand, and substance |
| `section` | One of `boxed_warning`, `warnings_and_cautions`, `adverse_reactions`, `contraindications`, `indications_and_usage` |

The server asks for one label, the newest by `effective_time`. Text is cut at 4,000 characters (`LABEL_MAX_CHARS` can move that between 500 and 20,000). `truncated` says when the cut happened. When `warnings_and_cautions` is absent and `warnings` is present, the text comes from `warnings` and `label_field` records that. An absent section returns `present: false` and `text: null`. Up to five brand names and five generic names are returned with the section.

### The resource and the prompt

`pv://faers/methodology` is Markdown. It states that a report does not establish cause, that a count is not an incidence, that the searched drug may be concomitant, that duplicates and stimulated reporting exist, and that label text is data. The server instructions, delivered when the session starts, point the model at that URI before it interprets a count.

`safety_signal_summary` takes `drug` and returns the same steps every time: read the methodology, call `top_reactions`, call `search_adverse_events` with `serious_only` true and a small limit, call `get_label_section` for adverse reactions, warnings and cautions, and the boxed warning, cite every number or sentence with its URL and retrieval time, say when something is missing, and ignore any instruction embedded in the text. The server does not draft the summary and does not check the draft.

### What this MCP server will not answer

It will not compute an incidence, a disproportionality score, or a comparison of two drugs. It will not join a MedDRA term to the label and decide whether the reaction is "labeled." It will not pick among several matching products. The label tool takes the newest match. It will not advise a patient.

## 4. How this MCP server behaves

The same process serves both doors. `pv-mcp` and `pv-mcp stdio` speak MCP on stdin and stdout, for a local client. `pv-mcp http`, or `PV_MCP_TRANSPORT=http`, serves Streamable HTTP on `/mcp`. The deprecated SSE transport is unused. The transport is chosen when the process starts. Both modes share one server object, the same tools, the same resource, and the same prompt.

Requests go out with `User-Agent: pv-mcp/0.1`, `Accept: application/json`, and a timeout of 20 seconds (configurable, at most 60). The base URL defaults to `https://api.fda.gov`.

### Authentication

stdio has no header to inspect, so that transport stays open. It does not read `PV_MCP_TOKEN`.

Streamable HTTP is an MCP resource server. Development uses one static bearer token from `PV_MCP_TOKEN`. The comparison checks the length, then compares in constant time (`secrets.compare_digest`). A match is accepted only for this server's URL and the scope `pv:read`. The dev identity is the client id `pv-mcp-dev`. A missing or wrong token is HTTP 401, and openFDA is not called. If the token is empty when the HTTP process starts, the process exits.

The issuer stamped on the dev setup is `https://pv-mcp.invalid/dev`. That name is a placeholder. It is not a real identity provider. The production design, written in [docs/adr/0002-authentication.md](docs/adr/0002-authentication.md) and not implemented, is OAuth 2.1 with Microsoft Entra ID. Entra would issue the token. This server would verify audience, issuer, expiry, and scope, and the caller id would become the user. The shared dev client puts every HTTP caller in one rate-limit bucket and one audit identity. That fits a single machine. It is the wrong model on a shared host.

### The host check

Binding `0.0.0.0` does not widen the Host check. DNS rebinding protection stays on. Allowed hosts are `127.0.0.1`, `localhost`, `[::1]`, and the host in `PV_MCP_RESOURCE_URL`. A request that names another host, such as `evil.com`, is rejected with HTTP 421. See [docs/adr/0001-transports.md](docs/adr/0001-transports.md).

### Retry

openFDA times out and returns 429 and 5xx under ordinary load. The client tries three times. A timeout, or HTTP 429, 500, 502, 503, or 504, waits and tries again. The waits are 0.25 seconds, then 0.5 seconds. Any other HTTP failure is reported at once. After the last attempt, the caller receives a tool error: the timeout, the HTTP status, a body that is not JSON, or a body over 1,500,000 bytes. That failure is not stored in the cache.

### Cache

An identical public query is answered from SQLite for one hour (`OPENFDA_CACHE_TTL_SECONDS`, default 3600, at most one day). The key is a SHA-256 of the path and the public parameters, sorted. The API key is not part of the key, the stored body, or the URL. HTTP 200 and HTTP 404 are stored. Timeouts, HTTP 429, and server errors are left uncached, so a bad minute does not become the answer for the next hour. A hit sets `cached` to true and keeps the original `retrieved_at`.

The library default is no cache file, so tests stay isolated. The HTTP entrypoint uses `.cache/openfda.sqlite` when the path is unset. Docker uses `/data/openfda.sqlite` on a volume. See [docs/adr/0004-caching-and-rate-limits.md](docs/adr/0004-caching-and-rate-limits.md).

### Rate limit

A one-minute sliding window allows 60 tool calls per caller (`PV_MCP_RATE_LIMIT_PER_MINUTE`). `0` turns the check off. Listing tools, reading the resource, and rendering the prompt do not spend the budget. Crossing the limit returns a tool error, `Rate limit exceeded. Try again shortly.`, and openFDA is not called. The refusal is itself audited. On stdio the caller is `local`. On the dev token the caller is `pv-mcp-dev`, so every HTTP client shares one bucket.

### The call log

Each `tools/call` appends one JSON line to stderr. stdio already owns stdout for the protocol. The line records `event` (`tool_call`), `caller`, `tool`, `params`, `latency_ms`, `status` (`ok` or `error`), and `result_size`. Field names `token`, `api_key`, `authorization`, `password`, `secret`, `pv_mcp_token`, and `openfda_api_key` are replaced. Strings longer than 200 characters are cut. Narratives never enter the tools, so they never enter the log.

There is no metrics endpoint and no dashboard. The surveillance of a running process is this log, the `cached` flag and `retrieved_at` on each result, and the rate-limit error when a caller goes too fast.

### The container

Docker Compose runs the HTTP server as a non-root user. The token and the API key come from the environment or a gitignored `.env`. The cache file sits on the volume `pv-mcp-cache`. Image scanning, the SBOM, and a cloud deployment are later work. They are not in this image's workflow yet.

### Settings

| Variable | Default | Role |
| --- | --- | --- |
| `OPENFDA_API_KEY` | empty | Optional quota key. Never written to results or the log |
| `OPENFDA_BASE_URL` | `https://api.fda.gov` | Upstream origin |
| `OPENFDA_TIMEOUT_SECONDS` | `20` | Per attempt, from just above 0 to 60 |
| `LABEL_MAX_CHARS` | `4000` | Label section cut, 500 to 20,000 |
| `OPENFDA_CACHE_PATH` | unset, or `.cache/openfda.sqlite` on HTTP | SQLite file |
| `OPENFDA_CACHE_TTL_SECONDS` | `3600` | 1 to 86,400 |
| `PV_MCP_TOKEN` | empty | Required for HTTP. stdio ignores it |
| `PV_MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `PV_MCP_HTTP_HOST` | `127.0.0.1` | Bind address. `0.0.0.0` in Compose |
| `PV_MCP_HTTP_PORT` | `8000` | HTTP port |
| `PV_MCP_RESOURCE_URL` | derived from host and port | Audience of the dev token, and an allowed Host |
| `PV_MCP_ISSUER_URL` | `https://pv-mcp.invalid/dev` | Placeholder issuer |
| `PV_MCP_RATE_LIMIT_PER_MINUTE` | `60` | `0` disables |

A blank string for the key, the token, the cache path, or the resource URL is treated as unset. `.env.example` lists the same names. `.env` is gitignored.

## 5. What is checked, and when

The suite never calls the internet. Tool contracts run through an in-memory MCP client against recorded HTTP responses. A live call was made by hand, once, to watch the cache hit the real API. The suite does not repeat it. Continuous integration does not call openFDA.

| When | Command | What it holds |
| --- | --- | --- |
| While developing | `make test` | The pytest suite, offline |
| Before a change feels finished | `make lint` | ruff (lint and format) and mypy in strict mode on `pv_mcp` |
| On every push and every pull request | `.github/workflows/ci.yml`, or `make ci` locally | Lockfile sync with uv 0.13.5 and Python 3.12, then ruff, mypy, pytest, and pip-audit |
| Coverage gate | the pytest step in CI | Coverage of the `pv_mcp` package. The job fails below 90% |
| Dependency watch | the last CI step | Runtime dependencies exported from the lockfile, with their hashes. pip-audit does not ask pip to resolve them again |
| By hand, outside the suite | one live openFDA session | Not part of CI. Not a regression test |

The workflow cancels a superseded run on the same ref. It has `contents: read` only.

The tests are grouped by the promise they lock:

| File | Promise |
| --- | --- |
| `tests/test_tools.py` | The three tools, the resource, and the prompt return the compact shape. A limit of 21 is rejected. An impossible date is rejected. Query syntax in a drug name is rejected. HTTP 404 is an empty success. A planted instruction in label text comes back as text. A missing warnings section falls back and names the field. The API key stays out of the result |
| `tests/test_queries.py` | The drug name is quoted in every field. Filters join with AND. An open-ended date uses today. Inverted dates are rejected |
| `tests/test_client.py` | A 503 is retried, then the count is returned. A timeout becomes a tool error. The URL in the result has no API key |
| `tests/test_cache.py` | Parameter order does not change the key. A second call keeps the original retrieval time. A different API key still hits the same row. Expired rows are dropped. Server errors are not stored |
| `tests/test_guardrails.py` | Secret field names and long strings are redacted. The sliding window is per caller. One tool call writes one audit line, and listing tools does not. A call past the limit does not hit openFDA again |
| `tests/test_http.py` | The HTTP process refuses to start without a token. A mismatched token is rejected. A missing or wrong bearer is HTTP 401 and does not call openFDA. Binding every interface still rejects `Host: evil.com` with HTTP 421. A valid token calls openFDA once, then the cache |
| `tests/test_settings.py` | A blank API key, token, or cache path is ignored |

ruff, mypy, and the pinned lockfile keep that contract from drifting between machines. pip-audit watches the runtime set for published vulnerabilities. It does not scan the container image. That scan is planned with the image workflow, not with this suite.

While a process is running, the things to watch are the stderr line for each tool call, a rising share of `status: error`, a `cached: true` result whose `retrieved_at` is older than you expected, and `Rate limit exceeded` if a client is looping. Nothing in the current server pages a person when those happen. The log is the record.

## 6. What this MCP server takes from the protocol

MCP is the contract between a host and this process. The host may be an editor, a desktop application, or another program. It discovers what the server offers, then calls it. pv-mcp uses the parts of that contract that fit a read-only public data source.

A tool is a function the host's model may call. It has a name, a description written for the model, and a schema for the arguments. `search_adverse_events`, `top_reactions`, and `get_label_section` are those functions. Each tool returns a typed object, so the client receives fields — the total, the reaction terms, the source URL, the retrieval time — rather than only a paragraph.

A resource is a document the client reads by URI. The host can show `pv://faers/methodology` on its own. It does not have to spend a tool call to fetch the method.

A prompt is a template a person runs. The server stops at that template. The host's model writes the summary, and a person can check the citations.

On HTTP the process is an MCP resource server: a bearer token scoped to `pv:read`, bound to this server's URL. A client that speaks the protocol needs no private library for this project. The server does not ask the host model to generate a completion on its behalf, does not solicit secrets from the user, and exposes no tool that writes.

Another program can connect over stdio or over HTTP without embedding this process. The agent that will do that is milestone M4. It is not built yet. The adapter planned for that agent loads tools only, so the methodology and the prompt have to be repeated in the agent's own instructions if the agent is to follow them.

## 7. Why the surface is this shape

The choices below are the ones already implemented. The behavior is the one in the sections above. The notes in `docs/adr/` record the transport, the authentication, and the cache.

The server reads two endpoints because those are the public files a safety question starts from. Adding a third source before this path is solid would blur what a citation points at.

A report is reduced before a model sees it. Returning a narrative or an age, sex, and weight would reopen the privacy problem FDA already narrowed, and it would hand a model text that sometimes reads like an instruction. Twenty reports and twenty-five reaction terms are hard caps so a single call stays small enough to read.

Label text is returned as data, one section at a time, from a fixed list. The result names the field that was actually read, including the older `warnings` fallback.

A cached number keeps its age. The original `retrieved_at` stays, so a reader can see that the figure is up to an hour old. Failures stay out of the cache.

stdio stays open because desktop clients have no header to send. HTTP checks the token and the Host header. One server object serves both, so the tools cannot drift apart.

The dev token is a single shared secret so a local HTTP client can be tested. It is not an identity. The Entra design is written down so the production shape is chosen, and left unimplemented so this server does not pretend to verify a real issuer.

Every tool call is counted, then limited. The log exists so a later reader can see who called what, with the secrets removed. The limit exists so a looping client does not spend the openFDA quota.

The upstream call is allowed to fail in the open. Three attempts, then a tool error, then no cache. A dead minute stays a dead minute.

The image holds no secrets. The token and the API key are environment variables. The SQLite file lives on a volume.

## 8. Milestones, and MCP ideas beyond them

M1, M2, and M3 are in the repository. M1 and M2 are the server this document describes: the three tools, the methodology resource, the summary prompt, stdio, Streamable HTTP, the dev token, the audit line, the cache, and Compose. M3 is the continuous integration workflow in [section 5](#5-what-is-checked-and-when). From M4 onward the milestones are still planned. None of them adds resource templates, argument completion, elicitation, sampling, or a new pharmacovigilance judgment on the server.

### M4 — an agent that uses the tools

A LangGraph agent drafts a safety-signal summary for one drug. Its tools come from `langchain.mcp.MCPAdapter` (`langchain[mcp]`), over stdio or over `http://…/mcp` with the bearer token. The adapter loads tools only. It does not see `safety_signal_summary` or `pv://faers/methodology`, so the same limits and the same disclaimer live in the agent's own system prompt. The agent plans, calls the three existing tools, and drafts Markdown that cites their URLs and retrieval times. A person then approves or edits that draft. The approved text is saved. The chat model is Groq, and the model name is configurable. The server still returns sourced records. It does not write the summary, and it does not check the draft.

### M5 — evaluation of that agent

Ten to fifteen golden cases, run on demand because the Groq quota is limited. They check tool choice, numbers that appear in the tool outputs, refusal to follow instructions planted in a label or a report, and the presence of the disclaimer. LLM responses are cached. The run writes a Markdown report. A workflow dispatch holds the API key. This does not change the protocol surface.

### M6 — image, scan, and a deploy workflow

The workflow builds the image, scans it with Trivy, writes an SBOM, and pushes to GHCR. A separate, manually triggered workflow deploys with Bicep to Azure Container Apps at zero minimum replicas, using GitHub OIDC rather than a long-lived Azure secret, with a budget alert and a teardown command. The production Entra ID verifier described in the authentication decision is not part of this milestone.

### M7 — the written account of the system

This README is the layered account of the server, including the example session below. M7 still adds an architecture diagram, `SECURITY.md` for the threat model (prompt injection, data exfiltration, denial of service, supply chain), and three architecture notes: untrusted tool output, the MCPAdapter client, and the deployment cost. M7 documents the server. It does not extend it.

ClinicalTrials.gov is not in M4–M7. It stays out while the FAERS path is the one the agent and the evals rely on.

### Later, not on this list

The protocol can carry pharmacovigilance work that openFDA does not do. None of the following is assigned to a milestone.

Resource templates would publish a drug as a dossier, for example `pv://drug/ibuprofen/reactions`, instead of three separate calls. A subscription on the label resource would tell a client when a weekly SPL update changed a boxed warning. openFDA only answers the request in front of it.

Completion would suggest drug names and MedDRA terms as the person types. The public API expects an exact string and returns HTTP 404 when the string matches nothing.

Elicitation would stop when a name matches several products or several labels, and ask the person which one to keep. The label tool today takes the newest matching label and does not ask.

One new tool, also exposed as a resource, would join the top MedDRA terms to the adverse-reaction and warnings text and return a structured row: term, report count, whether that term was found in the sections just read, and the source of each half. The model would receive the comparison already made. Milestone M4 leaves that comparison to the agent. Putting it in the server is a later decision, and it has to be a tool if the agent is to see it, because the adapter does not load resources.

Sampling would let the server gather the evidence, ask the host's model for a draft, and refuse any number that is not in that evidence. Milestone M4 does the opposite on purpose: the agent drafts, the person reviews, and the server stays a source of records. Sampling would couple the data server to the host's model. It is not planned.

Whatever is added later stays inside the same limit. The server does not compute an incidence, and it does not advise a patient to start or stop a medicine.

## 9. A worked session with this MCP server

Counts, report ids, and label sentences below are shortened so the shape of a call is visible. A live call returns the current openFDA values, with the same fields.

### Local client over stdio

```bash
uv run pv-mcp
```

A desktop client starts that command and speaks MCP on stdin and stdout. No bearer token is read. In Cursor, with this repository as the working directory:

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

MCP Inspector can do the same with `npx @modelcontextprotocol/inspector uv run pv-mcp`.

### MCP over HTTP

Put a long random value in `PV_MCP_TOKEN`, then:

```bash
uv run pv-mcp http
```

The endpoint is `http://127.0.0.1:8000/mcp`. The client sends `Authorization: Bearer <PV_MCP_TOKEN>`. Docker Compose publishes the same URL from the host. A call with no token, or the wrong token, receives HTTP 401 and never reaches a tool.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{}'
```

That prints `401`.

### One drug, field by field

The prompt `safety_signal_summary`, with `drug` set to `ibuprofen`, asks the client to do four things. The same calls can be made by hand.

Read the resource `pv://faers/methodology` first.

Count reaction terms:

```json
{
  "name": "top_reactions",
  "arguments": { "drug": "ibuprofen", "limit": 10 }
}
```

```json
{
  "drug": "ibuprofen",
  "reactions": [
    { "reaction": "NAUSEA", "count": 1000 },
    { "reaction": "FATIGUE", "count": 800 }
  ],
  "source": {
    "endpoint": "/drug/event.json",
    "query": "(patient.drug.openfda.generic_name:\"ibuprofen\" …)",
    "url": "https://api.fda.gov/drug/event.json?search=…&count=patient.reaction.reactionmeddrapt.exact&limit=10",
    "retrieved_at": "2026-10-25T13:40:35+00:00",
    "cached": false
  },
  "disclaimer": "FAERS reports do not establish that a drug caused a reaction. Counts are not incidence rates. This is not medical advice."
}
```

The `url` has no `api_key`. `NAUSEA` is a MedDRA preferred term, a count of reports.

Then a short list of serious reports that also mention nausea, inside a receive-date window:

```json
{
  "name": "search_adverse_events",
  "arguments": {
    "drug": "ibuprofen",
    "reaction": "nausea",
    "serious_only": true,
    "date_from": "2024-01-01",
    "date_to": "2024-12-31",
    "limit": 5
  }
}
```

```json
{
  "drug": "ibuprofen",
  "total": 42,
  "reports": [
    {
      "safety_report_id": "1001",
      "receive_date": "2024-03-15",
      "serious": true,
      "reactions": ["Nausea", "Headache"],
      "drugs": ["IBUPROFEN", "ASPIRIN"]
    }
  ],
  "source": {
    "endpoint": "/drug/event.json",
    "query": "(…) AND patient.reaction.reactionmeddrapt:\"nausea\" AND serious:1 AND receivedate:[20240101 TO 20241231]",
    "url": "https://api.fda.gov/drug/event.json?search=…&limit=5",
    "retrieved_at": "2026-10-25T13:40:40+00:00",
    "cached": false
  },
  "disclaimer": "FAERS reports do not establish that a drug caused a reaction. Counts are not incidence rates. This is not medical advice."
}
```

`total` can be larger than the number of reports returned. `drugs` lists product names on the report.

Then one label section:

```json
{
  "name": "get_label_section",
  "arguments": {
    "drug": "ibuprofen",
    "section": "warnings_and_cautions"
  }
}
```

```json
{
  "drug": "ibuprofen",
  "section": "warnings_and_cautions",
  "label_field": "warnings",
  "present": true,
  "text": "…",
  "truncated": true,
  "brand_names": ["Advil"],
  "generic_names": ["ibuprofen"],
  "source": {
    "endpoint": "/drug/label.json",
    "query": "(openfda.generic_name:\"ibuprofen\" …)",
    "url": "https://api.fda.gov/drug/label.json?search=…&limit=1&sort=effective_time:desc",
    "retrieved_at": "2026-10-25T13:40:42+00:00",
    "cached": false
  },
  "disclaimer": "FAERS reports do not establish that a drug caused a reaction. Counts are not incidence rates. This is not medical advice."
}
```

`label_field` is `warnings` when the newer section name is absent on that label. A sentence inside `text` that tells the reader to ignore previous instructions is still just text.

Calling `top_reactions` again with the same arguments, inside the hour, does not call openFDA. The result is the same object with `source.cached` true and the same `retrieved_at`. stderr gains a second audit line:

```json
{"event":"tool_call","caller":"local","tool":"top_reactions","params":{"drug":"ibuprofen","limit":10},"latency_ms":1,"status":"ok","result_size":900}
```

Over HTTP the `caller` is `pv-mcp-dev`. The line does not contain the bearer token or the openFDA key. A name such as `ibuprofen AND serious:1` is rejected before any request. A limit of 21 is rejected by the tool schema.
