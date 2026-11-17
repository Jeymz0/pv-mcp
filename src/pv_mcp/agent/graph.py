"""Plan, call the pharmacovigilance tools, draft, then stop for a person."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from pv_mcp.agent.prompts import DRAFT_INSTRUCTION, opening_messages
from pv_mcp.agent.report import ensure_disclaimer, write_report

MAX_TOOL_ROUNDS = 6


class ReviewDecision(BaseModel):
    """What the person sends back when the draft is waiting."""

    action: Literal["approve", "edit"]
    markdown: str | None = Field(
        default=None,
        description="Replacement Markdown. Required when action is edit.",
    )


class SummaryState(TypedDict):
    """One drug, the conversation, and the text a person has accepted."""

    drug: str
    messages: Annotated[list[Any], add_messages]
    draft: str
    approved: str
    report_path: str
    tool_rounds: int


def initial_state(drug: str) -> SummaryState:
    """Start a thread. The model has the limits and the worksheet, and no evidence yet."""

    return {
        "drug": drug,
        "messages": opening_messages(drug),
        "draft": "",
        "approved": "",
        "report_path": "",
        "tool_rounds": 0,
    }


def message_text(message: AIMessage) -> str:
    """Flatten a chat response to the Markdown the reviewer will read."""

    content = message.content
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts).strip()


def compile_summary_graph(
    model: Any,
    tools: list[Any],
    *,
    checkpointer: Any,
    reports_dir: Path,
    clock: Any = None,
) -> Any:
    """Graph that gathers evidence, drafts once, and interrupts before saving.

    Tool calls are not interrupted. The only pause is the finished Markdown.
    ``clock`` defaults to the current UTC time and exists so tests can pin a filename.
    """

    now = clock if clock is not None else _utc_now
    bound = model.bind_tools(tools)

    async def plan(state: SummaryState) -> dict[str, Any]:
        rounds = state["tool_rounds"]
        active = bound if rounds < MAX_TOOL_ROUNDS else model
        response = await active.ainvoke(state["messages"])
        calls = getattr(response, "tool_calls", None) or []
        return {
            "messages": [response],
            "tool_rounds": rounds + (1 if calls else 0),
        }

    def route(state: SummaryState) -> Literal["tools", "draft"]:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return "draft"

    async def draft(state: SummaryState) -> dict[str, Any]:
        instruction = HumanMessage(content=DRAFT_INSTRUCTION)
        response = await model.ainvoke([*state["messages"], instruction])
        if not isinstance(response, AIMessage):
            response = AIMessage(content=message_text(response))
        text = message_text(response)
        if not text:
            raise ValueError("The model returned an empty draft.")
        return {"draft": text, "messages": [instruction, response]}

    def review(state: SummaryState) -> dict[str, str]:
        decision = interrupt(
            {"drug": state["drug"], "draft": state["draft"]},
            response_schema=ReviewDecision,
        )
        if not isinstance(decision, ReviewDecision):
            decision = ReviewDecision.model_validate(decision)
        if decision.action == "edit":
            if decision.markdown is None or not decision.markdown.strip():
                raise ValueError("An edited report needs markdown.")
            chosen = decision.markdown
        else:
            chosen = state["draft"]
        return {"approved": ensure_disclaimer(chosen).strip()}

    def save(state: SummaryState) -> dict[str, str]:
        path = write_report(
            reports_dir,
            drug=state["drug"],
            body=state["approved"],
            now=now(),
        )
        return {"report_path": str(path)}

    graph = StateGraph(SummaryState)
    graph.add_node("plan", plan)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("draft", draft)
    graph.add_node("review", review)
    graph.add_node("save", save)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", route, {"tools": "tools", "draft": "draft"})
    graph.add_edge("tools", "plan")
    graph.add_edge("draft", "review")
    graph.add_edge("review", "save")
    graph.add_edge("save", END)
    return graph.compile(checkpointer=checkpointer)


def _utc_now() -> datetime:
    return datetime.now(UTC)
