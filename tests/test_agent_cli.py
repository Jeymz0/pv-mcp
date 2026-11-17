"""The CLI prints a draft, then saves an approval, without calling a live model."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from pv_mcp.agent.cli import main, open_graph, run_draft, run_resume
from pv_mcp.agent.graph import ReviewDecision, compile_summary_graph
from pv_mcp.agent.model import build_chat_model
from pv_mcp.agent.settings import AgentSettings
from pv_mcp.openfda.models import DISCLAIMER
from tests.test_agent_graph import TOOLS, ScriptedModel, _gathering_script


def test_groq_refuses_to_start_without_a_key() -> None:
    settings = AgentSettings(_env_file=None, groq_api_key=None, pv_agent_model_provider="groq")
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        build_chat_model(settings)


def test_a_provider_name_is_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    def fake(model: str, *, model_provider: str, **_kwargs: object) -> ScriptedModel:
        seen["model"] = model
        seen["provider"] = model_provider
        return ScriptedModel([])

    monkeypatch.setattr("pv_mcp.agent.model.init_chat_model", fake)
    settings = AgentSettings(
        _env_file=None,
        pv_agent_model="demo-model",
        pv_agent_model_provider="other",
    )
    build_chat_model(settings)
    assert seen == {"model": "demo-model", "provider": "other"}


def test_draft_command_prints_the_thread(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake(_settings: AgentSettings, drug: str) -> tuple[str, str]:
        assert drug == "ibuprofen"
        return "abc", "Draft body"

    monkeypatch.setattr("pv_mcp.agent.cli.run_draft", fake)
    monkeypatch.setattr(
        "pv_mcp.agent.cli.AgentSettings",
        lambda: AgentSettings(_env_file=None),
    )
    main(["draft", "ibuprofen"])
    output = capsys.readouterr().out
    assert "Draft body" in output
    assert "thread_id=abc" in output


def test_empty_drug_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pv_mcp.agent.cli.AgentSettings",
        lambda: AgentSettings(_env_file=None),
    )
    with pytest.raises(SystemExit, match="drug must not be empty"):
        main(["draft", "  "])


@pytest.mark.anyio
async def test_resume_saves_an_edited_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedModel(_gathering_script("Original."))
    graph = compile_summary_graph(
        model,
        TOOLS,
        checkpointer=InMemorySaver(),
        reports_dir=tmp_path,
        clock=lambda: datetime(2026, 10, 25, 13, 40, tzinfo=UTC),
    )

    @asynccontextmanager
    async def fake_open(_settings: AgentSettings) -> AsyncIterator[object]:
        yield graph

    monkeypatch.setattr("pv_mcp.agent.cli.open_graph", fake_open)
    settings = AgentSettings(_env_file=None, pv_agent_reports_dir=tmp_path)
    thread_id, draft = await run_draft(settings, "ibuprofen")
    assert draft == "Original."
    edited = tmp_path / "edit.md"
    edited.write_text("Kept by the reviewer.\n", encoding="utf-8")
    path = await run_resume(
        settings,
        thread_id,
        ReviewDecision(action="edit", markdown=edited.read_text(encoding="utf-8")),
    )
    text = Path(path).read_text(encoding="utf-8")
    assert "Kept by the reviewer." in text
    assert DISCLAIMER in text
    paused = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    assert paused.values["approved"]


def test_resume_command_rejects_an_empty_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "pv_mcp.agent.cli.AgentSettings",
        lambda: AgentSettings(_env_file=None),
    )
    empty = tmp_path / "empty.md"
    empty.write_text("  \n", encoding="utf-8")
    with pytest.raises(SystemExit, match="empty"):
        main(["resume", "thread", "--file", str(empty)])


@pytest.mark.anyio
async def test_open_graph_loads_the_live_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pv_mcp.agent.cli.build_chat_model", lambda _settings: ScriptedModel([]))
    captured: dict[str, set[str]] = {}

    def fake_compile(_model: object, tools: list[object], **_kwargs: object) -> str:
        captured["tools"] = {tool.name for tool in tools}  # type: ignore[attr-defined]
        return "compiled"

    monkeypatch.setattr("pv_mcp.agent.cli.compile_summary_graph", fake_compile)
    settings = AgentSettings(
        _env_file=None,
        pv_agent_transport="stdio",
        pv_agent_model_provider="other",
        pv_agent_checkpoint_path=tmp_path / "agent.sqlite",
        pv_agent_reports_dir=tmp_path / "reports",
    )
    async with open_graph(settings) as graph:
        assert graph == "compiled"
    assert captured["tools"] == {
        "search_adverse_events",
        "top_reactions",
        "get_label_section",
    }
