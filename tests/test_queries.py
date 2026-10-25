"""Search strings stay quoted, so a drug name cannot add an openFDA operator."""

from datetime import date

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from pv_mcp.openfda.queries import event_search, label_search, quote_phrase, require_name


def test_drug_name_is_quoted_in_every_field() -> None:
    search = event_search(
        drug="co-amoxiclav",
        reaction=None,
        serious_only=False,
        date_from=None,
        date_to=None,
        today=date(2026, 10, 25),
    )
    assert 'patient.drug.openfda.generic_name:"co-amoxiclav"' in search
    assert 'patient.drug.medicinalproduct:"co-amoxiclav"' in search
    assert " AND " not in search


def test_filters_join_with_and() -> None:
    search = event_search(
        drug="ibuprofen",
        reaction="nausea",
        serious_only=True,
        date_from=date(2024, 1, 1),
        date_to=date(2024, 1, 31),
        today=date(2026, 10, 25),
    )
    assert search.endswith("serious:1 AND receivedate:[20240101 TO 20240131]")
    assert 'patient.reaction.reactionmeddrapt:"nausea"' in search


def test_open_ended_date_uses_today() -> None:
    search = event_search(
        drug="ibuprofen",
        reaction=None,
        serious_only=False,
        date_from=date(2024, 5, 1),
        date_to=None,
        today=date(2026, 10, 25),
    )
    assert "receivedate:[20240501 TO 20261025]" in search


def test_inverted_dates_are_rejected() -> None:
    with pytest.raises(ToolError, match="date_from"):
        event_search(
            drug="ibuprofen",
            reaction=None,
            serious_only=False,
            date_from=date(2024, 2, 1),
            date_to=date(2024, 1, 1),
            today=date(2026, 10, 25),
        )


def test_query_syntax_in_a_name_is_rejected() -> None:
    with pytest.raises(ToolError, match="characters"):
        require_name('ibuprofen" OR serious:1', what="drug")


def test_label_search_quotes_the_drug() -> None:
    assert label_search("Advil") == (
        '(openfda.generic_name:"Advil" openfda.brand_name:"Advil" openfda.substance_name:"Advil")'
    )


def test_quote_phrase_escapes_embedded_quotes() -> None:
    assert quote_phrase('a"b') == '"a\\"b"'
