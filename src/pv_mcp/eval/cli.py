"""On-demand evaluation. CI does not run this against Groq."""

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from pv_mcp.agent.model import build_chat_model
from pv_mcp.agent.settings import AgentSettings
from pv_mcp.eval.cache import CachingModel, ResponseCache
from pv_mcp.eval.cases import cases
from pv_mcp.eval.run import render_report, run_cases, write_report


def main(argv: list[str] | None = None) -> None:
    """Grade the golden cases and write a Markdown report. Exit 1 when any case fails."""

    try:
        _main(argv)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def _main(argv: list[str] | None) -> None:
    parser = argparse.ArgumentParser(
        prog="pv-eval",
        description="Grade the summary agent on recorded tool results. Calls the chat model only.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Markdown report path. Defaults to reports/eval.md.",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="Where model replies are stored. Defaults to .cache/eval-responses.json.",
    )
    args = parser.parse_args(argv)
    output = args.output if args.output is not None else Path("reports/eval.md")
    cache_path = args.cache if args.cache is not None else Path(".cache/eval-responses.json")
    settings = AgentSettings()
    passed, failed, path = asyncio.run(_run(settings, output=output, cache_path=cache_path))
    print(f"passed={passed} failed={failed} cases={len(cases())}")
    print(f"report={path}")
    if failed:
        raise SystemExit(1)


async def _run(
    settings: AgentSettings,
    *,
    output: Path,
    cache_path: Path,
) -> tuple[int, int, Path]:
    model_name = f"{settings.pv_agent_model_provider}:{settings.pv_agent_model}"
    model = CachingModel(
        build_chat_model(settings),
        ResponseCache(cache_path),
        model_name,
    )
    when = datetime.now(UTC)
    grades = await run_cases(model)
    text = render_report(grades, model_name=model_name, when=when)
    path = write_report(output, text)
    failed = sum(1 for grade in grades if not grade.passed)
    return len(grades) - failed, failed, path
