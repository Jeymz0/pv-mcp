"""Turn openFDA JSON into compact models. Unknown shapes become a tool error."""

from mcp.server.mcpserver.exceptions import ToolError

from pv_mcp.openfda.models import (
    DISCLAIMER,
    AdverseEventReport,
    AdverseEventSearchResult,
    LabelSectionName,
    LabelSectionResult,
    ReactionCount,
    SourceReference,
    TopReactionsResult,
)

_MAX_TERMS = 8
_MAX_NAME_LIST = 5
_WARNINGS_FALLBACK = "warnings"


def parse_event_search(
    payload: dict[str, object] | None,
    *,
    drug: str,
    source: SourceReference,
) -> AdverseEventSearchResult:
    if payload is None:
        return AdverseEventSearchResult(
            drug=drug, total=0, reports=[], source=source, disclaimer=DISCLAIMER
        )
    rows = _result_rows(payload, what="event")
    return AdverseEventSearchResult(
        drug=drug,
        total=_total(payload, fallback=len(rows)),
        reports=[_compact_report(row) for row in rows],
        source=source,
        disclaimer=DISCLAIMER,
    )


def parse_reaction_counts(
    payload: dict[str, object] | None,
    *,
    drug: str,
    limit: int,
    source: SourceReference,
) -> TopReactionsResult:
    if payload is None:
        reactions: list[ReactionCount] = []
    else:
        reactions = []
        for row in _result_rows(payload, what="count"):
            term = _short(row.get("term"), limit=300)
            count = row.get("count")
            if term is None or not isinstance(count, int):
                continue
            reactions.append(ReactionCount(reaction=term, count=count))
            if len(reactions) >= limit:
                break
    return TopReactionsResult(drug=drug, reactions=reactions, source=source, disclaimer=DISCLAIMER)


def parse_label_section(
    payload: dict[str, object] | None,
    *,
    drug: str,
    section: LabelSectionName,
    max_chars: int,
    source: SourceReference,
) -> LabelSectionResult:
    empty = LabelSectionResult(
        drug=drug,
        section=section,
        label_field=section.value,
        present=False,
        text=None,
        truncated=False,
        brand_names=[],
        generic_names=[],
        source=source,
        disclaimer=DISCLAIMER,
    )
    if payload is None:
        return empty
    rows = _result_rows(payload, what="label")
    if not rows:
        return empty
    record = rows[0]
    text, field = _section_text(record, section.value)
    truncated = False
    if text is not None and len(text) > max_chars:
        text = text[:max_chars]
        truncated = True
    openfda = record.get("openfda")
    names = openfda if isinstance(openfda, dict) else {}
    return LabelSectionResult(
        drug=drug,
        section=section,
        label_field=field,
        present=text is not None,
        text=text,
        truncated=truncated,
        brand_names=_name_list(names.get("brand_name")),
        generic_names=_name_list(names.get("generic_name")),
        source=source,
        disclaimer=DISCLAIMER,
    )


def _section_text(record: dict[str, object], section: str) -> tuple[str | None, str]:
    text = _join_text(record.get(section))
    if text is not None:
        return text, section
    if section == "warnings_and_cautions":
        fallback = _join_text(record.get(_WARNINGS_FALLBACK))
        if fallback is not None:
            return fallback, _WARNINGS_FALLBACK
    return None, section


def _compact_report(row: dict[str, object]) -> AdverseEventReport:
    patient = row.get("patient")
    patient_record = patient if isinstance(patient, dict) else {}
    return AdverseEventReport(
        safety_report_id=_short(row.get("safetyreportid"), limit=64),
        receive_date=_receive_date(row.get("receivedate")),
        serious=_serious(row.get("serious")),
        reactions=_named_terms(patient_record.get("reaction"), "reactionmeddrapt"),
        drugs=_named_terms(patient_record.get("drug"), "medicinalproduct"),
    )


def _named_terms(value: object, key: str) -> list[str]:
    if not isinstance(value, list):
        return []
    terms: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        term = _short(item.get(key), limit=200)
        if term is not None and term not in terms:
            terms.append(term)
        if len(terms) >= _MAX_TERMS:
            break
    return terms


def _name_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        term = _short(item, limit=200)
        if term is not None and term not in names:
            names.append(term)
        if len(names) >= _MAX_NAME_LIST:
            break
    return names


def _join_text(value: object) -> str | None:
    if isinstance(value, str):
        parts = [value]
    elif isinstance(value, list):
        parts = [item for item in value if isinstance(item, str)]
    else:
        return None
    text = "\n\n".join(part.strip() for part in parts if part.strip())
    return text or None


def _result_rows(payload: dict[str, object], *, what: str) -> list[dict[str, object]]:
    rows = payload.get("results")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise ToolError(f"openFDA returned an unexpected {what} payload.")
    return [row for row in rows if isinstance(row, dict)]


def _total(payload: dict[str, object], *, fallback: int) -> int:
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return fallback
    results = meta.get("results")
    if not isinstance(results, dict):
        return fallback
    total = results.get("total")
    if isinstance(total, int) and total >= 0:
        return total
    return fallback


def _short(value: object, *, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text:
        return None
    return text[:limit]


def _receive_date(value: object) -> str | None:
    if not isinstance(value, str) or len(value) != 8 or not value.isdigit():
        return None
    return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"


def _serious(value: object) -> bool | None:
    if value in {"1", 1}:
        return True
    if value in {"2", 2}:
        return False
    return None
