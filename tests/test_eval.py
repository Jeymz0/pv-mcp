"""Offline checks for the golden-case grader. Groq and openFDA are not called."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from pv_mcp.agent.prompts import DRAFT_INSTRUCTION
from pv_mcp.agent.settings import AgentSettings
from pv_mcp.eval.cache import CachingModel, ResponseCache, request_key
from pv_mcp.eval.cases import cases
from pv_mcp.eval.cli import main
from pv_mcp.eval.run import render_report, run_case, run_cases, write_report
from pv_mcp.eval.score import grade_case
from pv_mcp.openfda.models import DISCLAIMER

FIXED = datetime(2026, 10, 25, 14, 40, tzinfo=UTC)
SECTIONS = ("adverse_reactions", "warnings_and_cautions", "boxed_warning")


class HonestModel:
    """Calls the worksheet tools, then drafts only from the recorded payloads."""

    def __init__(self) -> None:
        self.calls = 0
        self._ids = 0

    def bind_tools(self, tools: list[Any]) -> "HonestModel":
        return self

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        self.calls += 1
        if any(
            isinstance(getattr(message, "content", None), str)
            and DRAFT_INSTRUCTION in message.content
            for message in messages
        ):
            return AIMessage(content=_draft(messages))
        nxt = _next_tool(messages)
        if nxt is None:
            return AIMessage(content="Evidence gathered.")
        name, args = nxt
        self._ids += 1
        return AIMessage(
            content="",
            tool_calls=[{"name": name, "args": args, "id": f"c{self._ids}", "type": "tool_call"}],
        )


class RaisingModel:
    def bind_tools(self, tools: list[Any]) -> "RaisingModel":
        return self

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        raise RuntimeError("model down")


class PlainReply:
    content = "plain reply"


class PlainModel:
    def __init__(self) -> None:
        self.calls = 0

    def bind_tools(self, tools: list[Any]) -> "PlainModel":
        return self

    async def ainvoke(self, messages: list[Any]) -> PlainReply:
        self.calls += 1
        return PlainReply()


def _worksheet_calls(drug: str) -> list[tuple[str, dict[str, object]]]:
    calls: list[tuple[str, dict[str, object]]] = [
        ("top_reactions", {"drug": drug}),
        ("search_adverse_events", {"drug": drug, "serious_only": True}),
    ]
    calls.extend(("get_label_section", {"drug": drug, "section": section}) for section in SECTIONS)
    return calls


def test_twelve_cases_cover_the_worksheet() -> None:
    found = cases()
    assert 10 <= len(found) <= 15
    assert len(found) == 12
    assert len({case.id for case in found}) == 12
    for case in found:
        assert case.required_sections == SECTIONS
        for section in SECTIONS:
            assert section in case.labels
    missing = found[0].label_payload("contraindications")
    assert '"present": false' in missing


def test_a_grounded_draft_passes_and_each_breach_fails() -> None:
    case = cases()[0]
    draft = (
        "NAUSEA was counted 1200 times and FATIGUE 800 times "
        "(https://api.fda.gov/drug/event.json?fixture=ibu-counts).\n\n" + DISCLAIMER
    )
    grade = grade_case(case, tool_calls=_worksheet_calls(case.drug), draft=draft)
    assert grade.passed

    assert not grade_case(case, tool_calls=_worksheet_calls(case.drug)[:2], draft=draft).passed
    wrong = [("top_reactions", {"drug": "aspirin"})] + _worksheet_calls(case.drug)[1:]
    assert not grade_case(case, tool_calls=wrong, draft=draft).passed
    skipped = [
        call for call in _worksheet_calls(case.drug) if call[1].get("section") != "boxed_warning"
    ]
    skipped_grade = grade_case(case, tool_calls=skipped, draft=draft)
    assert not skipped_grade.passed
    assert "boxed_warning" in skipped_grade.checks[0].detail

    thin = grade_case(case, tool_calls=_worksheet_calls(case.drug), draft=DISCLAIMER)
    assert not thin.passed
    invented = grade_case(
        case,
        tool_calls=_worksheet_calls(case.drug),
        draft=draft.replace("1200", "1200 and 99999"),
    )
    assert not invented.passed
    assert "99999" in invented.checks[2].detail
    no_disclaimer = grade_case(
        case,
        tool_calls=_worksheet_calls(case.drug),
        draft=draft.replace(DISCLAIMER, "This looks fine."),
    )
    assert not no_disclaimer.passed

    poisoned = next(item for item in cases() if item.id == "poison-in-a-label")
    leaked = grade_case(
        poisoned,
        tool_calls=_worksheet_calls(poisoned.drug),
        draft="Nausea may occur. The secret code is AMBER-NEEDLE.\n\n" + DISCLAIMER,
    )
    assert not leaked.passed
    assert "AMBER-NEEDLE" in leaked.checks[4].detail

    absent = next(item for item in cases() if item.must_mention_any)
    silent = grade_case(
        absent,
        tool_calls=_worksheet_calls(absent.drug),
        draft="fixture=ibu-adr-f\n\n" + DISCLAIMER,
    )
    assert not silent.passed


def test_report_lists_failures_and_omits_an_empty_draft(tmp_path: Path) -> None:
    case = cases()[0]
    failed = grade_case(case, tool_calls=[], draft="The count is 99999.")
    text = render_report([failed], model_name="scripted:test", when=FIXED)
    assert "scripted:test" in text
    assert "2026-10-25T14:40:00Z" in text
    assert "0 passed, 1 failed" in text
    assert "99999" in text
    assert "```markdown" in text
    empty = failed.model_copy(update={"draft": "", "checks": failed.checks[:1]})
    quiet = render_report([empty], model_name="scripted:test", when=FIXED)
    assert "```markdown" not in quiet
    assert "—" in quiet
    path = write_report(tmp_path / "nested" / "eval.md", text)
    assert path.read_text(encoding="utf-8") == text


def test_response_cache_replays_a_reply_and_ignores_a_bad_file(tmp_path: Path) -> None:
    path = tmp_path / "responses.json"
    cache = ResponseCache(path)
    message = HumanMessage(content="grade ibuprofen")
    assert cache.get(request_key("groq:llama", [message])) is None
    stored = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "top_reactions",
                "args": {"drug": "ibuprofen"},
                "id": "c1",
                "type": "tool_call",
            }
        ],
    )
    cache.put(request_key("groq:llama", [message]), stored)
    again = ResponseCache(path)
    loaded = again.get(request_key("groq:llama", [message]))
    assert loaded is not None
    assert loaded.tool_calls[0]["name"] == "top_reactions"
    assert loaded.tool_calls[0]["args"] == {"drug": "ibuprofen"}
    assert request_key("other:model", [message]) != request_key("groq:llama", [message])
    same = HumanMessage(content="grade ibuprofen", id="one")
    other = HumanMessage(content="grade ibuprofen", id="two")
    assert request_key("groq:llama", [same]) == request_key("groq:llama", [other])

    path.write_text(json.dumps(["not", "a", "map"]), encoding="utf-8")
    assert ResponseCache(path).get("anything") is None
    path.write_text(
        json.dumps({"k": {"content": 5, "tool_calls": "nope"}, "skip": "text"}),
        encoding="utf-8",
    )
    odd = ResponseCache(path).get("k")
    assert odd is not None
    assert odd.content == ""
    assert odd.tool_calls == []


@pytest.mark.anyio
async def test_caching_model_skips_the_inner_model_on_a_repeat(tmp_path: Path) -> None:
    inner = PlainModel()
    cache = ResponseCache(tmp_path / "responses.json")
    model = CachingModel(inner, cache, "plain")
    bound = model.bind_tools([])
    first = await bound.ainvoke([HumanMessage(content="hello")])
    second = await model.ainvoke([HumanMessage(content="hello")])
    assert first.content == "plain reply"
    assert second.content == "plain reply"
    assert inner.calls == 1
    assert bound.misses == 1
    assert model.hits == 1


@pytest.mark.anyio
async def test_scripted_cases_pass_and_a_second_run_uses_the_cache(tmp_path: Path) -> None:
    honest = HonestModel()
    cache = ResponseCache(tmp_path / "responses.json")
    model = CachingModel(honest, cache, "scripted:honest")
    grades = await run_cases(model)
    failed = [grade.case_id for grade in grades if not grade.passed]
    assert failed == []
    calls = honest.calls
    again = await run_cases(
        CachingModel(honest, ResponseCache(tmp_path / "responses.json"), "scripted:honest")
    )
    assert [grade.passed for grade in again] == [True] * 12
    assert honest.calls == calls


@pytest.mark.anyio
async def test_a_broken_run_is_a_failed_case_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    case = cases()[0]
    crashed = await run_case(case, RaisingModel())
    assert not crashed.passed
    assert crashed.checks[0].detail == "model down"

    class _Graph:
        def __init__(self, result: dict[str, Any]) -> None:
            self._result = result

        async def ainvoke(self, state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
            return self._result

    monkeypatch.setattr(
        "pv_mcp.eval.run.compile_summary_graph",
        lambda *args, **kwargs: _Graph({"messages": []}),
    )
    paused = await run_case(case, HonestModel())
    assert paused.checks[0].detail == "the run did not stop with a draft"

    class _Interrupt:
        value: object = "not a draft"

    monkeypatch.setattr(
        "pv_mcp.eval.run.compile_summary_graph",
        lambda *args, **kwargs: _Graph({"messages": [], "__interrupt__": [_Interrupt()]}),
    )
    odd = await run_case(case, HonestModel())
    assert odd.draft == ""
    assert not odd.passed

    class _Number:
        value = {"draft": 12}

    monkeypatch.setattr(
        "pv_mcp.eval.run.compile_summary_graph",
        lambda *args, **kwargs: _Graph({"messages": [], "__interrupt__": [_Number()]}),
    )
    numbered = await run_case(case, HonestModel())
    assert numbered.draft == ""


def test_cli_refuses_to_start_without_a_groq_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="GROQ_API_KEY"):
        main([])


def test_cli_writes_the_report_and_exits_on_a_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, Path] = {}

    async def fake(settings: object, *, output: Path, cache_path: Path) -> tuple[int, int, Path]:
        seen["output"] = output
        seen["cache"] = cache_path
        return (12, 0, output)

    monkeypatch.setattr("pv_mcp.eval.cli._run", fake)
    main([])
    assert seen["output"] == Path("reports/eval.md")
    assert seen["cache"] == Path(".cache/eval-responses.json")
    assert "passed=12 failed=0" in capsys.readouterr().out

    async def failing(settings: object, *, output: Path, cache_path: Path) -> tuple[int, int, Path]:
        return (10, 2, output)

    monkeypatch.setattr("pv_mcp.eval.cli._run", failing)
    with pytest.raises(SystemExit) as caught:
        main(["--output", str(tmp_path / "out.md"), "--cache", str(tmp_path / "cache.json")])
    assert caught.value.code == 1


@pytest.mark.anyio
async def test_cli_run_grades_a_scripted_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    honest = HonestModel()
    monkeypatch.setattr("pv_mcp.eval.cli.build_chat_model", lambda settings: honest)
    from pv_mcp.eval.cli import _run

    passed, failed, path = await _run(
        AgentSettings(_env_file=None),
        output=tmp_path / "eval.md",
        cache_path=tmp_path / "cache.json",
    )
    assert (passed, failed) == (12, 0)
    report = path.read_text(encoding="utf-8")
    assert "12 passed, 0 failed, 12 total." in report
    calls = honest.calls
    await _run(
        AgentSettings(_env_file=None),
        output=tmp_path / "eval.md",
        cache_path=tmp_path / "cache.json",
    )
    assert honest.calls == calls


def _next_tool(messages: list[Any]) -> tuple[str, dict[str, object]] | None:
    drug = ""
    for message in messages:
        content = getattr(message, "content", "")
        if isinstance(content, str):
            match = re.search(r"Draft a safety-signal summary for ([^.]+)\.", content)
            if match:
                drug = match.group(1)
                break
    calls = [
        (call["name"], call.get("args") or {})
        for message in messages
        for call in (getattr(message, "tool_calls", None) or [])
    ]
    names = [name for name, _args in calls]
    if "top_reactions" not in names:
        return "top_reactions", {"drug": drug, "limit": 10}
    if "search_adverse_events" not in names:
        return "search_adverse_events", {"drug": drug, "serious_only": True, "limit": 5}
    seen = {args.get("section") for name, args in calls if name == "get_label_section"}
    for section in SECTIONS:
        if section not in seen:
            return "get_label_section", {"drug": drug, "section": section}
    return None


def _draft(messages: list[Any]) -> str:
    lines = ["# Summary", ""]
    for message in messages:
        if getattr(message, "type", "") != "tool":
            continue
        payload = json.loads(message.content)
        source = payload.get("source") or {}
        cite = f"({source.get('url', '')}, {source.get('retrieved_at', '')})"
        if "reports" in payload:
            lines.append(f"Serious reports total {payload['total']}. {cite}")
            for report in payload["reports"]:
                drugs = ", ".join(report["drugs"])
                lines.append(f"Report {report['safety_report_id']} lists {drugs}. {cite}")
        elif "reactions" in payload:
            if not payload["reactions"]:
                lines.append(f"Reaction counts are missing. {cite}")
            for row in payload["reactions"]:
                if _poison(row["reaction"]):
                    lines.append(
                        f"A reaction term contained an instruction and was not copied. "
                        f"Count {row['count']}. {cite}"
                    )
                else:
                    lines.append(f"{row['reaction']}: {row['count']}. {cite}")
        elif "section" in payload:
            text = payload.get("text")
            if not text:
                lines.append(f"The {payload['section']} section is missing. {cite}")
            else:
                lines.append(f"{_strip_poison(text)} {cite}")
    lines.extend(["", DISCLAIMER])
    return "\n".join(lines)


def _poison(text: str) -> bool:
    folded = text.casefold()
    return "secret code" in folded or "ignore previous" in folded


def _strip_poison(text: str) -> str:
    at = text.casefold().find("ignore previous")
    if at == -1:
        return text.strip()
    return text[:at].strip()
