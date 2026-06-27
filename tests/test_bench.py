import json
from dataclasses import dataclass
from pathlib import Path

from synapse.bench.judge import grade_completion, judge_pair, judge_prompt, parse_judge_response, parse_rubric_response
from synapse.bench.loaders import load_config, load_suite
from synapse.bench.ollama_client import OllamaBenchClient, is_retryable_provider_error
from synapse.bench.report import blinded_answers, pairwise_rows, summary_markdown, write_jsonl, write_outputs
from synapse.bench.runner import collect_completions, run_benchmark, should_cache_rubric_score, system_pairs
from synapse.bench.schema import BenchmarkConfig, CompletionRecord, JudgeConfig, PairwiseJudgment, PromptCase, RubricScore, SystemConfig
from synapse.bench.stats import wilson_interval, win_rate
from synapse.bench.systems import run_system
from synapse.bench.cache import DiskCache
from synapse.bench.verdict import build_benchmark_verdict


def test_bench_loaders_read_json_compatible_yaml():
    config = load_config("configs/benchmark.default.yaml")
    suite = load_suite("benchmarks/synapse_smoke.yaml")

    assert config.systems[0].id == "synapse_full"
    assert config.judge.model
    assert config.judge.models
    assert config.judge.retry_attempts >= 0
    assert config.judge.min_request_interval_s >= 0
    assert config.rubric_grading
    assert suite[0].id == "I01"


def test_pairwise_stats_include_ties():
    assert win_rate(1, 1, 2) == 0.5
    low, high = wilson_interval(5, 10)
    assert 0 < low < high < 1


def test_system_pairs_can_use_baseline_only_or_round_robin():
    systems = ["candidate", "previous", "single"]

    assert system_pairs(systems, "single", True) == [("candidate", "single"), ("previous", "single")]
    assert system_pairs(systems, None, False) == [
        ("candidate", "previous"),
        ("candidate", "single"),
        ("previous", "single"),
    ]
    assert system_pairs(systems, None, True, [["candidate", "single"]]) == [("candidate", "single")]


def test_parse_judge_response_handles_tie():
    winner, reason = parse_judge_response("FINAL_WINNER: tie\nREASON: both are similarly useful")

    assert winner == "tie"
    assert "similarly" in reason


def test_judge_prompt_discourages_position_bias_and_close_wins():
    prompt = judge_prompt("User task", "Answer one", "Answer two")

    assert "Do not choose Answer A or Answer B by default" in prompt
    assert "If the answers are close" in prompt
    assert "choose tie" in prompt
    assert "material quality difference" in prompt


def test_parse_rubric_response_clamps_scores():
    parsed = parse_rubric_response(
        "TASK_FULFILLMENT: 12\nCORRECTNESS: 8\nUSEFULNESS: 7\nSTRUCTURE: 6\nCONSTRAINT_HANDLING: 5\nINSIGHT: 4\nRATIONALE: useful"
    )

    assert parsed["TASK_FULFILLMENT"] == 10
    assert parsed["CORRECTNESS"] == 8
    assert parsed["RATIONALE"] == "useful"


def test_invalid_rubric_response_does_not_silently_score_zero():
    case = PromptCase(id="P1", title="Prompt", category="x", difficulty="easy", prompt="Hello")
    completion = CompletionRecord("run", "system", "P1", 1, "Answer", 0.1)
    score = grade_completion("run", case, 1, completion, JudgeConfig(model="judge"), _InvalidRubricClient())

    assert not score.valid
    assert score.score is None
    assert score.raw_response == "not a rubric"
    assert score.error


def test_valid_rubric_response_produces_weighted_score():
    case = PromptCase(id="P1", title="Prompt", category="x", difficulty="easy", prompt="Hello")
    completion = CompletionRecord("run", "system", "P1", 1, "Answer", 0.1)
    score = grade_completion("run", case, 1, completion, JudgeConfig(model="judge"), _ValidRubricClient())

    assert score.valid
    assert score.score == 76.5
    assert score.error is None


def test_rubric_cache_policy_keeps_only_successful_scores():
    valid_score = _rubric("system", "P1", 80)
    invalid_score = _rubric("system", "P2", None, valid=False)
    errored_score = _rubric("system", "P3", 80)
    errored_score.error = "HTTP 429: tokens per day limit reached"

    assert should_cache_rubric_score(valid_score)
    assert not should_cache_rubric_score(invalid_score)
    assert not should_cache_rubric_score(errored_score)


def test_daily_token_quota_error_is_not_retryable():
    error = 'groq request failed: HTTP 429: {"error":{"message":"Rate limit reached for model in organization on tokens per day (TPD): Limit 100000"}}'

    assert not is_retryable_provider_error(error)


def test_transient_rate_limit_error_remains_retryable():
    assert is_retryable_provider_error("HTTP 429: rate limit reached; please retry in 2s")


def test_benchmark_files_exist():
    assert Path("configs/benchmark.default.yaml").exists()
    assert Path("configs/benchmark.strong-judge.yaml").exists()
    assert Path("benchmarks/synapse_smoke.yaml").exists()


@dataclass
class _JsonlRecord:
    name: str
    score: int


def test_write_jsonl_serializes_dataclass_records(tmp_path):
    path = tmp_path / "records.jsonl"

    write_jsonl(path, [_JsonlRecord("alpha", 1)])

    assert json.loads(path.read_text(encoding="utf-8")) == {"name": "alpha", "score": 1}


def test_write_jsonl_serializes_dict_records(tmp_path):
    path = tmp_path / "records.jsonl"

    write_jsonl(path, [{"name": "beta", "score": 2}])

    assert json.loads(path.read_text(encoding="utf-8")) == {"name": "beta", "score": 2}


def test_write_jsonl_serializes_mixed_records(tmp_path):
    path = tmp_path / "records.jsonl"

    write_jsonl(path, [_JsonlRecord("alpha", 1), {"name": "beta", "score": 2}, "plain"])

    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert lines == [{"name": "alpha", "score": 1}, {"name": "beta", "score": 2}, "plain"]


def test_write_jsonl_handles_empty_list(tmp_path):
    path = tmp_path / "records.jsonl"

    write_jsonl(path, [])

    assert path.read_text(encoding="utf-8") == ""


def test_summary_markdown_counts_dict_fallback_scores():
    systems = [
        SystemConfig(id="candidate", kind="x", label="Candidate"),
        SystemConfig(id="baseline", kind="x", label="Baseline"),
    ]
    completions = [
        CompletionRecord("run", "candidate", "P1", 1, "Candidate", 0.1),
        CompletionRecord("run", "baseline", "P1", 1, "Baseline", 0.1),
    ]
    judgment = PairwiseJudgment(
        run_id="run",
        prompt_id="P1",
        seed=1,
        system_a="candidate",
        system_b="baseline",
        final_winner="tie",
        confidence=0.5,
        rationale="tie",
        unstable_order=True,
        raw_orders=[],
        category="x",
        difficulty="easy",
        rubric_fallback_scores=[{"valid": False}, _rubric("candidate", "P1", 80)],
    )

    summary = summary_markdown(systems, completions, [judgment], [])

    assert "Rubric fallback score records: 2" in summary
    assert "Invalid rubric fallback scores: 1" in summary


def test_ollama_single_receives_seed_option():
    class FakeClient:
        def __init__(self):
            self.options = None

        def chat(self, model, prompt, system_prompt="", options=None):
            self.options = options
            return "answer", 0.01, {}

    client = FakeClient()
    system = SystemConfig(id="single", kind="ollama_single", label="Single", model="model-a")
    case = PromptCase(id="P1", title="Prompt", category="x", difficulty="easy", prompt="Hello")

    record = run_system("run", system, case, seed=42, ollama_client=client)

    assert record.error is None
    assert client.options["seed"] == 42


def test_judge_receives_seed_option():
    class FakeClient:
        def __init__(self):
            self.options = []

        def chat(self, model, prompt, system_prompt="", options=None):
            self.options.append(options)
            return "WINNER: A\nREASON: clearer", 0.01, {}

    client = FakeClient()
    case = PromptCase(id="P1", title="Prompt", category="x", difficulty="easy", prompt="Hello")
    left = CompletionRecord("run", "left", "P1", 7, "A text", 0.1)
    right = CompletionRecord("run", "right", "P1", 7, "B text", 0.1)

    judgment = judge_pair("run", case, 7, left, right, JudgeConfig(model="judge"), client)

    assert judgment.error is None
    assert all("seed" in item for item in client.options)


def test_daily_token_quota_error_does_not_retry_provider_call():
    class QuotaRouter:
        def __init__(self):
            self.calls = 0

        def chat(self, model_ref, prompt, system_prompt="", options=None):
            from synapse.providers import ProviderResponse

            self.calls += 1
            return ProviderResponse(
                ok=False,
                text="",
                error='groq request failed: HTTP 429: {"error":{"message":"Rate limit reached for tokens per day (TPD): Limit 100000"}}',
            )

    sleeps = []
    router = QuotaRouter()
    client = OllamaBenchClient(router=router, retry_attempts=4, sleep_fn=sleeps.append)

    try:
        client.chat("groq:llama-3.3-70b-versatile", "Hello")
    except RuntimeError as exc:
        assert "tokens per day" in str(exc).lower()
    else:
        raise AssertionError("quota errors should fail without retrying")

    assert router.calls == 1
    assert sleeps == []

def test_provider_ref_benchmark_judge_call_works_with_mocked_router():
    class FakeRouter:
        def __init__(self):
            self.models = []

        def chat(self, model_ref, prompt, system_prompt="", options=None):
            from synapse.providers import ProviderResponse

            self.models.append(model_ref)
            return ProviderResponse(ok=True, text="FINAL_WINNER: A\nREASON: clearer", latency_s=0.01)

    router = FakeRouter()
    client = OllamaBenchClient(router=router)
    case = PromptCase(id="P1", title="Prompt", category="x", difficulty="easy", prompt="Hello")
    left = CompletionRecord("run", "left", "P1", 7, "A text", 0.1)
    right = CompletionRecord("run", "right", "P1", 7, "B text", 0.1)

    judgment = judge_pair("run", case, 7, left, right, JudgeConfig(model="openai:gpt-test"), client)

    assert judgment.error is None
    assert router.models == ["openai:gpt-test", "openai:gpt-test"]


def test_human_review_sheet_is_blinded(tmp_path):
    systems = [
        SystemConfig(id="synapse", kind="synapse_python", label="Synapse"),
        SystemConfig(id="single", kind="ollama_single", label="Single"),
    ]
    completions = [
        CompletionRecord("run", "synapse", "P1", 1, "Candidate answer", 0.1, metadata={"prompt": "Prompt text"}),
        CompletionRecord("run", "single", "P1", 1, "Single answer", 0.1, metadata={"prompt": "Prompt text"}),
    ]
    case = PromptCase(id="P1", title="Prompt", category="x", difficulty="easy", prompt="Prompt text")
    judgment = judge_pair("run", case, 1, completions[0], completions[1], JudgeConfig(model="judge"), _AlwaysTieClient())

    write_outputs(tmp_path, systems, completions, [judgment], [])

    sheet = (tmp_path / "human_review_sheet.csv").read_text(encoding="utf-8")
    key = (tmp_path / "human_review_key.csv").read_text(encoding="utf-8")
    assert "Prompt text" in sheet
    assert "Candidate answer" in sheet
    assert "Single answer" in sheet
    assert "auto_winner" not in sheet
    assert "synapse" not in sheet.lower()
    assert "auto_winner" in key


def test_human_review_sheet_can_randomize_answer_order(tmp_path):
    systems = [
        SystemConfig(id="synapse_full", kind="synapse_python", label="Synapse"),
        SystemConfig(id="single_best_local", kind="ollama_single", label="Single"),
    ]
    completions = [
        CompletionRecord("run", "synapse_full", "P2", 1, "Synapse answer", 0.1, metadata={"prompt": "Prompt text"}),
        CompletionRecord("run", "single_best_local", "P2", 1, "Single answer", 0.1, metadata={"prompt": "Prompt text"}),
    ]
    case = PromptCase(id="P2", title="Prompt", category="x", difficulty="easy", prompt="Prompt text")
    judgment = judge_pair("run", case, 1, completions[0], completions[1], JudgeConfig(model="judge"), _AlwaysTieClient())

    write_outputs(tmp_path, systems, completions, [judgment], [])

    key = (tmp_path / "human_review_key.csv").read_text(encoding="utf-8")
    assert "answer_a_system" in key
    assert "answer_b_system" in key
    assert ("single_best_local,synapse_full" in key) or ("synapse_full,single_best_local" in key)


def test_blinded_answers_reverses_some_review_items():
    left = CompletionRecord("run", "synapse_full", "P1", 1, "Synapse answer", 0.1)
    right = CompletionRecord("run", "single_best_local", "P1", 1, "Single answer", 0.1)
    reversed_seen = False
    for seed in range(1, 20):
        judgment = judge_pair(
            "run",
            PromptCase(id=f"P{seed}", title="Prompt", category="x", difficulty="easy", prompt="Prompt"),
            seed,
            left,
            right,
            JudgeConfig(model="judge"),
            _AlwaysTieClient(),
        )
        _answer_a, _answer_b, answer_a_system, _answer_b_system = blinded_answers(judgment, left, right)
        reversed_seen = reversed_seen or answer_a_system == "single_best_local"

    assert reversed_seen


class _AlwaysTieClient:
    def chat(self, model, prompt, system_prompt="", options=None):
        return "WINNER: tie\nREASON: tie", 0.01, {}


def test_biased_judge_marks_summary_unstable_and_inconclusive():
    case = PromptCase(id="P1", title="Prompt", category="x", difficulty="easy", prompt="Hello")
    left = CompletionRecord("run", "left", "P1", 1, "Left answer", 0.1)
    right = CompletionRecord("run", "right", "P1", 1, "Right answer", 0.1)
    judgment = judge_pair("run", case, 1, left, right, JudgeConfig(model="judge"), _AlwaysAClient())

    summary = summary_markdown(
        [SystemConfig(id="left", kind="x", label="Left"), SystemConfig(id="right", kind="x", label="Right")],
        [left, right],
        [judgment],
        [],
    )

    assert judgment.unstable_order
    assert judgment.final_winner == "tie"
    assert "Judge unreliable for this pair; do not interpret win rate." in summary
    assert "Mark this run as inconclusive" in summary
    assert "Visible Answer A choices: 2" in summary
    assert "Position-bias warning: visible Answer A received 2/2 non-tie raw judge choices." in summary
    assert "**Run verdict:** `inconclusive`" in summary


def test_visible_position_bias_awards_no_pairwise_win():
    case = PromptCase(id="P1", title="Prompt", category="x", difficulty="easy", prompt="Hello")
    left = CompletionRecord("run", "left", "P1", 1, "Left answer", 0.1)
    right = CompletionRecord("run", "right", "P1", 1, "Right answer", 0.1)

    judgment = judge_pair("run", case, 1, left, right, JudgeConfig(model="judge"), _AlwaysBClient())
    row = pairwise_rows([judgment])[0]

    assert judgment.unstable_order
    assert judgment.final_winner == "tie"
    assert row["wins"] == 0
    assert row["losses"] == 0
    assert row["ties"] == 1
    assert row["unstable_order_rate"] == "1.000"


def test_rubric_fallback_is_diagnostic_for_unstable_pairwise():
    case = PromptCase(id="P1", title="Prompt", category="x", difficulty="easy", prompt="Hello")
    left = CompletionRecord("run", "left", "P1", 1, "Left answer", 0.1)
    right = CompletionRecord("run", "right", "P1", 1, "Right answer", 0.1)

    judgment = judge_pair(
        "run",
        case,
        1,
        left,
        right,
        JudgeConfig(model="judge"),
        _BiasedValidRubricClient(),
        use_rubric_fallback=True,
    )
    summary = summary_markdown(
        [SystemConfig(id="left", kind="x", label="Left"), SystemConfig(id="right", kind="x", label="Right")],
        [left, right],
        [judgment],
        [],
    )

    assert judgment.unstable_order
    assert judgment.used_rubric_fallback
    assert judgment.final_winner == "tie"
    assert "No pairwise win awarded" in judgment.rubric_fallback_note
    assert all(score.valid for score in judgment.rubric_fallback_scores)
    assert pairwise_rows([judgment])[0]["ties"] == 1
    assert "Rubric fallback is diagnostic only; unstable pairwise comparisons still award no pairwise win." in summary


class _AlwaysAClient:
    def chat(self, model, prompt, system_prompt="", options=None):
        return "A_STRENGTHS: ok\nA_WEAKNESSES: none\nB_STRENGTHS: ok\nB_WEAKNESSES: none\nFINAL_WINNER: A\nREASON: biased", 0.01, {}


class _AlwaysBClient:
    def chat(self, model, prompt, system_prompt="", options=None):
        return "A_STRENGTHS: ok\nA_WEAKNESSES: none\nB_STRENGTHS: ok\nB_WEAKNESSES: none\nFINAL_WINNER: B\nREASON: biased", 0.01, {}


class _BiasedValidRubricClient:
    def chat(self, model, prompt, system_prompt="", options=None):
        if "Grade one answer" in prompt:
            if "Right answer" in prompt:
                return (
                    "TASK_FULFILLMENT: 9\n"
                    "CORRECTNESS: 9\n"
                    "USEFULNESS: 9\n"
                    "STRUCTURE: 9\n"
                    "CONSTRAINT_HANDLING: 9\n"
                    "INSIGHT: 9\n"
                    "RATIONALE: stronger"
                ), 0.01, {}
            return (
                "TASK_FULFILLMENT: 6\n"
                "CORRECTNESS: 6\n"
                "USEFULNESS: 6\n"
                "STRUCTURE: 6\n"
                "CONSTRAINT_HANDLING: 6\n"
                "INSIGHT: 6\n"
                "RATIONALE: weaker"
            ), 0.01, {}
        return "A_STRENGTHS: ok\nA_WEAKNESSES: none\nB_STRENGTHS: ok\nB_WEAKNESSES: none\nFINAL_WINNER: A\nREASON: biased", 0.01, {}


class _InvalidRubricClient:
    def chat(self, model, prompt, system_prompt="", options=None):
        return "not a rubric", 0.01, {}


class _ValidRubricClient:
    def chat(self, model, prompt, system_prompt="", options=None):
        return (
            "TASK_FULFILLMENT: 8\n"
            "CORRECTNESS: 7\n"
            "USEFULNESS: 8\n"
            "STRUCTURE: 7\n"
            "CONSTRAINT_HANDLING: 8\n"
            "INSIGHT: 8\n"
            "RATIONALE: useful"
        ), 0.01, {}


def test_fallback_cannot_override_when_rubric_parsing_fails():
    case = PromptCase(id="P1", title="Prompt", category="x", difficulty="easy", prompt="Hello")
    left = CompletionRecord("run", "left", "P1", 1, "Left answer", 0.1)
    right = CompletionRecord("run", "right", "P1", 1, "Right answer", 0.1)
    judgment = judge_pair(
        "run",
        case,
        1,
        left,
        right,
        JudgeConfig(model="judge"),
        _BiasedInvalidRubricClient(),
        use_rubric_fallback=True,
    )

    assert judgment.unstable_order
    assert not judgment.used_rubric_fallback
    assert judgment.final_winner == "tie"
    assert judgment.rubric_fallback_scores
    assert all(not score.valid for score in judgment.rubric_fallback_scores)


class _BiasedInvalidRubricClient:
    def chat(self, model, prompt, system_prompt="", options=None):
        if "Grade one answer" in prompt:
            return "not a rubric", 0.01, {}
        return "A_STRENGTHS: ok\nA_WEAKNESSES: none\nB_STRENGTHS: ok\nB_WEAKNESSES: none\nFINAL_WINNER: A\nREASON: biased", 0.01, {}


def test_verdict_uses_valid_rubric_scores_and_excludes_invalid_scores():
    systems = [
        SystemConfig(id="synapse_full", kind="synapse_python", label="Synapse"),
        SystemConfig(id="single_best_local", kind="ollama_single", label="Single"),
    ]
    completions = [
        CompletionRecord("run", "synapse_full", f"P{i}", 1, "Synapse answer", 0.1)
        for i in range(1, 5)
    ] + [
        CompletionRecord("run", "single_best_local", f"P{i}", 1, "Single answer", 0.1)
        for i in range(1, 5)
    ]
    judgments = [
        judge_pair(
            "run",
            PromptCase(id=f"P{i}", title="Prompt", category="x", difficulty="easy", prompt="Prompt"),
            i,
            completions[i - 1],
            completions[i + 3],
            JudgeConfig(model="judge"),
            _AlwaysAClient(),
        )
        for i in range(1, 5)
    ]
    scores = [
        _rubric("synapse_full", "P1", 80),
        _rubric("synapse_full", "P2", 82),
        _rubric("synapse_full", "P3", 84),
        _rubric("synapse_full", "P4", None, valid=False),
        _rubric("single_best_local", "P1", 70),
        _rubric("single_best_local", "P2", 72),
        _rubric("single_best_local", "P3", 74),
        _rubric("single_best_local", "P4", None, valid=False),
    ]

    verdict = build_benchmark_verdict(systems, completions, judgments, scores)

    assert verdict.verdict == "credible"
    assert verdict.comparisons[0].verdict == "credible_win"
    assert verdict.comparisons[0].evidence == "rubric"
    assert verdict.comparisons[0].valid_rubric_scores == {"synapse_full": 3, "single_best_local": 3}
    assert verdict.rubric_summaries[0].invalid_scores == 1


def test_verdict_marks_close_rubric_scores_as_mixed():
    systems = [
        SystemConfig(id="candidate", kind="x", label="Candidate"),
        SystemConfig(id="baseline", kind="x", label="Baseline"),
    ]
    completions = [
        CompletionRecord("run", "candidate", f"P{i}", 1, "Candidate", 0.1)
        for i in range(1, 4)
    ] + [
        CompletionRecord("run", "baseline", f"P{i}", 1, "Baseline", 0.1)
        for i in range(1, 4)
    ]
    judgments = [
        judge_pair(
            "run",
            PromptCase(id=f"P{i}", title="Prompt", category="x", difficulty="easy", prompt="Prompt"),
            i,
            completions[i - 1],
            completions[i + 2],
            JudgeConfig(model="judge"),
            _AlwaysTieClient(),
        )
        for i in range(1, 4)
    ]
    scores = [
        _rubric("candidate", "P1", 75),
        _rubric("candidate", "P2", 76),
        _rubric("candidate", "P3", 77),
        _rubric("baseline", "P1", 73),
        _rubric("baseline", "P2", 74),
        _rubric("baseline", "P3", 75),
    ]

    verdict = build_benchmark_verdict(systems, completions, judgments, scores)

    assert verdict.verdict == "mixed"
    assert verdict.comparisons[0].verdict == "mixed"


def test_write_outputs_writes_benchmark_verdict_json(tmp_path):
    systems = [
        SystemConfig(id="synapse_full", kind="synapse_python", label="Synapse"),
        SystemConfig(id="single_best_local", kind="ollama_single", label="Single"),
    ]
    completions = [
        CompletionRecord("run", "synapse_full", "P1", 1, "Synapse answer", 0.1, metadata={"prompt": "Prompt"}),
        CompletionRecord("run", "single_best_local", "P1", 1, "Single answer", 0.1, metadata={"prompt": "Prompt"}),
    ]
    judgment = judge_pair(
        "run",
        PromptCase(id="P1", title="Prompt", category="x", difficulty="easy", prompt="Prompt"),
        1,
        completions[0],
        completions[1],
        JudgeConfig(model="judge"),
        _AlwaysAClient(),
    )

    write_outputs(tmp_path, systems, completions, [judgment], [])

    verdict_json = (tmp_path / "benchmark_verdict.json").read_text(encoding="utf-8")
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert '"verdict": "inconclusive"' in verdict_json
    assert "## Benchmark Verdict" in summary


def _rubric(system_id: str, prompt_id: str, score: float | None, valid: bool = True) -> RubricScore:
    return RubricScore(
        run_id="run",
        prompt_id=prompt_id,
        seed=1,
        system_id=system_id,
        score=score,
        task_fulfillment=8 if valid else None,
        correctness=8 if valid else None,
        usefulness=8 if valid else None,
        structure=8 if valid else None,
        constraint_handling=8 if valid else None,
        insight=8 if valid else None,
        rationale="ok",
        valid=valid,
        error=None if valid else "bad parse",
    )


def test_failed_completions_are_not_cached(tmp_path):
    config = BenchmarkConfig(
        run_name="fail-cache",
        seeds=[1],
        systems=[SystemConfig(id="bad", kind="unknown", label="Bad")],
        judge=JudgeConfig(model="judge"),
        cache_dir=str(tmp_path / "cache"),
    )
    suite = [PromptCase(id="P1", title="Prompt", category="x", difficulty="easy", prompt="Hello")]
    cache = DiskCache(config.cache_dir)

    records = collect_completions("run", config, suite, cache, no_cache=False)

    assert records[0].error
    assert not list((tmp_path / "cache").rglob("*.json"))


def test_run_benchmark_fails_when_all_completions_fail(tmp_path):
    config_path = tmp_path / "config.yaml"
    suite_path = tmp_path / "suite.yaml"
    config_path.write_text(
        '{"run_name":"fail","output_dir":"' + str(tmp_path / "runs").replace("\\", "\\\\") + '","cache_dir":"' + str(tmp_path / "cache").replace("\\", "\\\\") + '","seeds":[1],"judge":{"model":"judge"},"systems":[{"id":"bad","kind":"unknown","label":"Bad"}]}',
        encoding="utf-8",
    )
    suite_path.write_text(
        '{"prompts":[{"id":"P1","title":"Prompt","category":"x","difficulty":"easy","prompt":"Hello"}]}',
        encoding="utf-8",
    )

    try:
        run_benchmark(str(config_path), str(suite_path))
    except RuntimeError as exc:
        assert "all completions failed" in str(exc)
    else:
        raise AssertionError("run_benchmark should fail when all completions fail")

