# Security

This is the threat model for pv-mcp, a read-only MCP server over public FDA files. It describes what the project holds, how four abuses show up, and what is left open. It does not add a control the code does not already have.

The version in this repository is 0.1.0 on `main`.

## Reporting a vulnerability

Open a private security advisory on this GitHub repository. Put a public issue in only when the detail can be read by anyone without making the problem easier to use. Do not send secrets, tokens, or patient text in the report.

## What is in scope

The MCP server, the summary agent, the image, and the Azure deployment described in the README.

A report that reaches the model is public text from openFDA. The server drops the narrative and the age, sex, and weight before that text is returned. The files the FDA already withholds stay withheld. This project does not hold a patient database.

Secrets the process can see are `PV_MCP_TOKEN`, `OPENFDA_API_KEY`, and, when the agent runs, `GROQ_API_KEY`. The Azure sign-in uses a federated credential. There is no Azure client secret in the repository.

## Prompt injection and poisoned tool output

A label sentence or a reaction term can read like an instruction. openFDA republishes that text. The server cannot know which sentence was written as a warning and which was planted.

The server returns the text as a field. It does not interpret it, and it does not follow it. The methodology resource and the `safety_signal_summary` prompt tell the caller to treat that text as data. The agent copies the same rule into its system prompt, because the adapter that loads the tools does not load the prompt or the resource. Tool results stay in tool messages. A person reads the draft before it is saved. Twelve recorded cases check that a planted phrase stays out of the draft and that a number in the draft was in the tool result. Those cases run when someone starts them. They are not part of every push.

What remains open: a model can still obey the planted sentence. The server does not grade the draft. The save step appends the disclaimer if the text lost it, so a file on disk is not proof the model wrote the disclaimer. The evaluation scores the draft at the interrupt, before that append. A person is still the one who accepts the note.

## Data leaving the process

The tool result is a count, a short list of public reports, or one section of a label, plus the query URL and the time it was read. Report rows keep an id, a receive date, a serious flag, up to eight reaction terms, and up to eight product names. They do not keep the narrative or the demographic fields.

The audit line on stderr records the caller, the tool, the parameters, the latency, the status, and the result size. Field names that hold a token, a key, or a password are replaced. Strings longer than 200 characters are cut. The openFDA key is not part of the URL in the result and not part of the cache key.

stdio has no header to check. A person who can start the process on that machine can call the tools. That is the desktop shape. Streamable HTTP requires the bearer token, checks it in constant time, and accepts it only for this server's URL and the scope `pv:read`. A request whose Host header is not localhost and not the host in `PV_MCP_RESOURCE_URL` is rejected.

The agent sends the tool results to the configured chat model. With the default provider, that is Groq. Those results are the public fields above. A draft saved under `reports/` stays on the machine that ran the agent.

What remains open: the dev token is one shared secret. Every HTTP caller is the same identity, `pv-mcp-dev`, for the audit line and the rate limit. The production check against Microsoft Entra ID is written in `docs/adr/0002-authentication.md` and is not built. A person who has the token can read the same public files the server can read.

## Denial of service

A call is bounded before it can fan out.

- The drug name is a plain string, 1 to 200 characters. Characters that would change the openFDA query are rejected.
- `search_adverse_events` returns at most 20 reports. `top_reactions` returns at most 25 terms. A label section is cut, by default at 4,000 characters.
- The openFDA body is refused above 1,500,000 bytes. The timeout is 20 seconds, and at most 60. A timeout, HTTP 429, or a 5xx status is tried three times, then reported. The failure is not cached.
- Each caller gets 60 tool calls a minute. The window is in memory. A new process starts at zero. On Azure the maximum is one replica, and a replica that has scaled to zero starts empty.
- Identical public reads are served from SQLite for an hour, so a repeated question does not spend the openFDA quota again.

The monthly budget mails a person at half the amount and at the full amount. The mail does not stop the app. The default amount is 5, in the subscription's billing currency.

What remains open: the anonymous openFDA quota is small, and a token holder can spend it. The shared dev token is one bucket, so one client can crowd out another. Scaling to zero drops the cache and the rate-limit window.

## Supply chain

Runtime dependencies are pinned in `uv.lock`. On every push, `ci.yml` runs ruff, mypy, pytest, and pip-audit of that locked set, including the agent extra. The tests do not call openFDA or Groq.

The image runs as uid 10001, does not install the agent extra, and does not contain a token or an API key. The build applies Debian security updates, writes a CycloneDX SBOM, and scans with Trivy. A fixed HIGH or CRITICAL finding stops the push. An unfixed finding in the base image is reported and does not, by itself, stop the push. The SBOM and the table are the artifact `image-reports`.

GitHub signs in to Azure with OIDC. The workflow does not store an Azure client secret or a registry password. The image is pulled from GHCR. The workflow asks GitHub to mark the package public. When that request is refused, the package stays private until someone sets it public, and Azure cannot pull it.

What remains open: GitHub Actions are pinned to release tags, not to a commit digest. Dependency updates are applied by hand. There is no Dependabot configuration in this repository. pip-audit and Trivy are the checks that run. A finding with no fix yet can remain in the base image until Debian publishes one and the next build picks it up.

## What this model does not claim

The server does not decide that a drug caused a reaction, and it does not tell a patient to start or stop a medicine. The disclaimer on every result says the same thing. Passing the evaluation, or passing the image scan, does not make a draft medical advice.
