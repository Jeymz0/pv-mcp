# pv-mcp — decisions a hiring manager can read in a few minutes

pv-mcp is a read-only MCP server in front of public pharmacovigilance data. A model can ask what FAERS has reported for a drug, and what the official label says, and every answer comes back with its query, its timestamp, and a reminder that a report is not proof of cause. The work shipped so far is that boundary: the tools, the two transports, authentication, an audit trail, a cache, and a container. The review agent, the evaluation suite, and the Azure deployment are later slices. The data boundary comes first, so a model is only introduced once the numbers have a source.

## The data, and why they are easy to misuse

Pharmacovigilance, often shortened to PV, is the work of detecting, assessing, and preventing adverse effects of medicines, mostly after they are on the market. A trial measures a drug in a chosen population for a limited time. PV is what happens once millions of people, with other illnesses and other drugs, take it in ordinary life. The useful question is usually a hypothesis: this reaction is showing up on reports more than we expected, and a person should look. The dangerous question is a rate, a ranking of two drugs, or a reason for a patient to start or stop a treatment. These files cannot answer that.

FAERS, the FDA Adverse Event Reporting System, is the U.S. Food and Drug Administration’s database of those reports. Manufacturers must send serious and unexpected cases. Health professionals and patients may send reports voluntarily. Each case is an individual case safety report, an ICSR, shaped by the ICH E2B standard. A report can list several drugs and several reactions. Nothing in the record ties one drug to one reaction. A drug may be marked suspect by the reporter, or it may only be concomitant, present at the same time. The FDA does not require the reporter to prove cause, and it does not medically confirm the story before the report is stored. Duplicates are common, because the patient, the clinician, and the company can each file the same event. There is no count of how many people took the drug, so a tally of reports is not an incidence. Publicity, a new label, or a longer time on the market changes how often people report.

openFDA is the FDA’s public API over datasets it has already decided to release. This server uses two endpoints. `drug/event` is FAERS, republished as JSON and refreshed quarterly, often lagging the underlying database by a few months. `drug/label` is Structured Product Labeling, SPL, the electronic label manufacturers submit. Labels update about weekly. They are a living document: boxed warning, warnings, adverse reactions, contraindications, indications. openFDA reformats them and does not verify them. The text on the API can differ from the carton in a pharmacy, and many over-the-counter labels were never approved line by line. Reaction names on the event side are MedDRA, the Medical Dictionary for Regulatory Activities. A count in this server is a count of MedDRA preferred terms on matching reports, written so that “nausea” and “feeling sick” do not silently split.

People use the same files in four legitimate ways. A safety scientist screens a marketed drug for a reaction term worth a case series. A medical-information or labeling colleague reads the current U.S. warning, boxed warning, and adverse-reaction section before answering a question. A regulatory team watches whether a label changed. A model, in this project, drafts a short brief that cites the query and the retrieval time, for a human to accept or rewrite. None of those uses is a clinical decision. The FDA’s own public guidance is the same: the existence of reports does not establish that the product caused the event, the data are not a safety profile, and patients should talk to their doctor before changing a medicine.

Privacy is the other half of the same design. The case FDA holds includes a free-text narrative. That narrative can name a patient, a reporter, a hospital, or a date of birth, so FDA leaves it out of the public dashboard and the quarterly public files. A redacted narrative is a Freedom of Information request, reviewed before release. openFDA serves that public extract, and it says the API does not contain direct patient identifiers. The JSON can still carry age, sex, weight, receive dates, and a narrative field when one was left in the extract. Age plus a rare reaction plus a date is sometimes enough to recognize a person. This server makes a second cut. Tool results keep a report id, a receive date, a seriousness flag, reaction terms, and the product names as reported. They drop the narrative and the demographic fields, even if the payload included them. Label text is not patient data. It is still untrusted: a label can contain sentences that look like instructions, and the server returns them as data for a person to read.

The descriptions above follow the FDA’s public notes on [FAERS and the openFDA drug-event API](https://open.fda.gov/apis/drug/event/), the [drug-label API](https://open.fda.gov/apis/drug/label/), [CDER’s account of what the public dashboard withholds](https://www.fda.gov/drugs/cder-conversations/understanding-cders-postmarket-safety-surveillance-programs-and-public-data), and the [FOIA path for an individual narrative](https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems/instructions-requesting-individual-case-reports).

## A small surface, chosen on purpose

A portfolio that wraps five APIs looks busy and proves little. The call was to stay on two public openFDA endpoints, adverse-event reports and drug labels, and to leave ClinicalTrials.gov until the FAERS path was honest.

What shipped is three tools. One returns the matching total and a short list of reports. One counts MedDRA reaction terms. One reads a single section of the newest matching label. Next to them, a methodology resource states what FAERS cannot show, and a prompt template asks the client for a sourced summary. The model receives a bounded answer, written for it to use, with the limits in the tool description.

## Reports a model can quote

The public extract can still carry a narrative field and structured demographics. Returning either would reopen the privacy problem the FDA already tried to close, and it would hand a model text that sometimes reads like an instruction. Each report is reduced to an id, a receive date, a seriousness flag, reaction terms, and the product names as reported.

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
