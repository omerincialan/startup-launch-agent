"""Benchmark the recursive positioning loop on fixed startup ideas.

Default mode calls the configured OpenAI model. Use --mock to verify the complete
evaluation pipeline without network access or API cost.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent  # noqa: E402


CASES = [
    {
        "id": "real-estate-follow-up",
        "idea": "An AI assistant for independent real-estate agents.",
        "hypothesis": (
            "Buyer agents lose qualified opportunities because inconsistent lead "
            "follow-up lets high-intent prospects go cold."
        ),
    },
    {
        "id": "ecommerce-reviews",
        "idea": "A tool that helps small ecommerce brands use customer reviews.",
        "hypothesis": (
            "Lean ecommerce teams struggle to turn scattered review language into "
            "credible product-page and advertising messages."
        ),
    },
    {
        "id": "consultant-proposals",
        "idea": "An AI copilot for independent consultants.",
        "hypothesis": (
            "Solo consultants lose momentum when creating tailored proposals and "
            "following up consistently requires too much non-billable work."
        ),
    },
]


def install_mock_model() -> None:
    """Install a deterministic stand-in that exercises one improvement cycle."""

    def mock_structured(prompt: str, schema):
        improving = (
            "Best positioning so far:" in prompt
            or "Recover valuable opportunities" in prompt
        )
        if schema is agent.PositioningArtifact:
            if improving:
                return schema(
                    statement=(
                        "For a specific underserved customer, the product resolves "
                        "a recurring revenue-risk workflow with a focused assistant "
                        "while keeping unvalidated performance claims explicit."
                    ),
                    headline="Recover valuable opportunities before they go cold",
                    target_customer="A clearly defined small-business operator",
                    painful_problem="A repeated workflow causes valuable opportunities to be missed",
                    differentiated_value="Focuses on one measurable workflow instead of generic assistance",
                    proof_needed="Customer interviews and a measured workflow pilot",
                )
            return schema(
                statement="An AI assistant that helps businesses save time.",
                headline="Work smarter with AI",
                target_customer="Businesses",
                painful_problem="Too much manual work",
                differentiated_value="Uses AI",
                proof_needed="Customer validation",
            )
        if schema is agent.PositioningEvaluation:
            scores = (8.6, 8.4, 8.5, 8.0, 8.8) if improving else (6.0, 4.5, 5.5, 3.5, 7.0)
            return schema(
                clarity=scores[0],
                specificity=scores[1],
                customer_relevance=scores[2],
                differentiation=scores[3],
                credibility=scores[4],
                strengths=["Avoids unsupported proof claims"],
                feedback=(
                    ["Ready to test with target customers"]
                    if improving
                    else ["Name a narrower customer", "Make the costly workflow concrete"]
                ),
            )
        raise TypeError(f"Unsupported schema: {schema}")

    agent.run_structured = mock_structured


def evaluate_case(case: dict[str, str], threshold: float, max_iterations: int) -> dict:
    graph = agent.build_positioning_graph()
    state = graph.invoke(
        {
            "project_id": f"eval-{case['id']}",
            "startup_idea": case["idea"],
            "selected_hypothesis": case["hypothesis"],
            "research_findings": "Evaluation fixture: no external research supplied.",
            "positioning_attempts": [],
            "positioning_iteration": 0,
            "positioning_threshold": threshold,
            "positioning_max_iterations": max_iterations,
            "current_phase": "positioning",
            "status": "running",
            "silent": True,
        }
    )
    evaluation = state["positioning_evaluation"]
    return {
        "id": case["id"],
        "score": evaluation["score"],
        "passed": evaluation["passed"],
        "iterations": state["positioning_iteration"],
        "dimensions": evaluation["dimensions"],
        "final_statement": state["positioning"]["statement"],
        "attempt_scores": [
            attempt["evaluation"]["score"] for attempt in state["positioning_attempts"]
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate startup positioning quality")
    parser.add_argument("--mock", action="store_true", help="Run without API calls")
    parser.add_argument("--threshold", type=float, default=8.0)
    parser.add_argument("--max-iterations", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 0 <= args.threshold <= 10:
        print(json.dumps({"ok": False, "error": "threshold must be between 0 and 10"}))
        return 2
    if args.max_iterations < 1:
        print(json.dumps({"ok": False, "error": "max-iterations must be positive"}))
        return 2
    if args.mock:
        install_mock_model()

    try:
        cases = [evaluate_case(case, args.threshold, args.max_iterations) for case in CASES]
        scores = [case["score"] for case in cases]
        payload = {
            "ok": True,
            "mode": "mock" if args.mock else "live",
            "metric": "positioning_quality",
            "aggregate_score": round(mean(scores), 2),
            "pass_rate": round(sum(case["passed"] for case in cases) / len(cases), 3),
            "case_count": len(cases),
            "cases": cases,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "mode": "mock" if args.mock else "live", "error": str(exc)},
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
