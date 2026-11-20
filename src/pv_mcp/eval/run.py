"""Run the golden cases through the summary graph and write a Markdown report."""

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from pv_mcp.agent.graph import compile_summary_graph, initial_state
from pv_mcp.eval.cases import EvalCase, cases
from pv_mcp.eval.score import Check, Grade, grade_case
from pv_mcp.openfda.models import DISCLAIMER


async def run_cases(model: Any) -> list[Grade]:
    """Grade every case. The model sees recorded tool results, not openFDA."""

    grades: list[Grade] = []
    for case in cases():
        grades.append(await run_case(case, model))
    return grades


async def run_case(case: EvalCase, model: Any) -> Grade:
    """Run one case until the review interrupt and score that draft."""

    try:
        with TemporaryDirectory() as directory:
            graph = compile_summary_graph(
                model,
                _tools(case),
                checkpointer=InMemorySaver(),
                reports_dir=Path(directory),
            )
            result = await graph.ainvoke(
                initial_state(case.drug),
                {"configurable": {"thread_id": case.id}},
            )
    except Exception as exc:  # a model or tool failure is a failed case, not a crash
        return Grade(
            case_id=case.id,
            passed=False,
            checks=[Check(name="run", passed=False, detail=str(exc))],
            draft="",
        )
    try:
        draft, calls = _paused(result)
    except ValueError as exc:
        return Grade(
            case_id=case.id,
            passed=False,
            checks=[Check(name="run", passed=False, detail=str(exc))],
            draft="",
        )
    return grade_case(case, tool_calls=calls, draft=draft)


def render_report(grades: list[Grade], *, model_name: str, when: datetime) -> str:
    """Markdown a person can read without opening the drafts first."""

    passed = sum(1 for grade in grades if grade.passed)
    lines = [
        "# Agent evaluation",
        "",
        f"Model: `{model_name}`",
        f"Ran at: {when.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"Cases: {passed} passed, {len(grades) - passed} failed, {len(grades)} total.",
        "",
        "The tools returned recorded payloads. openFDA was not called. "
        "The draft is scored before a person edits it, so the disclaimer has to "
        "come from the model. The save step would append it later.",
        "",
        "| Case | Tools | Mentions | Grounded | Disclaimer | Refusal | Result |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for grade in grades:
        row = (
            f"| {grade.case_id} | {_mark(grade, 'tools')} | {_mark(grade, 'mentions')} "
            f"| {_mark(grade, 'grounded')} | {_mark(grade, 'disclaimer')} "
            f"| {_mark(grade, 'refusal')} | {'pass' if grade.passed else 'fail'} |"
        )
        lines.append(row)
    failures = [grade for grade in grades if not grade.passed]
    if failures:
        lines.extend(["", "## Failures", ""])
        for grade in failures:
            lines.append(f"### {grade.case_id}")
            lines.append("")
            for check in grade.checks:
                if not check.passed:
                    lines.append(f"- {check.name}: {check.detail}")
            if grade.draft:
                lines.extend(["", "Draft:", "", "```markdown", grade.draft, "```", ""])
            else:
                lines.append("")
    lines.append("")
    lines.append(f"Standard disclaimer the draft must contain: {DISCLAIMER}")
    lines.append("")
    return "\n".join(lines)


def write_report(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _paused(result: dict[str, Any]) -> tuple[str, list[tuple[str, dict[str, object]]]]:
    interrupts = result.get("__interrupt__") or []
    if not interrupts:
        raise ValueError("the run did not stop with a draft")
    payload = interrupts[0].value
    draft = payload.get("draft", "") if isinstance(payload, dict) else ""
    if not isinstance(draft, str):
        draft = ""
    return draft, _tool_calls(result.get("messages") or [])


def _tools(case: EvalCase) -> list[Any]:
    @tool
    def top_reactions(drug: str, limit: int = 10) -> str:
        """Count MedDRA terms for one drug."""

        return json.dumps(case.top_reactions)

    @tool
    def search_adverse_events(
        drug: str,
        reaction: str | None = None,
        serious_only: bool = False,
        limit: int = 5,
    ) -> str:
        """List compact FAERS reports for one drug."""

        return json.dumps(case.search)

    @tool
    def get_label_section(drug: str, section: str) -> str:
        """Read one label section."""

        return case.label_payload(section)

    return [top_reactions, search_adverse_events, get_label_section]


def _tool_calls(messages: list[Any]) -> list[tuple[str, dict[str, object]]]:
    found: list[tuple[str, dict[str, object]]] = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            name = call.get("name")
            args = call.get("args") or {}
            if isinstance(name, str) and isinstance(args, dict):
                found.append((name, args))
    return found


def _mark(grade: Grade, name: str) -> str:
    for check in grade.checks:
        if check.name == name:
            return "pass" if check.passed else "fail"
    return "—"
