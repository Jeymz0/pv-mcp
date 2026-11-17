# 0005. The summary agent

## Status

Accepted for milestone M4.

## Context

A person can already call the three tools from a desktop MCP client. The next
step is a program that calls them and drafts a Markdown summary. The draft has
to stop for a person before it is saved. The server must stay the source of
the records. It does not write the summary, and it does not check the draft.

`MCPAdapter` loads tools only. It does not see `safety_signal_summary` or
`pv://faers/methodology`.

## Decision

The agent is a LangGraph graph in this repository, installed with the `agent`
extra. The server image does not install that extra.

- Tools come from `langchain.mcp.MCPAdapter` over the wire. stdio launches
  `stdio_server.py` with the parent environment. HTTP passes `PV_MCP_TOKEN` to
  a FastMCP `Client` as a bearer token. The client pins the initialize
  handshake (`mode="legacy"`), which is the era this MCP Python server speaks.
- The agent does not construct or embed an `MCPServer`.
- The chat model is created with `init_chat_model`. The provider and the model
  name are settings. Groq is the default. A missing `GROQ_API_KEY` stops the
  process before a draft starts.
- The system prompt repeats the FAERS methodology and forbids following
  instructions found in tool output. Tool results stay in tool messages.
- The graph may call tools in a loop, capped at six rounds. It then drafts
  once. `interrupt` pauses on that Markdown. Resume with approve, or with a
  replacement. The approved text is saved under `reports/`, and the disclaimer
  is appended when the text no longer contains it.
- Read-only tool calls are not interrupted one by one.
- The LangGraph checkpointer is a local SQLite file so a second command can
  resume the same thread. Tests use an in-memory checkpointer and a scripted
  chat model. They do not call Groq or openFDA. A separate test lists the
  three tools through the adapter, over stdio and over HTTP.

## Consequences

Evaluation of the live model is milestone M5. It is not part of `ci.yml`.
The production identity provider is still the design in
[0002](0002-authentication.md). The dev token remains one shared client id.
