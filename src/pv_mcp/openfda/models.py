"""Structured tool results. Every result carries its source and a disclaimer."""

from enum import StrEnum

from pydantic import BaseModel, Field

DISCLAIMER = (
    "FAERS reports do not establish that a drug caused a reaction. "
    "Counts are not incidence rates. This is not medical advice."
)


class LabelSectionName(StrEnum):
    """SPL sections this server will read from an openFDA drug label."""

    boxed_warning = "boxed_warning"
    warnings_and_cautions = "warnings_and_cautions"
    adverse_reactions = "adverse_reactions"
    contraindications = "contraindications"
    indications_and_usage = "indications_and_usage"


class SourceReference(BaseModel):
    """The openFDA request behind a result. The URL never contains an API key."""

    endpoint: str = Field(description="openFDA path, for example /drug/event.json.")
    query: str = Field(description="Value of the search parameter sent to openFDA.")
    url: str = Field(description="Full request URL with the API key removed.")
    retrieved_at: str = Field(description="UTC time the response was read, ISO-8601.")


class AdverseEventReport(BaseModel):
    """A compact FAERS report. Narratives and patient demographics are omitted."""

    safety_report_id: str | None
    receive_date: str | None = Field(description="Receive date as YYYY-MM-DD when known.")
    serious: bool | None
    reactions: list[str]
    drugs: list[str] = Field(
        description="Medicinal product names as reported. Not a causality list."
    )


class AdverseEventSearchResult(BaseModel):
    """Matching FAERS reports for one drug search."""

    drug: str
    total: int = Field(description="openFDA total for the query, which can exceed len(reports).")
    reports: list[AdverseEventReport]
    source: SourceReference
    disclaimer: str


class ReactionCount(BaseModel):
    """How many matching reports list one MedDRA reaction term."""

    reaction: str
    count: int


class TopReactionsResult(BaseModel):
    """Most frequently reported reaction terms for one drug."""

    drug: str
    reactions: list[ReactionCount]
    source: SourceReference
    disclaimer: str


class LabelSectionResult(BaseModel):
    """One section of one matching drug label, truncated when it is long."""

    drug: str
    section: LabelSectionName
    label_field: str = Field(
        description="openFDA field that was read. May be 'warnings' when "
        "warnings_and_cautions is absent on that label."
    )
    present: bool
    text: str | None
    truncated: bool
    brand_names: list[str]
    generic_names: list[str]
    source: SourceReference
    disclaimer: str
