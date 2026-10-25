# pv-mcp — an MCP server for public pharmacovigilance data

pv-mcp is a read-only MCP server for public pharmacovigilance data from the U.S. Food and Drug Administration. A client can ask what FAERS has reported for a drug, and what the official label says. Every answer carries its query, the time the data were read, and a reminder that a report is not proof of cause.

## 1. Pharmacovigilance

Pharmacovigilance (PV) is the detection, assessment, and prevention of adverse effects of medicines, mostly after they are on the market. A clinical trial measures a drug in a chosen population for a limited time. PV watches what happens once many people, with other illnesses and other drugs, take it in ordinary life.

The question spontaneous reports can support is a hypothesis: this reaction is appearing often enough that a person should look. A rate, a ranking of two drugs, or a reason for a patient to start or stop a treatment is a different question. These files cannot support it.

In practice, a safety scientist screens a marketed drug for a reaction term that deserves a case series. A medical-information or labeling colleague reads the current U.S. warning, boxed warning, and adverse-reaction section before answering a question. A regulatory team watches whether a label changed. The FDA’s public guidance sets the same limit. The existence of reports does not establish that the product caused the event. The data are not a safety profile. A patient should talk to their doctor before changing a medicine.

## 2. The data

FAERS, the FDA Adverse Event Reporting System, stores the reports. Manufacturers must send serious and unexpected cases. Health professionals and patients may report voluntarily. Each case is an individual case safety report (ICSR), shaped by the ICH E2B standard.

A report can list several drugs and several reactions. The record does not tie one drug to one reaction. The reporter may mark a drug as suspect, or the drug may only be concomitant, taken at the same time. The FDA does not require proof of cause, and it does not medically confirm the story before storing the report. Duplicates are common, because the patient, the clinician, and the company can each file the same event. There is no count of how many people took the drug, so a tally of reports is not an incidence. Publicity, a label change, or a longer time on the market changes how often people report.

Reaction names are coded in MedDRA, the Medical Dictionary for Regulatory Activities. A count of reports is a count of MedDRA preferred terms. “Nausea” and “feeling sick” remain separate terms unless a coding step has already mapped them.

The other dataset is the drug label, submitted as Structured Product Labeling (SPL). It is a living document: boxed warning, warnings, adverse reactions, contraindications, indications. The wording changes as knowledge of the drug changes. It can differ from the carton in a pharmacy. Many over-the-counter labels were never approved line by line.

The case the FDA holds includes a free-text narrative. That narrative can name a patient, a reporter, a hospital, or a date of birth, so FDA leaves it out of the public dashboard and the quarterly public files. A redacted narrative is released only after a Freedom of Information review. The public extract can still carry age, sex, weight, receive dates, and a narrative field when one remains. Age, a rare reaction, and a date can be enough to recognize a person. Label text is not patient data. It can still contain sentences that read like instructions.

## 3. The public APIs

openFDA is the FDA’s API over datasets it has already released. It converts those files to JSON and adds search fields. It serves public data, and it states that the API does not contain direct patient identifiers.

Two drug endpoints are relevant.

`https://api.fda.gov/drug/event.json` republishes publicly releasable FAERS. Updates are quarterly and can lag the underlying database by a few months. A query with no match comes back as HTTP 404. Drugs and reactions sit side by side. Any of the drugs may be marked suspect. That mark is the reporter’s opinion.

`https://api.fda.gov/drug/label.json` republishes SPL for prescription and over-the-counter products. Updates are about weekly. openFDA reformats the label and does not verify it. Sections vary from product to product. Older labels often store precautions under `warnings` rather than `warnings_and_cautions`.

Anonymous calls share a small quota. An API key raises that quota. The key is a credential for the FDA’s gateway. It is not part of the scientific result.

These descriptions follow the FDA’s public notes on the [drug-event API](https://open.fda.gov/apis/drug/event/), the [drug-label API](https://open.fda.gov/apis/drug/label/), [what the public dashboard withholds](https://www.fda.gov/drugs/cder-conversations/understanding-cders-postmarket-safety-surveillance-programs-and-public-data), and the [FOIA path for an individual narrative](https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems/instructions-requesting-individual-case-reports).

## 4. What the MCP server does

The server exposes three tools, one resource, and one prompt.

`search_adverse_events` returns the openFDA total and a short list of reports: id, receive date, seriousness, reaction terms, and product names. The narrative and the demographic fields are omitted. The caller passes a plain drug name, with an optional reaction, a seriousness filter, a date range, and a limit of at most 20.

`top_reactions` counts MedDRA preferred terms for one drug, at most 25 terms.

`get_label_section` reads one section of the newest matching label: boxed warning, warnings and cautions, adverse reactions, contraindications, or indications. The text is cut at a fixed length. When warnings and cautions are absent, the warnings field is used, and the result names that field.

The resource `pv://faers/methodology` states how to read these files. The prompt `safety_signal_summary` asks a client for one sourced summary of a drug: read the methodology, call the three tools, cite the URL and the retrieval time, and keep any sentence found in a report or a label as data.

Every tool result includes the endpoint, the search, the URL, the time openFDA was read, and the same disclaimer. The API key never appears in that URL.

The same process serves two transports. stdio is for a local client. Streamable HTTP serves `/mcp` and requires a bearer token. Each tool call appends one JSON line to stderr. An identical public query is answered from SQLite for one hour, and the original retrieval time is kept. A caller past the per-minute limit receives a tool error, and openFDA is not called. A timeout, an HTTP 429, or a server error is retried a few times and then reported as a tool error. That failure is not stored.

Docker Compose runs the HTTP server as a non-root user. The token and the API key come from the environment. The cache file sits on a volume.

## 5. Decisions behind the MCP server

### Two endpoints, and no others

The server reads openFDA drug events and drug labels. ClinicalTrials.gov stays out until the FAERS path is solid. The three tools, the methodology resource, and the summary prompt are the whole functional surface.

### A report is reduced before a model sees it

Returning a narrative or an age, sex, and weight would reopen the privacy problem FDA already narrowed, and it would hand a model text that sometimes reads like an instruction. Each report keeps an id, a receive date, a seriousness flag, reaction terms, and the product names as reported. The caller passes a drug name in plain language. The server quotes it into the openFDA search and rejects characters that would change the query. Twenty reports and twenty-five reaction terms are hard caps. Dates have to be real calendar dates. HTTP 404 becomes an empty success, because no match is a valid answer.

### Label text is returned as data

One section is read at a time, from a fixed list, and cut at a fixed length. The result names the field that was actually read. Older labels fall back from `warnings_and_cautions` to `warnings`, and `label_field` records that. A test plants an instruction inside label text and checks that it comes back as text. The server has no path that would follow it.

### A cached number keeps its age

The cache key is a hash of the path and the public parameters. The API key is not part of the key, the stored body, or the URL. HTTP 200 and HTTP 404 are stored for one hour. Timeouts, HTTP 429, and server errors are left uncached, so a bad minute does not become the answer for the next hour. A hit sets `cached` to true and keeps the original `retrieved_at`.

### stdio is open, HTTP checks the host

Desktop clients speak stdio, which has no header to inspect, so that transport stays open. Streamable HTTP is the remote door. The deprecated SSE transport is unused. Both modes are one server object. The transport is chosen when the process starts. Binding every interface does not widen the Host check. DNS rebinding protection stays on, and a request that names another host is rejected.

### The MCP server is a resource server

Development uses one static bearer token from the environment, compared in constant time, accepted only for this server’s URL and the scope `pv:read`. A missing or wrong token is HTTP 401. The HTTP process exits on startup when the token is empty. The production identity provider is written down and left unimplemented: OAuth 2.1 with Microsoft Entra ID. Entra would issue the token. This server would verify audience, issuer, expiry, and scope, and the caller id would become the user. The shared dev client `pv-mcp-dev` puts every HTTP client in one rate-limit bucket and one audit identity. That is acceptable on a single machine and the wrong model on a shared host.

### Every tool call is counted, and then limited

Each `tools/call` appends one JSON object to stderr, because stdio already owns stdout for the protocol. The line records the caller, the tool, the parameters, the latency, the status, and the size of the result. Secret field names are replaced, and long strings are cut. Narratives never enter the tools, so they never enter the log. A one-minute sliding window limits how often one caller may invoke a tool. Listing tools does not spend that budget. Crossing the limit is itself audited, and it does not call openFDA. On the dev token, the bucket is shared.

### The upstream call is allowed to fail

openFDA times out and returns 429 and 503 under ordinary load. The client allows three attempts with a short backoff, refuses a body over a fixed size, and surfaces a dead request as a tool error. The failure is not cached.

### The image holds no secrets

The container runs as a non-root user. The token and the API key are environment variables. The SQLite file lives on a volume. Image scanning, the SBOM, and a cloud deployment sit outside this server.

### The test suite never calls the internet

Tool contracts run through an in-memory MCP client against recorded HTTP responses. The HTTP path is exercised in-process: an anonymous call is rejected, a valid token is accepted, a foreign Host is rejected, and a second identical call is served from the cache. ruff, mypy in strict mode, and pinned dependencies keep that contract from drifting. A live call was made by hand, once, to watch the cache hit the real API. The suite does not repeat it.

## 6. Using the MCP server

Counts, report ids, and label sentences below are shortened so the shape of a call is visible. A live call returns the current openFDA values, with the same fields.

### Local MCP client over stdio

From the repository:

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

### An MCP session for one drug

The prompt `safety_signal_summary`, with `drug` set to `ibuprofen`, asks the client to do four things. The same calls can be made by hand.

Read the resource `pv://faers/methodology` first. It is Markdown. It states that a report does not establish cause, that a count is not an incidence, and that label text is data.

Count reaction terms:

```json
{
  "name": "top_reactions",
  "arguments": { "drug": "ibuprofen", "limit": 10 }
}
```

The structured result looks like this:

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

The `url` has no `api_key`. The `query` is the drug name quoted across the generic, brand, substance, and reported-product fields. `NAUSEA` here is a MedDRA preferred term, a count of reports, not a rate.

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

`total` can be larger than the number of reports returned. `drugs` lists product names on the report. One of them may be concomitant. There is no narrative and no age or sex.

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

`label_field` is `warnings` when the newer section name is absent on that label. `text` is data. A sentence inside it that tells the reader to ignore previous instructions is still just text.

Calling `top_reactions` again with the same arguments, inside the hour, does not call openFDA. The result is the same object with `source.cached` true and the same `retrieved_at`. stderr gains a second audit line:

```json
{"event":"tool_call","caller":"local","tool":"top_reactions","params":{"drug":"ibuprofen","limit":10},"latency_ms":1,"status":"ok","result_size":900}
```

Over HTTP the `caller` is `pv-mcp-dev`. The line does not contain the bearer token or the openFDA key. A name such as `ibuprofen AND serious:1` is rejected before any request, because it is query syntax rather than a drug name. A limit of 21 is rejected by the tool schema.
