"""Build openFDA search strings. User text is quoted so it cannot add operators."""

from datetime import date

from mcp.server.mcpserver.exceptions import ToolError

_ALLOWED = set(" .'()/%&,-_")
_MAX_NAME_LENGTH = 200

EVENT_DRUG_FIELDS = (
    "patient.drug.openfda.generic_name",
    "patient.drug.openfda.brand_name",
    "patient.drug.openfda.substance_name",
    "patient.drug.medicinalproduct",
)
LABEL_DRUG_FIELDS = (
    "openfda.generic_name",
    "openfda.brand_name",
    "openfda.substance_name",
)
REACTION_COUNT_FIELD = "patient.reaction.reactionmeddrapt.exact"


def require_name(value: str, *, what: str) -> str:
    """Accept a plain drug or reaction name and reject query syntax."""

    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > _MAX_NAME_LENGTH:
        raise ToolError(f"{what} must be 1 to {_MAX_NAME_LENGTH} characters.")
    if any(not (character.isalnum() or character in _ALLOWED) for character in cleaned):
        raise ToolError(f"{what} contains characters that cannot be sent to openFDA.")
    return cleaned


def quote_phrase(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def any_field(fields: tuple[str, ...], value: str) -> str:
    """OR across fields. openFDA treats a space between clauses as OR."""

    phrase = quote_phrase(value)
    return "(" + " ".join(f"{field}:{phrase}" for field in fields) + ")"


def receivedate_clause(start: date | None, end: date | None, *, today: date) -> str | None:
    if start is None and end is None:
        return None
    if start is not None and end is not None and start > end:
        raise ToolError("date_from must be on or before date_to.")
    left = (start or date(1900, 1, 1)).strftime("%Y%m%d")
    right = (end or today).strftime("%Y%m%d")
    return f"receivedate:[{left} TO {right}]"


def event_search(
    *,
    drug: str,
    reaction: str | None,
    serious_only: bool,
    date_from: date | None,
    date_to: date | None,
    today: date,
) -> str:
    parts = [any_field(EVENT_DRUG_FIELDS, drug)]
    if reaction:
        parts.append(f"patient.reaction.reactionmeddrapt:{quote_phrase(reaction)}")
    if serious_only:
        parts.append("serious:1")
    received = receivedate_clause(date_from, date_to, today=today)
    if received:
        parts.append(received)
    return " AND ".join(parts)


def label_search(drug: str) -> str:
    return any_field(LABEL_DRUG_FIELDS, drug)
