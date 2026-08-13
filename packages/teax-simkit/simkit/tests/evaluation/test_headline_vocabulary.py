"""The runtime's half of the fail-closed obligation, pinned at every seam that can break it.

CONSTRAINT-SEMANTICS Item 3 renamed `all_satisfied` to `full_satisfaction` *on purpose*: state 3's
meaning strengthened from "nothing failed" to "everything was checked and passed", and a token whose
meaning changes under a reader is a silent misread. The rename only buys anything if every reader
refuses the retired token by name instead of defaulting.

There are exactly three runtime seams where a headline token is looked up, and all three were bare
subscripts before this item:

1. `canonical_headline` — the projection seam (`evaluation/projection.py`)
2. `_HEADLINE_DISPOSITION` — `ObjectivePolicy`'s dispatch table, the real study path
3. `_DISPOSITION_BY_HEADLINE` — `DispositionPolicy`'s dispatch table

Each is tested here against the retired token *and* an invented one. Without these, a future
refactor that reinstates a bare subscript or a `.get(token, default)` goes green — and a
`.get(..., "satisfied")` is precisely the failure the rename exists to prevent.

`UnknownHeadlineToken` is deliberately not an `AssessmentFailed`: a token the runtime cannot map
means the runtime does not understand the package, which must stop the run rather than record a
per-case policy failure that looks healthy in the store. That distinction is asserted too.
"""

from __future__ import annotations

import pytest

from simkit.evaluation.evidence import (
    CANONICAL_HEADLINE,
    UnknownHeadlineToken,
    canonical_headline,
)
from simkit.study.policy import (
    _DISPOSITION_BY_HEADLINE,
    _HEADLINE_DISPOSITION,
    AssessmentFailed,
    _disposition_for,
)

#: The token this item retired, and one nobody has ever defined. Both must refuse identically:
#: the first is the realistic case (a package built before the item), the second proves the
#: refusal is a closed-vocabulary rule and not a special case for one string.
UNKNOWN_TOKENS = ["all_satisfied", "invented_token"]


# ---------------------------------------------------------------------------
# The token map itself
# ---------------------------------------------------------------------------


def test_every_report_token_maps_to_exactly_one_canonical_token():
    assert set(CANONICAL_HEADLINE) == {
        "violation",
        "indeterminate",
        "full_satisfaction",
        "partial_coverage",
        "not_assessed",
    }
    # Injective: two report tokens collapsing onto one canonical token would make a state
    # unrecoverable on the runtime side.
    assert len(set(CANONICAL_HEADLINE.values())) == len(CANONICAL_HEADLINE)


# ---------------------------------------------------------------------------
# Seam 1 — the projection seam
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", UNKNOWN_TOKENS)
def test_the_projection_seam_refuses_an_unmapped_token_by_name(token):
    with pytest.raises(UnknownHeadlineToken) as raised:
        canonical_headline(token)
    message = str(raised.value)
    assert token in message
    # The message must tell the reader which side is stale; a bare KeyError did not.
    assert "regenerate" in message and "update the runtime" in message


@pytest.mark.parametrize("token", UNKNOWN_TOKENS)
def test_the_projection_seam_never_returns_a_satisfied_reading(token):
    """The failure mode the rename exists to prevent, stated as the property.

    A reader that defaulted — `CANONICAL_HEADLINE.get(token, "satisfied")` — would turn a
    package it cannot understand into a feasible candidate. This asserts no value comes back
    at all.
    """
    with pytest.raises(UnknownHeadlineToken):
        result = canonical_headline(token)
        pytest.fail(f"returned {result!r} instead of refusing")


# ---------------------------------------------------------------------------
# Seams 2 and 3 — both dispatch tables
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "table,name",
    [
        (_HEADLINE_DISPOSITION, "_HEADLINE_DISPOSITION"),
        (_DISPOSITION_BY_HEADLINE, "_DISPOSITION_BY_HEADLINE"),
    ],
)
@pytest.mark.parametrize("token", UNKNOWN_TOKENS)
def test_both_dispatch_tables_refuse_an_untaught_headline_by_name(table, name, token):
    with pytest.raises(UnknownHeadlineToken) as raised:
        _disposition_for(token, table, name)
    message = str(raised.value)
    assert name in message and token in message
    assert "has not been taught" in message or "no disposition for" in message


@pytest.mark.parametrize(
    "table", [_HEADLINE_DISPOSITION, _DISPOSITION_BY_HEADLINE], ids=["objective", "disposition"]
)
def test_partial_coverage_is_taught_to_both_tables(table):
    """The state the item added must exist in both, or one policy silently cannot see it."""
    assert "partial_coverage" in table


def test_an_unknown_token_is_not_an_assessment_failure():
    """It must stop the run, not become a per-case record that looks healthy in the store."""
    with pytest.raises(UnknownHeadlineToken) as raised:
        canonical_headline("all_satisfied")
    assert not isinstance(raised.value, AssessmentFailed)
