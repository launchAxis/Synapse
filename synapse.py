from __future__ import annotations

import json
import re
import statistics
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

import ollama


# =========================
# CONFIG
# =========================

MODELS: Dict[str, str] = {
    "1": "qwen2.5:3b",
    "2": "gemma2:2b",
    "3": "llama3.2:3b"
}

# Number of evolutionary rounds before stopping by stagnation or max rounds.
MAX_ROUNDS = 4

# Keep this small for consumer hardware. Set to True if you want more concurrency.
USE_PARALLEL = True
MAX_WORKERS = 3

# Selection behavior
TOP_K_SURVIVORS = 2
OUTLIER_STD_THRESHOLD = 1.25  # more aggressive = lower number
MIN_SCORE_TO_SURVIVE = 7.0

# Final presentation rounds
FINAL_PRESENTATION_CANDIDATES = 3
FINAL_PRESENTATION_REFINEMENT_ROUNDS = 1

# Memory
USE_MEMORY = False
MEMORY_PATH = Path("ai_council_memory.json")

# Graph export
EXPORT_MERMAID = False
MERMAID_PATH = Path("idea_evolution.mmd")

# Prompt adaptation
ADAPT_PROMPTS = True

# Optional: if one model is consistently the best critic, you can weight its vote a bit more.
USE_CRITIC_WEIGHTS = True
CRITIC_WEIGHT_MIN = 0.8
CRITIC_WEIGHT_MAX = 1.2

# =========================
# DATA MODELS
# =========================


@dataclass
class Idea:
    id: str
    text: str
    origin: str
    generation: int = 0
    parent_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CritiqueResult:
    critic_id: str
    idea_id: str
    score: float
    reason: str
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    raw: str = ""


@dataclass
class RoundResult:
    round_index: int
    ideas_before: Dict[str, Idea]
    critiques: List[CritiqueResult]
    scores: Dict[str, float]
    survivors: Dict[str, Idea]
    eliminated: Dict[str, Idea]
    improved: Dict[str, Idea]
    hybrid: Optional[Idea]


# =========================
# UTILITIES
# =========================


def safe_json_loads(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except Exception:
        # Try to recover from fenced JSON or surrounding text.
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
    return None


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def extract_score_fallback(text: str) -> float:
    m = re.search(r"(?:score\s*[:=]?\s*)(\d+(?:\.\d+)?)", text, flags=re.I)
    if m:
        return float(m.group(1))
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if nums:
        return float(nums[0])
    return 5.0


def compact(text: str, limit: int = 600) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def now_tag() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# =========================
# MEMORY
# =========================


class SessionMemory:
    def __init__(self, enabled: bool, path: Path):
        self.enabled = enabled
        self.path = path
        self.data = self.load() if enabled else {}

    def load(self) -> dict:
        if not self.path.exists():
            return {
                "runs": [],
                "critic_strengths": {k: [] for k in MODELS},
                "critic_weights": {k: 1.0 for k in MODELS},
                "prompt_notes": [],
            }
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {
                "runs": [],
                "critic_strengths": {k: [] for k in MODELS},
                "critic_weights": {k: 1.0 for k in MODELS},
                "prompt_notes": [],
            }

    def save(self) -> None:
        if not self.enabled:
            return
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def append_run(self, run_summary: dict) -> None:
        if not self.enabled:
            return
        self.data.setdefault("runs", []).append(run_summary)
        self.save()

    def note_critic_performance(self, critic_id: str, score: float) -> None:
        if not self.enabled:
            return
        self.data.setdefault("critic_strengths", {}).setdefault(critic_id, []).append(score)
        scores = self.data["critic_strengths"][critic_id]
        avg = statistics.mean(scores[-10:]) if scores else 1.0
        # Normalize to 0.8-1.2 range for gentle weighting.
        self.data.setdefault("critic_weights", {})[critic_id] = clamp(0.8 + (avg / 10.0) * 0.4, 0.8, 1.2)
        self.save()

    def critic_weight(self, critic_id: str) -> float:
        if not self.enabled:
            return 1.0
        return float(self.data.get("critic_weights", {}).get(critic_id, 1.0))

    def add_prompt_note(self, note: str) -> None:
        if not self.enabled:
            return
        self.data.setdefault("prompt_notes", []).append(note)
        self.save()

    def recent_prompt_notes(self, n: int = 5) -> List[str]:
        return self.data.get("prompt_notes", [])[-n:] if self.enabled else []


# =========================
# GRAPH EXPORT
# =========================


class EvolutionGraph:
    def __init__(self):
        self.lines: List[str] = ["flowchart TD"]
        self.nodes_seen: set[str] = set()

    def add_node(self, node_id: str, label: str) -> None:
        safe_label = label.replace('"', "'").replace("\n", " ")
        if node_id in self.nodes_seen:
            return
        self.nodes_seen.add(node_id)
        self.lines.append(f'    {node_id}["{safe_label}"]')

    def add_edge(self, src: str, dst: str) -> None:
        self.lines.append(f"    {src} --> {dst}")

    def save(self, path: Path) -> None:
        path.write_text("\n".join(self.lines), encoding="utf-8")


# =========================
# LLM CALLS
# =========================


def ask_model(model: str, prompt: str, system: Optional[str] = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = ollama.chat(model=model, messages=messages)
    return resp["message"]["content"]


def ask_json(model: str, prompt: str, system: Optional[str] = None) -> dict:
    raw = ask_model(model, prompt, system=system)
    parsed = safe_json_loads(raw)
    if parsed is None:
        return {"raw": raw}
    parsed["raw"] = raw
    return parsed


# =========================
# PROMPTS
# =========================


def memory_context(memory: SessionMemory) -> str:
    notes = memory.recent_prompt_notes(5)
    if not notes:
        return ""
    joined = "\n".join(f"- {n}" for n in notes)
    return f"Recent process notes from prior runs:\n{joined}\n"


def idea_generation_prompt(question: str, memory: SessionMemory, role_id: str) -> str:
    extra = memory_context(memory)
    return textwrap.dedent(f"""
    You are AI {role_id}. Follow this instruction carefully.

    Generate ONE distinct, high-quality solution idea to the user's prompt.
    Be original and specific. Do not copy the style of the other AIs.

    IMPORTANT CONSTRAINT:
    Your idea must NOT be a generic productivity app, scheduling tool, note-taking app, chatbot assistant, or study planner unless it introduces a truly novel mechanism that does not already exist.

    User prompt:
    {question}

    {extra}

    Output format:
    Idea:
    <your idea>
    Reasoning:
    <short reasoning>
    """).strip()


def critique_prompt(question: str, idea_id: str, idea_text: str, critic_id: str, memory: SessionMemory) -> str:
    extra = memory_context(memory)
    critic_bias = """You are a skeptical reviewer. Look for flaws, missing pieces, hallucinations, and practical issues. Be extremely critical. If it is not innovative or specific, score it below 5"""
    return textwrap.dedent(f"""
    {critic_bias}

    User prompt:
    {question}

    Idea {idea_id}:
    {idea_text}

    {extra}

    Return valid JSON only with keys:
    score (number 1 to 10),
    reason (string),
    strengths (array of strings),
    weaknesses (array of strings).
    """).strip()


def improvement_prompt(question: str, idea: Idea, critique_summary: str, role_id: str, memory: SessionMemory, prompt_notes: List[str]) -> str:
    extra = memory_context(memory)
    notes = "\n".join(f"- {n}" for n in prompt_notes)
    return textwrap.dedent(f"""
    You are AI {role_id}. Improve the idea while preserving the core goal.

    User prompt:
    {question}

    Original idea:
    {idea.text}

    Critique summary:
    {critique_summary}

    Process notes to follow:
    {notes if notes else '- none'}

    {extra}

    Requirements:
    - Keep the idea concrete.
    - Fix the problems mentioned in critique.
    - Preserve what is already good.
    - If multiple surviving ideas exist, contribute a complementary improvement, not a duplicate.

    Output format:
    Improved idea:
    <your improved idea>

    Short justification:
    <1-3 sentences>
    """).strip()


def hybrid_prompt(question: str, ideas: List[Idea], critique_summary: str, memory: SessionMemory) -> str:
    extra = memory_context(memory)
    blocks = "\n\n".join([f"Idea {idea.id}:\n{idea.text}" for idea in ideas])
    return textwrap.dedent(f"""
    Combine the best features of the surviving ideas into a single stronger hybrid.

    User prompt:
    {question}

    Surviving ideas:
    {blocks}

    Critique summary:
    {critique_summary}

    {extra}

    Output format:
    Hybrid idea:
    <your hybrid>

    Short justification:
    <1-3 sentences>
    """).strip()


def final_presentation_prompt(question: str, final_idea: Idea, style: str, memory: SessionMemory) -> str:
    extra = memory_context(memory)
    return textwrap.dedent(f"""
    Present the final idea in the best possible way.

    User prompt:
    {question}

    Final idea:
    {final_idea.text}

    Presentation style:
    {style}

    {extra}

    Make the response polished, clear, and useful.
    """).strip()


def self_improve_prompt_prompt(question: str, memory: SessionMemory, recent_rounds: List[RoundResult]) -> str:
    # This is a small meta-prompt that asks the model to suggest prompt improvements.
    # The system then uses the suggestion to tweak future prompts.
    round_summaries = []
    for r in recent_rounds[-3:]:
        top = sorted(r.scores.items(), key=lambda x: x[1], reverse=True)
        round_summaries.append(
            {
                "round": r.round_index,
                "scores": top,
                "survivors": list(r.survivors.keys()),
            }
        )
    return textwrap.dedent(f"""
    You are a prompt optimizer. Improve the instructions used by a multi-agent AI council.

    User prompt:
    {question}

    Recent round summaries:
    {json.dumps(round_summaries, indent=2)}

    Return valid JSON only with keys:
    note (string),
    revised_rule (string).
    The revised_rule should be a short instruction that can be appended to future prompts.
    """).strip()


# =========================
# CORE PIPELINE
# =========================


def parallel_map(func, items: List[Any]) -> List[Any]:
    if not USE_PARALLEL or len(items) <= 1:
        return [func(item) for item in items]
    results = [None] * len(items)
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(items))) as ex:
        futures = {ex.submit(func, item): idx for idx, item in enumerate(items)}
        for fut in as_completed(futures):
            idx = futures[fut]
            results[idx] = fut.result()
    return results


def generate_initial_ideas(question: str, memory: SessionMemory, graph: EvolutionGraph) -> Dict[str, Idea]:
    def make_task(item: Tuple[str, str]) -> Tuple[str, Idea]:
        role_id, model = item
        prompt = idea_generation_prompt(question, memory, role_id)
        text = ask_model(model, prompt)
        idea = Idea(
            id=role_id,
            text=text.strip(),
            origin=model,
            generation=0,
        )
        return role_id, idea

    tasks = list(MODELS.items())
    outputs = parallel_map(make_task, tasks)
    ideas = {idea_id: idea for idea_id, idea in outputs}

    for idea in ideas.values():
        graph.add_node(f"I{idea.id}_g0", f"Idea {idea.id} (g0)")
    return ideas


def parse_critique(model_id: str, idea_id: str, raw: str) -> CritiqueResult:
    parsed = safe_json_loads(raw)
    if parsed is None:
        score = extract_score_fallback(raw)
        return CritiqueResult(
            critic_id=model_id,
            idea_id=idea_id,
            score=score,
            reason=raw[:400],
            raw=raw,
        )

    score = parsed.get("score", 5.0)
    try:
        score = float(score)
    except Exception:
        score = extract_score_fallback(raw)

    strengths = parsed.get("strengths", []) or []
    weaknesses = parsed.get("weaknesses", []) or []
    reason = parsed.get("reason", "") or raw[:400]
    return CritiqueResult(
        critic_id=model_id,
        idea_id=idea_id,
        score=float(score),
        reason=reason,
        strengths=[str(x) for x in strengths],
        weaknesses=[str(x) for x in weaknesses],
        raw=raw,
    )


def critique_ideas(question: str, ideas: Dict[str, Idea], memory: SessionMemory) -> List[CritiqueResult]:
    jobs = []
    for critic_id, model in MODELS.items():
        for idea_id, idea in ideas.items():
            jobs.append((critic_id, model, idea_id, idea))

    def worker(job: Tuple[str, str, str, Idea]) -> CritiqueResult:
        critic_id, model, idea_id, idea = job
        prompt = critique_prompt(question, idea_id, idea.text, critic_id, memory)
        raw = ask_model(model, prompt)
        result = parse_critique(critic_id, idea_id, raw)
        memory.note_critic_performance(critic_id, result.score)
        return result

    return parallel_map(worker, jobs)


def aggregate_scores(critique_results: List[CritiqueResult]) -> Dict[str, float]:
    grouped: Dict[str, List[float]] = {}
    for c in critique_results:
        grouped.setdefault(c.idea_id, []).append(c.score)

    avg_scores = {idea_id: statistics.mean(scores) for idea_id, scores in grouped.items()}
    return avg_scores


def weighted_aggregate_scores(critique_results: List[CritiqueResult], memory: SessionMemory) -> Dict[str, float]:
    grouped: Dict[str, List[Tuple[float, float]]] = {}
    for c in critique_results:
        w = memory.critic_weight(c.critic_id) if USE_CRITIC_WEIGHTS else 1.0
        grouped.setdefault(c.idea_id, []).append((c.score, w))

    scores: Dict[str, float] = {}
    for idea_id, pairs in grouped.items():
        numerator = sum(score * weight for score, weight in pairs)
        denominator = sum(weight for _, weight in pairs) or 1.0
        scores[idea_id] = numerator / denominator
    return scores


def detect_outliers_and_survivors(scores: Dict[str, float], top_k: int = TOP_K_SURVIVORS) -> Tuple[List[str], List[str]]:
    if not scores:
        return [], []

    items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    values = [v for _, v in items]
    mean = statistics.mean(values)
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0

    survivors: List[str] = []
    eliminated: List[str] = []

    # Keep ideas that are not outliers below the mean by too much and above minimum score.
    for idea_id, score in items:
        below_outlier_cutoff = (mean - OUTLIER_STD_THRESHOLD * stdev) if stdev > 0 else MIN_SCORE_TO_SURVIVE
        if score >= max(MIN_SCORE_TO_SURVIVE, below_outlier_cutoff):
            survivors.append(idea_id)
        else:
            eliminated.append(idea_id)

    # Guarantee at least top_k survivors.
    if len(survivors) < min(top_k, len(items)):
        for idea_id, _ in items:
            if idea_id not in survivors:
                survivors.append(idea_id)
            if len(survivors) >= min(top_k, len(items)):
                break
        eliminated = [i for i in scores if i not in survivors]

    # Limit survivors to top_k if too many.
    if len(survivors) > top_k:
        survivors = [idea_id for idea_id, _ in items[:top_k]]
        eliminated = [i for i in scores if i not in survivors]

    return survivors, eliminated


def summarize_critiques(critique_results: List[CritiqueResult], idea_ids: List[str]) -> str:
    blocks = []
    for idea_id in idea_ids:
        related = [c for c in critique_results if c.idea_id == idea_id]
        if not related:
            continue
        scores = [c.score for c in related]
        avg = statistics.mean(scores)
        reasons = " | ".join(c.reason[:160].replace("\n", " ") for c in related[:2])
        blocks.append(f"Idea {idea_id}: avg={avg:.2f}; notes={reasons}")
    return "\n".join(blocks)


def choose_best_strongest_idea(ideas: Dict[str, Idea], scores: Dict[str, float]) -> Idea:
    best_id = max(scores, key=scores.get)
    return ideas[best_id]


def improve_survivors(
    question: str,
    survivors: Dict[str, Idea],
    critique_results: List[CritiqueResult],
    memory: SessionMemory,
    graph: EvolutionGraph,
    prompt_notes: List[str],
    round_index: int,
) -> Dict[str, Idea]:
    survivor_ids = list(survivors.keys())
    critique_summary = summarize_critiques(critique_results, survivor_ids)

    jobs: List[Tuple[str, str, Idea, str]] = []
    # one direct improver per survivor, using a different AI each time (cycled)
    model_keys = list(MODELS.keys())
    for idx, idea_id in enumerate(survivor_ids):
        model_key = model_keys[idx % len(model_keys)]
        jobs.append((idea_id, model_key, survivors[idea_id], critique_summary))

    def worker(job: Tuple[str, str, Idea, str]) -> Tuple[str, Idea]:
        idea_id, model_key, idea, summary = job
        model = MODELS[model_key]
        prompt = improvement_prompt(question, idea, summary, model_key, memory, prompt_notes)
        raw = ask_model(model, prompt)
        improved = Idea(
            id=f"{idea_id}i{round_index}",
            text=raw.strip(),
            origin=model,
            generation=idea.generation + 1,
            parent_ids=[idea.id],
        )
        return idea_id, improved

    outputs = parallel_map(worker, jobs)
    improved = {old_id: new_idea for old_id, new_idea in outputs}

    # Add hybrid of all survivors
    survivor_ideas = list(survivors.values())
    if len(survivor_ideas) >= 2:
        # Use AI 1 as the hybrid synthesizer to keep the process stable.
        hybrid_text = ask_model(MODELS["1"], hybrid_prompt(question, survivor_ideas, critique_summary, memory))
        hybrid = Idea(
            id=f"H{round_index}",
            text=hybrid_text.strip(),
            origin=MODELS["1"],
            generation=max(i.generation for i in survivor_ideas) + 1,
            parent_ids=[i.id for i in survivor_ideas],
        )
    else:
        hybrid = None

    # Update graph nodes and edges
    for old_id, new_idea in improved.items():
        graph.add_node(f"{new_idea.id}", f"{new_idea.id}")
        graph.add_edge(f"I{old_id}" if not old_id.startswith("H") else old_id, f"{new_idea.id}")
    if hybrid:
        graph.add_node(hybrid.id, hybrid.id)
        for p in hybrid.parent_ids:
            graph.add_edge(f"{p}", hybrid.id)

    new_pool = dict(improved)
    if hybrid:
        # Use the hybrid alongside improved survivors.
        new_pool[hybrid.id] = hybrid

    return new_pool


def maybe_self_improve_prompts(question: str, memory: SessionMemory, recent_rounds: List[RoundResult]) -> List[str]:
    if not ADAPT_PROMPTS:
        return []

    # Ask AI 1 to optimize the process. This does not change the pipeline order,
    # only appends a short rule to future prompts.
    prompt = self_improve_prompt_prompt(question, memory, recent_rounds)
    raw = ask_model(MODELS["1"], prompt)
    parsed = safe_json_loads(raw)
    if not parsed:
        return []

    note = str(parsed.get("note", "")).strip()
    revised_rule = str(parsed.get("revised_rule", "")).strip()
    if note:
        memory.add_prompt_note(note)
    if revised_rule:
        memory.add_prompt_note(revised_rule)
        return [revised_rule]
    return []


def should_stop(round_index: int, scores_history: List[Dict[str, float]], ideas: Dict[str, Idea]) -> bool:
    # Stop if one idea remains or max rounds reached.
    if len(ideas) <= 1:
        return True
    if round_index >= MAX_ROUNDS - 1:
        return True

    # Stop if no meaningful improvement over the last two rounds.
    if len(scores_history) >= 3:
        last = scores_history[-1]
        prev = scores_history[-2]
        if last and prev:
            best_last = max(last.values())
            best_prev = max(prev.values())
            if abs(best_last - best_prev) < 0.15:
                return False  # keep going a bit, but do not force stop too early
    return False


def reduce_to_one_idea(question: str, memory: SessionMemory, graph: EvolutionGraph) -> Tuple[Idea, List[RoundResult]]:
    ideas = generate_initial_ideas(question, memory, graph)
    rounds: List[RoundResult] = []
    scores_history: List[Dict[str, float]] = []
    prompt_notes: List[str] = []

    # The process starts exactly as requested: independent generation.
    for round_index in range(MAX_ROUNDS):
        critiques = critique_ideas(question, ideas, memory)
        scores = weighted_aggregate_scores(critiques, memory)
        scores_history.append(scores)

        survivor_ids, eliminated_ids = detect_outliers_and_survivors(scores, top_k=TOP_K_SURVIVORS)
        survivors = {iid: ideas[iid] for iid in survivor_ids if iid in ideas}
        eliminated = {iid: ideas[iid] for iid in eliminated_ids if iid in ideas}

        # If only one survives, that's the final core idea.
        if len(survivors) == 1:
            final_core = next(iter(survivors.values()))
            rounds.append(
                RoundResult(
                    round_index=round_index,
                    ideas_before=ideas,
                    critiques=critiques,
                    scores=scores,
                    survivors=survivors,
                    eliminated=eliminated,
                    improved={},
                    hybrid=None,
                )
            )
            return final_core, rounds

        # STEP 3: improve the survivors
        improved_pool = improve_survivors(
            question=question,
            survivors=survivors,
            critique_results=critiques,
            memory=memory,
            graph=graph,
            prompt_notes=prompt_notes,
            round_index=round_index,
        )

        # Optional self-improvement of prompts after each round.
        prompt_notes = maybe_self_improve_prompts(question, memory, rounds)

        rounds.append(
            RoundResult(
                round_index=round_index,
                ideas_before=ideas,
                critiques=critiques,
                scores=scores,
                survivors=survivors,
                eliminated=eliminated,
                improved=improved_pool,
                hybrid=improved_pool.get(f"H{round_index}"),
            )
        )

        ideas = improved_pool

        if should_stop(round_index, scores_history, ideas):
            break

    # Choose the strongest remaining idea as the final core idea.
    final_scores = aggregate_scores(critique_ideas(question, ideas, memory))
    final_core = choose_best_strongest_idea(ideas, final_scores)
    return final_core, rounds


# =========================
# FINAL PRESENTATION PHASE
# =========================


def generate_presentations(question: str, final_core: Idea, memory: SessionMemory) -> Dict[str, Idea]:
    styles = {
        "1": "technical and concise",
        "2": "balanced and explanatory",
        "3": "polished and compelling",
    }
    presentations: Dict[str, Idea] = {}

    def worker(item: Tuple[str, str]) -> Tuple[str, Idea]:
        pid, model = item
        prompt = final_presentation_prompt(question, final_core, styles[pid], memory)
        text = ask_model(model, prompt)
        idea = Idea(
            id=f"P{pid}",
            text=text.strip(),
            origin=model,
            generation=final_core.generation,
            parent_ids=[final_core.id],
        )
        return pid, idea

    outputs = parallel_map(worker, list(MODELS.items()))
    for pid, idea in outputs:
        presentations[pid] = idea
    return presentations


def vote_presentations(question: str, presentations: Dict[str, Idea], memory: SessionMemory) -> Tuple[str, Dict[str, float], List[CritiqueResult]]:
    critiques = critique_ideas(question, presentations, memory)
    scores = weighted_aggregate_scores(critiques, memory)

    # Real voting: each critic ranks the candidate presentations, then the bot aggregates.
    # We use the scores as a proxy for rank aggregation, and keep the top score.
    winner = max(scores, key=scores.get)
    return winner, scores, critiques


# =========================
# REPORTING
# =========================


def print_round_summary(round_result: RoundResult) -> None:
    print(f"\n--- Round {round_result.round_index + 1} ---")
    print("Scores:")
    for idea_id, score in sorted(round_result.scores.items(), key=lambda x: x[1], reverse=True):
        status = "SURVIVED" if idea_id in round_result.survivors else "CUT"
        print(f"  {idea_id}: {score:.2f}  [{status}]")

    print("Survivors:", ", ".join(round_result.survivors.keys()) if round_result.survivors else "none")
    if round_result.hybrid:
        print(f"Hybrid: {round_result.hybrid.id}")


# =========================
# MAIN ENTRY
# =========================


def run_council(question: str) -> str:
    memory = SessionMemory(enabled=USE_MEMORY, path=MEMORY_PATH)
    graph = EvolutionGraph()

    final_core, rounds = reduce_to_one_idea(question, memory, graph)

    # Final presentation competition, exactly per the process.
    presentations = generate_presentations(question, final_core, memory)
    winner, final_scores, final_critiques = vote_presentations(question, presentations, memory)
    best_presentation = presentations[winner]

    # Save graph if enabled.
    if EXPORT_MERMAID:
        graph.save(MERMAID_PATH)

    # Save run summary to memory.
    if USE_MEMORY:
        memory.append_run(
            {
                "question": question,
                "rounds": len(rounds),
                "final_core": final_core.text[:1000],
                "presentation_winner": winner,
                "presentation_scores": final_scores,
            }
        )

    # Print a compact trace so you can see the process.
    print("\n============================")
    print("AI COUNCIL PROCESS TRACE")
    print("============================")
    for rr in rounds:
        print_round_summary(rr)

    print("\n--- Final core idea ---")
    print(compact(final_core.text, 1200))

    print("\n--- Final presentation scores ---")
    for pid, score in sorted(final_scores.items(), key=lambda x: x[1], reverse=True):
        print(f"  P{pid}: {score:.2f}")

    print("\n--- Winner ---")
    print(f"Presentation {winner}")
    return best_presentation.text


if __name__ == "__main__":
    user_question = input("Enter your prompt: ").strip()
    if not user_question:
        raise SystemExit("No prompt entered.")

    result = run_council(user_question)
    print("\n\n============================")
    print("FINAL ANSWER")
    print("============================\n")
    print(result)
