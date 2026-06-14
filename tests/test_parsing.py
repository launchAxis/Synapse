from synapse.tournament import parse_judgment
from synapse.utils import parse_labeled_field


def test_parse_markdown_labeled_critique_field():
    text = """
**Main weakness:** The idea is too dependent on a central server.

**Risk:** Schools with unreliable internet may lose key functionality.

**Missing element:** A teacher-controlled offline workflow.

**Unclear assumption:** Every device can run the same AI features.

**Suggested improvement:** Add local-first content sync and teacher override tools.
"""

    assert parse_labeled_field(text, "Main weakness") == "The idea is too dependent on a central server."
    assert parse_labeled_field(text, "Risk") == "Schools with unreliable internet may lose key functionality."
    assert parse_labeled_field(text, "Suggested improvement") == "Add local-first content sync and teacher override tools."


def test_parse_uppercase_labeled_critique_field():
    text = """
MAIN_WEAKNESS: Too dependent on one school server.
RISK: Outages could stop classroom use.
MISSING_ELEMENT: A fallback teacher workflow.
UNCLEAR_ASSUMPTION: All schools can maintain the server.
SUGGESTED_IMPROVEMENT: Add peer-to-peer sync and paper export.
"""

    assert parse_labeled_field(text, "MAIN_WEAKNESS") == "Too dependent on one school server."
    assert parse_labeled_field(text, "MISSING_ELEMENT") == "A fallback teacher workflow."


def test_parse_tournament_judgment():
    assert parse_judgment("WINNER: B\nREASON: clearer plan") == ("B", "clearer plan")


def test_parse_markdown_wrapped_tournament_judgment():
    assert parse_judgment("**WINNER:** **A**\n**REASON:** clearer plan")[0] == "A"


def test_unclear_tournament_judgment_is_invalid():
    assert parse_judgment("Idea B seems stronger because it is clearer.")[0] is None
