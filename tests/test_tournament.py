from synapse.ideas import Idea
from synapse.tournament import eligible_judges, rank_ideas, run_pairwise_tournament


class FakeResponse:
    def __init__(self, text: str = "", ok: bool = True, error: str = ""):
        self.ok = ok
        self.text = text
        self.error = error


class StableLeftManager:
    def ask(self, model, prompt):
        if "Idea A (L)" in prompt:
            return FakeResponse("WINNER: Idea A\nREASON: L is stronger.")
        if "Idea B (L)" in prompt:
            return FakeResponse("WINNER: Idea B\nREASON: L is stronger.")
        return FakeResponse("WINNER: Idea A\nREASON: fallback.")


class AlwaysVisibleAManager:
    def ask(self, model, prompt):
        return FakeResponse("WINNER: Idea A\nREASON: visible A looked better.")


def test_rank_ideas_prefers_more_wins_then_fewer_losses_then_id():
    idea_b = Idea(id="B", text="B", author_model="test")
    idea_a = Idea(id="A", text="A", author_model="test")
    idea_c = Idea(id="C", text="C", author_model="test")

    idea_a.wins = 2
    idea_a.losses = 1
    idea_b.wins = 2
    idea_b.losses = 0
    idea_c.wins = 1
    idea_c.losses = 0

    assert [idea.id for idea in rank_ideas([idea_a, idea_b, idea_c])] == ["B", "A", "C"]


def test_rank_ideas_tie_uses_stable_id_order():
    idea_b = Idea(id="B", text="B", author_model="test")
    idea_a = Idea(id="A", text="A", author_model="test")

    assert [idea.id for idea in rank_ideas([idea_b, idea_a])] == ["A", "B"]


def test_eligible_judges_avoid_authors_when_alternatives_exist():
    idea_a = Idea(id="A", text="A", author_model="model-a")
    idea_b = Idea(id="B", text="B", author_model="model-b")

    judges = eligible_judges(
        idea_a,
        idea_b,
        {"A": "model-a", "B": "model-b", "C": "model-c"},
    )

    assert judges == [("C", "model-c")]


def test_eligible_judges_fall_back_when_no_alternative_exists():
    idea_a = Idea(id="A", text="A", author_model="model-a")
    idea_b = Idea(id="B", text="B", author_model="model-b")

    judges = eligible_judges(idea_a, idea_b, {"A": "model-a", "B": "model-b"})

    assert judges == [("A", "model-a"), ("B", "model-b")]


def test_symmetric_tournament_awards_win_when_mapped_winner_is_stable():
    left = Idea(id="L", text="Left idea", author_model="model-left")
    right = Idea(id="R", text="Right idea", author_model="model-right")

    ranked, comparisons = run_pairwise_tournament(
        "Prompt",
        [right, left],
        {"J": "model-judge"},
        StableLeftManager(),
    )

    assert len(comparisons) == 1
    assert comparisons[0].valid
    assert comparisons[0].stable
    assert comparisons[0].winner_id == "L"
    assert comparisons[0].first_winner_id == "L"
    assert comparisons[0].second_winner_id == "L"
    assert left.wins == 1
    assert right.losses == 1
    assert [idea.id for idea in ranked] == ["L", "R"]


def test_visible_position_bias_becomes_unstable_with_no_win_awarded():
    left = Idea(id="L", text="Left idea", author_model="model-left")
    right = Idea(id="R", text="Right idea", author_model="model-right")

    ranked, comparisons = run_pairwise_tournament(
        "Prompt",
        [left, right],
        {"J": "model-judge"},
        AlwaysVisibleAManager(),
    )

    assert len(comparisons) == 1
    assert comparisons[0].valid
    assert not comparisons[0].stable
    assert comparisons[0].winner_id == ""
    assert comparisons[0].first_winner_id == "L"
    assert comparisons[0].second_winner_id == "R"
    assert left.wins == 0
    assert right.wins == 0
    assert left.losses == 0
    assert right.losses == 0
    assert [idea.id for idea in ranked] == ["L", "R"]


def test_unstable_comparisons_do_not_distort_existing_rank_order():
    idea_c = Idea(id="C", text="C", author_model="model-c")
    idea_a = Idea(id="A", text="A", author_model="model-a")
    idea_b = Idea(id="B", text="B", author_model="model-b")

    ranked, comparisons = run_pairwise_tournament(
        "Prompt",
        [idea_c, idea_b, idea_a],
        {"J": "model-judge"},
        AlwaysVisibleAManager(),
    )

    assert all(item.valid and not item.stable for item in comparisons)
    assert all(idea.wins == 0 and idea.losses == 0 for idea in [idea_a, idea_b, idea_c])
    assert [idea.id for idea in ranked] == ["A", "B", "C"]
