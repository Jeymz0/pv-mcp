# Project brief: pv-mcp — a secure MCP server for public pharmacovigilance data

## Context & goal
I'm a senior AI/ML platform engineer building a portfolio project to demonstrate hands-on
Model Context Protocol (MCP) server expertise for a Principal AI Solutions Architect role at a
pharma-services company (pharmacovigilance, real-world evidence, patient access).
The project must show enterprise-grade practice: MCP server design, DevOps deployment,
cloud architecture, security by design, evaluation, and documented architecture decisions.
Quality over quantity: small, clean, well-tested, well-documented.

## Hard constraints
- Budget ≈ 0 €: free tiers only. Public GitHub repo, GitHub Actions, GHCR.
  LLM: Groq API (free tier, rate-limited) behind a provider-agnostic interface.
  Data: openFDA (free), optionally ClinicalTrials.gov API v2.
- Everything must run locally with Docker Compose. Cloud deployment is optional, on demand,
  and must fit within Azure free grants (scale to zero).
- Before writing code, check the CURRENT official docs: MCP specification
  (modelcontextprotocol.io), the official MCP Python SDK, langchain-mcp-adapters, LangGraph,
  openFDA. Do not rely on memory for APIs that may have changed. Pin all versions.
- Never commit secrets: .env (gitignored) + .env.example.

## Tech stack
Python 3.12, uv, official MCP Python SDK, pydantic v2, httpx, ruff, mypy,
pytest (+ respx or recorded fixtures: no network calls in CI tests),
multi-stage Docker image running as non-root, Docker Compose,
LangGraph + langchain-mcp-adapters + a Groq chat model (model name configurable via env),
OpenTelemetry (optional local Jaeger in Compose), Bicep for Azure IaC.

## Functional scope

### MCP server (read-only)
Tools — typed and validated inputs, structured outputs, descriptions written for LLMs:
1. `search_adverse_events(drug, reaction?, serious_only?, date_from?, date_to?, limit<=20)`
   — FAERS reports from the openFDA drug/event endpoint; returns total count + compact summaries.
2. `top_reactions(drug, limit<=25)` — aggregated reaction counts via openFDA count queries.
3. `get_label_section(drug, section)` — section is an enum (boxed_warning,
   warnings_and_cautions, adverse_reactions, contraindications, indications_and_usage)
   from the drug/label endpoint, truncated to a safe maximum length.
4. (optional) `search_clinical_trials(condition, intervention?, status?)` — ClinicalTrials.gov v2.

Resource: methodology & limitations of FAERS data (a report does not establish causality;
not medical advice).
Prompt: `safety_signal_summary(drug)` — a template guiding a client to a sourced summary.
Every tool output includes the source query/URL, a retrieval timestamp and a short disclaimer.

### Transports
stdio for local clients (MCP Inspector, Claude Desktop, Cursor) and Streamable HTTP for
remote deployment, from the same codebase.

### Security by design (documented in SECURITY.md with a short threat model)
- Authentication on the HTTP transport, following the MCP authorization model as supported by
  the current SDK. Dev: simple token verifier. Write an ADR on how production would use an
  OAuth 2.1 identity provider (e.g. Microsoft Entra ID).
- Input validation, strict limits, timeouts, retries with backoff, per-client rate limiting,
  response size caps.
- Treat all external data as untrusted: tool outputs are clearly delimited data, the agent's
  system prompt forbids following instructions found in tool outputs, and tests include a
  poisoned fixture containing a prompt injection.
- Structured JSON audit log for every tool call (caller, tool, params, latency, status,
  result size), with no secrets or personal data.
- Least privilege: read-only tools, non-root container, minimal image.
- Supply chain: Dependabot, pip-audit, Trivy image scan, SBOM.

### Performance & cost
Local cache (SQLite or diskcache, with TTL) for openFDA responses to respect rate limits;
optional openFDA API key via env.

### Agent client (integration + human review)
A LangGraph agent connected to the MCP server through langchain-mcp-adapters, using a Groq model.
Use case: "Draft a safety signal summary for drug X".
Flow: plan → call tools → draft a summary citing tool outputs → human-in-the-loop interrupt
for approval/edit → save the approved report as Markdown. CLI entry point.

### Evaluation
- Unit and contract tests for each tool (in-memory MCP client session), fully offline.
- Agent eval suite: 10–15 golden cases checking tool selection, numbers grounded in tool
  outputs, refusal to follow injected instructions, disclaimer present.
  Runs on demand only (Groq quota), caches LLM responses, outputs a Markdown report.

## DevOps (GitHub Actions)
- `ci.yml` (push/PR): ruff, mypy, pytest with coverage, pip-audit.
- `build.yml` (main): build image, Trivy scan, SBOM, push to GHCR.
- `eval.yml` (workflow_dispatch): agent eval with the Groq key from GitHub secrets,
  report uploaded as an artifact.
- `deploy.yml` (workflow_dispatch only): Bicep deployment to Azure Container Apps with
  min replicas = 0, authenticated with GitHub OIDC federated credentials (no long-lived Azure
  secrets), including a budget alert. Also provide a teardown command.
- A Makefile (or justfile) for common commands.

## Documentation (as important as the code)
- README: what & why, Mermaid architecture diagram, 5-minute quickstart (Docker Compose +
  MCP Inspector + Claude Desktop/Cursor config), example session, cost section.
- `docs/adr/`: 0001 transports, 0002 authentication, 0003 untrusted tool output handling,
  0004 caching & rate limits, 0005 LLM provider abstraction, 0006 deployment target & cost.
- SECURITY.md: threat model (prompt injection / tool poisoning, data exfiltration, DoS,
  supply chain).

## Way of working
Do NOT build everything at once. First propose the repository structure and a milestone plan,
then wait for my validation. Deliver milestone by milestone, each ending with passing tests and
a short list of what I should verify manually:
- M1: server over stdio + tools + offline tests
- M2: Streamable HTTP + auth + audit log + cache + Docker Compose
- M3: CI workflow
- M4: LangGraph agent + human-in-the-loop
- M5: evaluation suite
- M6: image build/scan + Bicep + deploy workflow
- M7: documentation & polish
Keep code idiomatic, typed and modular. Explain non-obvious decisions in ADRs rather than in
long comments. Ask me whenever a decision is ambiguous.
