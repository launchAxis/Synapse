from synapse.ideas import Idea
from synapse.tournament import rank_ideas


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
