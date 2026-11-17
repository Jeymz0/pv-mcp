"""CLI: draft a summary, then approve or replace it."""

import argparse
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from pv_mcp.agent.connection import mcp_target
from pv_mcp.agent.graph import ReviewDecision, compile_summary_graph, initial_state
from pv_mcp.agent.model import build_chat_model
from pv_mcp.agent.settings import AgentSettings


def main(argv: list[str] | None = None) -> None:
    """Entry point for ``pv-agent``. A missing secret or a bad URL exits the process."""

    try:
        _main(argv)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def _main(argv: list[str] | None) -> None:
    parser = argparse.ArgumentParser(
        prog="pv-agent",
        description="Draft a sourced safety-signal summary and wait for a person to accept it.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    draft = commands.add_parser("draft", help="Call the tools and stop with a draft.")
    draft.add_argument("drug", help="Plain drug name, for example ibuprofen.")
    resume = commands.add_parser("resume", help="Approve the draft, or replace it, and save.")
    resume.add_argument("thread_id", help="thread_id printed when the draft stopped.")
    choice = resume.add_mutually_exclusive_group(required=True)
    choice.add_argument("--approve", action="store_true", help="Save the draft as written.")
    choice.add_argument("--file", type=Path, help="Save this Markdown file instead of the draft.")
    args = parser.parse_args(argv)
    settings = AgentSettings()
    if args.command == "draft":
        thread_id, text = asyncio.run(run_draft(settings, args.drug))
        print(text)
        print(f"thread_id={thread_id}")
        return
    decision = _decision(approve=args.approve, file=args.file)
    path = asyncio.run(run_resume(settings, args.thread_id, decision))
    print(f"saved={path}")


def _decision(*, approve: bool, file: Path | None) -> ReviewDecision:
    if approve:
        return ReviewDecision(action="approve")
    if file is None:
        raise ValueError("Resume with --approve or --file.")
    markdown = file.read_text(encoding="utf-8")
    if not markdown.strip():
        raise ValueError("The edited file is empty.")
    return ReviewDecision(action="edit", markdown=markdown)


async def run_draft(settings: AgentSettings, drug: str) -> tuple[str, str]:
    """Run until the review interrupt. Returns the thread id and the draft."""

    if not drug.strip():
        raise ValueError("drug must not be empty.")
    thread_id = uuid4().hex
    async with open_graph(settings) as graph:
        result = await graph.ainvoke(
            initial_state(drug),
            {"configurable": {"thread_id": thread_id}},
        )
    interrupts = result.get("__interrupt__") or []
    if not interrupts:
        raise ValueError("The run finished without a draft to review.")
    payload = interrupts[0].value
    draft = payload["draft"] if isinstance(payload, dict) else ""
    if not isinstance(draft, str) or not draft.strip():
        raise ValueError("The review interrupt did not include a draft.")
    return thread_id, draft


async def run_resume(
    settings: AgentSettings,
    thread_id: str,
    decision: ReviewDecision,
) -> str:
    """Continue a saved thread and return the path of the approved file."""

    async with open_graph(settings) as graph:
        result = await graph.ainvoke(
            Command(resume=decision.model_dump()),
            {"configurable": {"thread_id": thread_id}},
        )
    path = result.get("report_path")
    if not isinstance(path, str) or not path:
        raise ValueError("This thread did not save a report.")
    return path


@asynccontextmanager
async def open_graph(settings: AgentSettings) -> AsyncIterator[Any]:
    """Checkpoint, MCP tools, and the compiled graph for one command."""

    from langchain.mcp import MCPAdapter

    settings.pv_agent_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(settings.pv_agent_checkpoint_path)) as saver:
        async with MCPAdapter(mcp_target(settings)) as adapter:
            tools = await adapter.list_tools()
            yield compile_summary_graph(
                build_chat_model(settings),
                tools,
                checkpointer=saver,
                reports_dir=settings.pv_agent_reports_dir,
            )
