# pv-mcp — decisions a hiring manager can read in a few minutes

pv-mcp is a read-only MCP server in front of public pharmacovigilance data. A model can ask what FAERS has reported for a drug, and what the official label says, and every answer comes back with its query, its timestamp, and a reminder that a report is not proof of cause. The work shipped so far is that boundary: the tools, the two transports, authentication, an audit trail, a cache, and a container. The review agent, the evaluation suite, and the Azure deployment are later slices. The data boundary comes first, so a model is only introduced once the numbers have a source.

## A small surface, chosen on purpose

A portfolio that wraps five APIs looks busy and proves little. The call was to stay on two public openFDA endpoints, adverse-event reports and drug labels, and to leave ClinicalTrials.gov until the FAERS path was honest.

What shipped is three tools. One returns the matching total and a short list of reports. One counts MedDRA reaction terms. One reads a single section of the newest matching label. Next to them, a methodology resource states what FAERS cannot show, and a prompt template asks the client for a sourced summary. The model receives a bounded answer, written for it to use, with the limits in the tool description.

## Reports a model can quote

FAERS records contain free-text narratives and patient demographics. Returning those would create a privacy problem and a prompt-injection problem, for no gain in a signal summary. Each report is reduced to an id, a receive date, a seriousness flag, reaction terms, and the product names as reported.

The caller passes a drug name in plain language. The server quotes it into an openFDA search and rejects characters that would change the query. Caps are hard: twenty reports, twenty-five reaction terms, real calendar dates only. When openFDA answers HTTP 404, the tool returns an empty success. No match is a valid answer.

## Label text stays data

Labels are long, inconsistent across years, and sometimes written like instructions to the reader. The server exposes one section at a time, from a fixed list, and cuts the text at a fixed length. The result names the field that was actually read.

Older labels keep precautions under `warnings` rather than `warnings_and_cautions`. The server falls back to that field and says so. A test plants an instruction inside label text and checks that it comes back as text in the payload. The server has no path that would follow it.

## Every number keeps its source

A safety sentence that cannot be traced to a query is useless in this domain. Every tool result carries the endpoint, the search, the URL, the time openFDA was read, and the same short disclaimer. An optional API key raises the anonymous quota. It travels only on the upstream request. It is removed from the URL the model sees.

Repeated public queries are answered from SQLite for an hour. The cache key is a hash of the path and the public parameters, so two API keys share one row and the key itself is never stored. Timeouts, HTTP 429, and server errors are retried and then left uncached, so a bad minute does not become the answer for the next hour. A hit keeps the original retrieval time and sets `cached` to true. The reader can see the age of the number.

## One process, two ways in

Desktop clients speak stdio. A container needs HTTP. The current Python SDK takes one server object and chooses the transport at startup, so both modes are the same code. The deprecated SSE transport is unused.

stdio has no header to inspect, so it stays open for a local client such as Cursor or MCP Inspector. Streamable HTTP serves `/mcp` for anything remote. Binding all interfaces does not widen the Host check. DNS rebinding protection stays on, and a request that names another host is rejected.

## HTTP behaves as a resource server

The MCP authorization model treats this process as a resource server. Development uses one static bearer token from the environment, compared in constant time, accepted only for this server’s URL and the scope `pv:read`. A missing or wrong token is HTTP 401. The HTTP process exits on startup when the token is empty.

The production identity provider is written down and left unimplemented: OAuth 2.1 with Microsoft Entra ID. Entra would issue the token, this server would only verify audience, issuer, expiry, and scope, and the caller id would become the user. The shared dev client `pv-mcp-dev` is enough for a local demo. The architecture note says it is the wrong model for a shared host.

## The server can account for what was asked

Each tool call appends one JSON line to stderr. stdio already owns stdout for the protocol, so the log cannot share it. The line records the caller, the tool, the parameters, the latency, the status, and the size of the result. Secret field names are redacted, and long strings are cut. Narratives never enter the tools, so they never enter the log.

A one-minute sliding window limits how often one caller may invoke a tool. Listing tools does not spend that budget. Crossing the limit returns a tool error, writes the audit line, and does not call openFDA. With the dev token, every HTTP client shares one bucket. That consequence is part of the design note, not an accident.

## The upstream API is assumed to fail

openFDA times out and returns 429 and 503 under ordinary load. The client allows three attempts with a short backoff, refuses a body over a fixed size, and surfaces a dead request as a tool error the model can read. The failure is not cached.

## The container is the smallest privilege that runs

The image runs as a non-root user. The token and the API key come from the environment, never from the image. Compose publishes the port and keeps the SQLite file on a volume. Image scanning, the SBOM, and the Azure deployment are the next operational slice.

## The tests never call the internet

A green run cannot depend on openFDA’s quota or on the network in CI. Tool contracts run through an in-memory MCP client against recorded HTTP responses. The HTTP path is exercised in-process: anonymous calls are rejected, a valid token is accepted, a foreign Host is rejected, and a second identical call is served from the cache. ruff, mypy in strict mode, and pinned dependencies keep that contract from drifting. A live call was made by hand, once, to watch the cache hit against the real API. The suite does not repeat it.
