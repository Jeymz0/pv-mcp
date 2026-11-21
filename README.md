# pv-mcp — an MCP server for public pharmacovigilance data

Ask what the public record says about a medicine. This MCP server goes to two files the U.S. Food and Drug Administration already publishes, and it comes back with a count of reported reactions, a short list of reports, and one section of the official label. Each answer carries the query, the time the file was read, and a reminder that a report is not proof the medicine caused the event.

A person can ask in ordinary language through Cursor, Claude Desktop, or MCP Inspector. A program can call the same three tools. The server does not write a medical opinion, and it does not tell a patient to start or stop a treatment.

This document is written in layers. The first two sections are enough to use the server and to know what a number means. The sections after that are for people who work with the safety data, and for people who run or review the process. A chat model can call the same tools and draft a summary. That agent is described with the server, at each layer, and the commands are in [section 10](#10-the-summary-agent). An on-demand grade of that draft is in [section 11](#11-grading-the-draft). Publishing the image, and starting a copy that scales to zero, are in [section 12](#12-publishing-and-deploying-this-mcp-server).

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

A push to the main branch builds that HTTP server as an image, scans it, and publishes it. Starting the image in Azure is a separate step, done by hand. While nobody is calling, that copy scales down to zero replicas. The commands are in [section 12](#12-publishing-and-deploying-this-mcp-server).

### Or let an agent draft, then read it

`pv-agent` asks a chat model to call the three tools and write one Markdown note for one drug. It stops before anything is saved. You read the draft, keep it, or replace it with a file of your own. The note you accept is written under `reports/`. A Groq key is required for a live draft. The commands are in [section 10](#10-the-summary-agent). The tests never call Groq.

Twelve recorded cases can grade a draft. They look at which tools were called, whether each number in the note appears in those tool results, whether a sentence planted in a report or a label was obeyed, and whether the disclaimer is there. That grade calls the chat model, so it runs when you ask. The command is in [section 11](#11-grading-the-draft).

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

### What the agent writes

The agent is a client, not a fourth tool. It starts from that same worksheet. The model is asked to call `top_reactions`, then `search_adverse_events` for serious reports, then `get_label_section` for adverse reactions, warnings and cautions, and the boxed warning. The draft is Markdown. Each number or quoted sentence is supposed to carry the URL and the retrieval time from the tool that returned it. Tool text stays data. An instruction planted in a label or a report is not an instruction to the model.

Nothing is saved at the draft step. A person approves the text, or substitutes another Markdown file. The file that is kept is `{drug}-{UTC time}.md` under `reports/`. It carries the disclaimer. If the person's edit no longer contains that sentence, the save step appends it.

The agent does not compute an incidence and does not decide that a reaction is labeled. Twelve recorded cases check a live draft for the tools it called, for numbers that appear in the tool results, for a planted instruction it should have ignored, and for the disclaimer. The payloads are fixed, so the expected numbers do not move. A person still reads the draft before it is saved. What each check holds, and when the run happens, is in [section 5](#5-what-is-checked-and-when).

### What this MCP server will not answer

It will not compute an incidence, a disproportionality score, or a comparison of two drugs. It will not join a MedDRA term to the label and decide whether the reaction is "labeled." It will not pick among several matching products. The label tool takes the newest match. It will not advise a patient.

A copy published to Azure answers those same three questions. It does not keep a database of patients. The cache file lives on the replica and disappears when the replica scales to zero.

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

Docker Compose runs the HTTP server as a non-root user, uid 10001. The token and the API key come from the environment or a gitignored `.env`. The cache file sits on the volume `pv-mcp-cache`. The image does not install the agent extra. The agent runs beside the container and connects to `http://127.0.0.1:8000/mcp`.

### The published image

`.github/workflows/build.yml` runs on a push to `main`, and when someone starts it by hand. It builds `linux/amd64`, writes a CycloneDX SBOM, and scans the image with Trivy. A fixed HIGH or CRITICAL finding fails the job. The image is pushed only after that scan, to `ghcr.io/<owner>/<repository>`, tagged with the commit SHA. On `main` it is also tagged `main`. The SBOM and the scan table are the artifact `image-reports`. The workflow then asks GitHub to mark the package public, so Azure can pull it without a registry password. If that request is refused, the package page is where the visibility is set.

The image carries no token and no API key. The build applies the Debian security updates that the base tag has not picked up yet, then the scan runs. `org.opencontainers.image.source` points at this repository. The decision is [docs/adr/0006-deployment-target-and-cost.md](docs/adr/0006-deployment-target-and-cost.md).

### A copy that scales to zero

`.github/workflows/deploy.yml` runs only when someone starts it. The choice is `deploy` or `teardown`. GitHub signs in to Azure with OIDC. The federated credential subject is `repo:<owner>/<name>:ref:refs/heads/main`, and the audience is `api://AzureADTokenExchange`. `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID` are repository variables. There is no Azure client secret. The app registration needs Contributor, so the workflow can create and delete the resource group, and Cost Management Contributor, so it can write the budget.

`infra/main.bicep` creates one Container Apps environment and one app in West Europe. The app has a minimum of 0 replicas and a maximum of 1. The public URL is `https://<fqdn>/mcp`, and `PV_MCP_RESOURCE_URL` is set to that URL so the Host check and the dev token audience match it. `PV_MCP_TOKEN` comes from the repository secret of the same name. An empty `OPENFDA_API_KEY` leaves the anonymous quota. The idle timeout is 30 minutes. The cache stays on the replica's disk. There is no Log Analytics workspace and no managed disk. A monthly budget on the resource group mails `BUDGET_CONTACT` at half the amount and at the full amount. The default amount is 5, in the subscription's billing currency. The mail does not stop the app.

`infra/teardown.sh` deletes the resource group. `make teardown` runs it for `rg-pv-mcp`. The Entra ID verifier from the authentication decision is not part of this deployment.

### The summary agent

`uv sync --extra agent` installs `pv-agent`. The graph is LangGraph. The tools come from `langchain.mcp.MCPAdapter`. The adapter loads tools only, so the methodology text and the disclaimer are copied into the agent's system prompt. The decision is [docs/adr/0005-agent-client.md](docs/adr/0005-agent-client.md).

On stdio the client launches `src/pv_mcp/agent/stdio_server.py` with the parent environment, so `OPENFDA_API_KEY` reaches the child server. On HTTP, `PV_AGENT_MCP_URL` must be an `http` or `https` URL ending in `/mcp`, and `PV_MCP_TOKEN` is sent as a bearer token. A missing token or a URL that does not end in `/mcp` stops the process before it connects. The FastMCP client pins the initialize handshake (`mode="legacy"`), which is the protocol era this server speaks. The agent does not construct an `MCPServer`.

The chat model is built with `init_chat_model`. `PV_AGENT_MODEL` and `PV_AGENT_MODEL_PROVIDER` choose it. The default is Groq and `llama-3.3-70b-versatile`. When the provider is Groq, an empty `GROQ_API_KEY` stops the process before a draft.

The graph may call tools in a loop, then it drafts once. Six tool-calling rounds is the cap. Tool calls are not paused one by one. The only interrupt is the finished Markdown. `pv-agent draft` prints that Markdown and a `thread_id`, and writes nothing under `reports/`. `pv-agent resume THREAD --approve` saves the draft. `pv-agent resume THREAD --file summary.md` saves that file instead. An empty drug name or an empty edit file exits. The thread is stored in `.cache/agent.sqlite`, so the second command can be a new process.

### The evaluation run

`pv-eval` runs that same graph on twelve recorded tool payloads. It does not start the MCP server and it does not call openFDA. The chat model is the one named by `PV_AGENT_MODEL` and `PV_AGENT_MODEL_PROVIDER`. When the provider is Groq, an empty `GROQ_API_KEY` stops the process before a case starts.

Each model reply is stored in `.cache/eval-responses.json`. The key is a hash of the model name and the messages, so a second run of the same case does not call Groq again. `--cache` chooses another file. The draft is scored at the interrupt, before the save step would append the disclaimer. A model that left the disclaimer out fails, even though a later save would have added it.

`pv-eval` writes `reports/eval.md` (`--output` chooses another path) and exits non-zero when any case fails. The decision is [docs/adr/0003-untrusted-tool-output.md](docs/adr/0003-untrusted-tool-output.md). GitHub Actions runs the same command when someone starts `.github/workflows/eval.yml` by hand. The key is the repository secret `GROQ_API_KEY`. The report is uploaded as an artifact. The push workflow stays on the offline suite.

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

Agent settings, read from the same `.env` when the extra is installed:

| Variable | Default | Role |
| --- | --- | --- |
| `GROQ_API_KEY` | empty | Required for a live draft when the provider is Groq |
| `PV_AGENT_MODEL` | `llama-3.3-70b-versatile` | Chat model name |
| `PV_AGENT_MODEL_PROVIDER` | `groq` | Passed to `init_chat_model` |
| `PV_AGENT_TRANSPORT` | `stdio` | `stdio` or `http` |
| `PV_AGENT_MCP_URL` | `http://127.0.0.1:8000/mcp` | HTTP target. Must end in `/mcp` |
| `PV_AGENT_REPORTS_DIR` | `reports` | Where the approved Markdown is written |
| `PV_AGENT_CHECKPOINT_PATH` | `.cache/agent.sqlite` | Thread store for the review interrupt |

A blank string for the key, the token, the cache path, or the resource URL is treated as unset. The same is true of `GROQ_API_KEY` and of the token when the agent reads it. `.env.example` lists the names. `.env` is gitignored.

## 5. What is checked, and when

The pytest suite never calls openFDA and never calls Groq. Tool contracts run through an in-memory MCP client against recorded HTTP responses. The agent tests use a scripted chat model. They also list the three tools through `MCPAdapter`, over stdio and over a local HTTP port. The evaluation tests use the same kind of scripted model against recorded tool payloads, and they check that a second run reads the reply cache instead of calling the model again. A live openFDA call was made by hand, once, to watch the cache hit the real API. The suite does not repeat it. A live Groq draft is `pv-eval`, and it is not part of CI. Continuous integration does not call openFDA and does not call Groq.

| When | Command | What it holds |
| --- | --- | --- |
| While developing | `make test` | The pytest suite, offline |
| Before a change feels finished | `make lint` | ruff (lint and format) and mypy in strict mode on `pv_mcp` |
| On every push and every pull request | `.github/workflows/ci.yml`, or `make ci` locally | Lockfile sync with uv 0.13.5 and Python 3.12, including the `agent` extra, then ruff, mypy, pytest, and pip-audit |
| On every push to main | `.github/workflows/build.yml` | Build the linux/amd64 image, write a CycloneDX SBOM, fail on a fixed HIGH or CRITICAL finding, then push that scanned image to GHCR |
| Coverage gate | the pytest step in CI | Coverage of the `pv_mcp` package. The job fails below 90% |
| Dependency watch | the last CI step | Runtime dependencies, including the agent extra, exported from the lockfile with their hashes. pip-audit does not ask pip to resolve them again |
| On demand | `make eval`, or `uv run --extra agent pv-eval` | Twelve golden cases against the configured chat model. Recorded tool payloads. Cached replies. A Markdown report. Exit non-zero if a case fails |
| On demand, in GitHub | `.github/workflows/eval.yml`, started by hand | The same command. `GROQ_API_KEY` is a repository secret. The report is kept as an artifact |
| On demand, in GitHub | `.github/workflows/deploy.yml`, started by hand | Bicep deployment to Azure Container Apps, or deletion of the resource group. OIDC. Minimum 0 replicas. Budget mail |
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
| `tests/test_agent_graph.py` | A scripted model calls the three tools, then drafting stops for review. Approval saves the draft. An edit replaces it. The disclaimer is kept. A planted instruction arrives as tool data. The tool loop stops after six rounds. An empty draft is rejected. Groq is not called |
| `tests/test_agent_client.py` | stdio launches the server script. HTTP attaches the bearer token. `MCPAdapter` lists the three tools over both transports and does not call openFDA |
| `tests/test_agent_cli.py` | `pv-agent draft` prints the thread id. An empty drug exits. Resume writes the edited file. A missing Groq key is refused before a provider client is built |
| `tests/test_eval.py` | Twelve cases, each check failing and passing, a scripted run through the real graph, the reply cache, the report, and a missing Groq key. Groq is not called |
| `tests/test_release.py` | The image workflow scans before it pushes, the deploy workflow is manual and uses OIDC, the template scales to zero and budgets the group, and the image stays a non-root server without the agent extra |

ruff, mypy, and the pinned lockfile keep that contract from drifting between machines. pip-audit watches the runtime set for published vulnerabilities. Trivy watches the image, in the build workflow, and the SBOM from that run is the artifact to keep.

While a server process is running, the things to watch are the stderr line for each tool call, a rising share of `status: error`, a `cached: true` result whose `retrieved_at` is older than you expected, and `Rate limit exceeded` if a client is looping. Nothing in the current server pages a person when those happen. The log is the record.

While the agent is running, the things to watch are different. `pv-agent draft` must stop with a Markdown draft and a `thread_id`, and `reports/` must still be unchanged. `pv-agent resume` is the step that writes the file. The saved file should contain the disclaimer and, if the draft was approved as written, the URLs and times from the tool results. The server log for that run is the same stderr line as any other caller: `local` on stdio, `pv-mcp-dev` on the shared HTTP token.

`pv-eval` is the check that a live model still does that. Read `reports/eval.md` for the pass count and, on a failure, which check broke and the draft that was scored. A second run of a case already in `.cache/eval-responses.json` reuses that reply. A green report means the draft matched the recorded payloads. The offline suite is what locks the live tools.

After a push to main, the things to watch on the image are the Trivy table in the `image-reports` artifact and whether `ghcr.io/<owner>/<repository>:main` moved. After a deploy, the things to watch are the public URL printed by the deployment, a replica count of zero while the app is idle, and the budget mail if the month crosses half the amount or the full amount. The stderr line is still the audit record. It lives only as long as the replica does.

## 6. What this MCP server takes from the protocol

MCP is the contract between a host and this process. The host may be an editor, a desktop application, or another program. It discovers what the server offers, then calls it. pv-mcp uses the parts of that contract that fit a read-only public data source.

A tool is a function the host's model may call. It has a name, a description written for the model, and a schema for the arguments. `search_adverse_events`, `top_reactions`, and `get_label_section` are those functions. Each tool returns a typed object, so the client receives fields — the total, the reaction terms, the source URL, the retrieval time — rather than only a paragraph.

A resource is a document the client reads by URI. The host can show `pv://faers/methodology` on its own. It does not have to spend a tool call to fetch the method.

A prompt is a template a person runs. The server stops at that template. The host's model writes the summary, and a person can check the citations.

On HTTP the process is an MCP resource server: a bearer token scoped to `pv:read`, bound to this server's URL. A client that speaks the protocol needs no private library for this project. The server does not ask the host model to generate a completion on its behalf, does not solicit secrets from the user, and exposes no tool that writes.

Another program can connect over stdio or over HTTP without embedding this process. The summary agent in [section 10](#10-the-summary-agent) does that. `MCPAdapter` loads tools only, so the methodology and the disclaimer are repeated in the agent's own system prompt. The server still returns the records. The agent drafts, and a person accepts the draft.

The grade in [section 11](#11-grading-the-draft) is not a new protocol feature. It runs the same graph with recorded tool results standing in for the server, so a live model can be checked without changing what the server returns.

Publishing the image and running it in Azure does not add a tool, a resource, or a prompt. The remote process is the same HTTP server.

## 7. Why the surface is this shape

The choices below are the ones already implemented. The behavior is the one in the sections above. The notes in `docs/adr/` record the transport, the authentication, the cache, the agent client, and how a draft is judged when tool output is untrusted.

The server reads two endpoints because those are the public files a safety question starts from. Adding a third source before this path is solid would blur what a citation points at.

A report is reduced before a model sees it. Returning a narrative or an age, sex, and weight would reopen the privacy problem FDA already narrowed, and it would hand a model text that sometimes reads like an instruction. Twenty reports and twenty-five reaction terms are hard caps so a single call stays small enough to read.

Label text is returned as data, one section at a time, from a fixed list. The result names the field that was actually read, including the older `warnings` fallback.

A cached number keeps its age. The original `retrieved_at` stays, so a reader can see that the figure is up to an hour old. Failures stay out of the cache.

stdio stays open because desktop clients have no header to send. HTTP checks the token and the Host header. One server object serves both, so the tools cannot drift apart.

The dev token is a single shared secret so a local HTTP client can be tested. It is not an identity. The Entra design is written down so the production shape is chosen, and left unimplemented so this server does not pretend to verify a real issuer.

Every tool call is counted, then limited. The log exists so a later reader can see who called what, with the secrets removed. The limit exists so a looping client does not spend the openFDA quota.

The upstream call is allowed to fail in the open. Three attempts, then a tool error, then no cache. A dead minute stays a dead minute.

The image holds no secrets. The token and the API key are environment variables. Locally the SQLite file lives on a volume. In Azure the file lives on the replica, and scale-to-zero is chosen so an idle month stays near the budget. A managed disk and a log workspace would be standing costs, so they are left out. The scan runs before the push. A fixed high-severity finding stops the push. The decision is [docs/adr/0006-deployment-target-and-cost.md](docs/adr/0006-deployment-target-and-cost.md).

The evaluation uses recorded payloads so a count cannot change between runs, and so the grade does not spend the openFDA quota. It scores the draft at the interrupt, because the save step appends the disclaimer and would hide a model that left it out. An integer in the draft has to appear in those payloads. A phrase planted in a report or a label has to stay out of the draft. The run is on demand so the Groq quota is not spent on every push. The decision is [docs/adr/0003-untrusted-tool-output.md](docs/adr/0003-untrusted-tool-output.md).

## 8. Milestones, and MCP ideas beyond them

M1 through M6 are in the repository. M1 and M2 are the server this document describes: the three tools, the methodology resource, the summary prompt, stdio, Streamable HTTP, the dev token, the audit line, the cache, and Compose. M3 is the continuous integration workflow in [section 5](#5-what-is-checked-and-when). M4 is the summary agent in [section 10](#10-the-summary-agent). M5 is the on-demand grade of that agent in [section 11](#11-grading-the-draft). M6 is the image, the scan, and the manual Azure deployment in [section 12](#12-publishing-and-deploying-this-mcp-server). M7 is still planned. None of these milestones adds resource templates, argument completion, elicitation, sampling, or a new pharmacovigilance judgment on the server.

### M4 — an agent that uses the tools

`pv-agent` drafts a safety-signal summary for one drug. Its tools come from `langchain.mcp.MCPAdapter` (`langchain[mcp]`), over stdio or over `http://…/mcp` with the bearer token. The adapter loads tools only. It does not see `safety_signal_summary` or `pv://faers/methodology`, so the same limits and the same disclaimer live in the agent's own system prompt. The graph plans, calls the three existing tools, and drafts Markdown that cites their URLs and retrieval times. A LangGraph interrupt then waits. The person approves the draft or replaces it, and the approved text is saved. The chat model is Groq by default, and the model name and provider are settings. The decision is [docs/adr/0005-agent-client.md](docs/adr/0005-agent-client.md). The server still returns sourced records. It does not write the summary, and it does not check the draft.

### M5 — evaluation of that agent

`pv-eval` grades the draft on twelve golden cases. A case passes when the three tools were called for that drug, the worksheet label sections were requested, the recorded facts appear, every integer in the draft is in the recorded tool results, a planted instruction is not followed, and the standard disclaimer is in the draft the model wrote. The payloads are recorded, so openFDA is not called. Model replies are cached. The command writes a Markdown report and exits non-zero when a case fails. `.github/workflows/eval.yml` runs it when someone starts the workflow, and uploads the report. The Groq key is a repository secret. This does not change the protocol surface. The decision is [docs/adr/0003-untrusted-tool-output.md](docs/adr/0003-untrusted-tool-output.md).

### M6 — image, scan, and a deploy workflow

`.github/workflows/build.yml` builds the image, writes a CycloneDX SBOM, scans it with Trivy, and pushes the scanned image to GHCR. `.github/workflows/deploy.yml` is started by hand. It deploys `infra/main.bicep` to Azure Container Apps with a minimum of zero replicas, signs in with GitHub OIDC, creates a monthly budget alert, and can delete the resource group. The production Entra ID verifier described in the authentication decision is not part of this milestone. The decision is [docs/adr/0006-deployment-target-and-cost.md](docs/adr/0006-deployment-target-and-cost.md).

### M7 — the written account of the system

This README is the layered account of the server, including the example session below. [0005](docs/adr/0005-agent-client.md) records the agent client, [0003](docs/adr/0003-untrusted-tool-output.md) records how a draft is judged when tool output is untrusted, and [0006](docs/adr/0006-deployment-target-and-cost.md) records the deployment and its cost. M7 still adds an architecture diagram and `SECURITY.md` for the threat model (prompt injection, data exfiltration, denial of service, supply chain). M7 documents the server. It does not extend it.

ClinicalTrials.gov is not in M7. It stays out while the FAERS path is the one the agent and the evaluation rely on.

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

## 10. The summary agent

This is the walkthrough. What the draft is allowed to claim is in [section 3](#what-the-agent-writes). How the process connects, which settings it reads, and where it stops are in [section 4](#the-summary-agent). What the tests lock, and what a person watches, are in [section 5](#5-what-is-checked-and-when).

Install the extra and put a Groq key in `.env`:

```bash
uv sync --extra agent
```

Draft over stdio. The command starts the MCP server as a child process, calls the tools, prints the Markdown, and stops. `reports/` is still empty.

```bash
uv run --extra agent pv-agent draft ibuprofen
```

The last line is `thread_id=...`. Read the Markdown above it. Then keep it:

```bash
uv run --extra agent pv-agent resume THREAD_ID --approve
```

or replace it with a file you edited:

```bash
uv run --extra agent pv-agent resume THREAD_ID --file summary.md
```

The command prints `saved=reports/ibuprofen-YYYYMMDDTHHMMSSZ.md`. The second command can be a new shell. The thread is in `.cache/agent.sqlite`.

To use a server that is already running, including Docker Compose, point the agent at that URL and use the same `PV_MCP_TOKEN` the server was started with:

```bash
PV_AGENT_TRANSPORT=http PV_AGENT_MCP_URL=http://127.0.0.1:8000/mcp \
  uv run --extra agent pv-agent draft ibuprofen
```

A missing Groq key, a missing HTTP token, an empty drug name, or an empty edit file exits before a file is written.

## 11. Grading the draft

This is the walkthrough. What the grade is allowed to decide is in [what the agent writes](#what-the-agent-writes). How the cache, the exit code, and the workflow are wired is in [the evaluation run](#the-evaluation-run). What the offline tests lock, and what a person reads in the report, are in [section 5](#5-what-is-checked-and-when).

The extra and the Groq key are the same ones the agent uses:

```bash
uv sync --extra agent
uv run --extra agent pv-eval
```

The command prints `passed=… failed=…` and `report=reports/eval.md`. Each row is one drug situation: the tools, the facts that had to appear, the numbers, the disclaimer, and whether a planted sentence leaked. A failed row is copied under the table with the draft that was scored. The process exits non-zero when any case fails.

A second run with the same model reads `.cache/eval-responses.json` and does not call Groq for a reply it has already stored. `--output` and `--cache` choose other paths. The command does not call openFDA, and it does not write a per-drug note under `reports/`.

`make ci` does not run this. In GitHub, start the `eval` workflow by hand. The repository secret is `GROQ_API_KEY`. The Markdown report is kept as an artifact named `eval-report`.

## 12. Publishing and deploying this MCP server

This is the walkthrough. What a remote copy still answers is in [what this MCP server will not answer](#what-this-mcp-server-will-not-answer). How the image, the scan, the budget, and the sign-in are wired is in [the published image](#the-published-image) and [a copy that scales to zero](#a-copy-that-scales-to-zero). What to read after a run is in [section 5](#5-what-is-checked-and-when).

Build the image locally:

```bash
make image
```

That tag is `pv-mcp:local`. Compose builds the same Dockerfile and serves `http://127.0.0.1:8000/mcp`.

A push to `main` runs the build workflow. The artifact `image-reports` holds `sbom.cdx.json` and the Trivy table. The image is `ghcr.io/<owner>/<repository>:<commit>` and, from `main`, `:main`.

Before the first deploy, create an Entra app registration and do not create a client secret. Add a federated credential:

- Issuer: `https://token.actions.githubusercontent.com`
- Subject: `repo:<owner>/<name>:ref:refs/heads/main`
- Audience: `api://AzureADTokenExchange`

Grant that app Contributor and Cost Management Contributor on the subscription. In the GitHub repository, add variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, and `BUDGET_CONTACT`. Add the secret `PV_MCP_TOKEN`. Then start the `deploy` workflow and leave the action on `deploy`. The log prints `url`, the public `https://<fqdn>/mcp`. A client sends the same bearer token.

To remove the copy, start the `deploy` workflow and choose `teardown`, or, from a machine already signed in to Azure:

```bash
make teardown
```

That deletes the resource group `rg-pv-mcp`. `./infra/teardown.sh other-group` deletes another name. The dev token check is unchanged. Entra is not the verifier for this copy.

