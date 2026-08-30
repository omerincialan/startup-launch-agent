"""Demo-ready, long-horizon startup launch agent.

This vertical slice takes a founder from an idea to a selected problem hypothesis
and an evidence-driven 30-day validation roadmap. LangGraph checkpoints make the
human decision durable, so a project can be stopped and resumed later.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict, TypeVar

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "startup_agent.db"
ARTIFACTS_DIR = ROOT / "artifacts"

load_dotenv(ROOT / ".env")


class StartupState(TypedDict, total=False):
    project_id: str
    startup_idea: str
    goal: str
    research_plan: str
    research_findings: str
    pain_points: str
    hypotheses: str
    selected_hypothesis: str
    positioning: dict[str, str]
    positioning_evaluation: dict[str, Any]
    best_positioning: dict[str, str]
    best_positioning_evaluation: dict[str, Any]
    positioning_attempts: list[dict[str, Any]]
    positioning_iteration: int
    positioning_threshold: float
    positioning_max_iterations: int
    validation_plan: str
    thirty_day_roadmap: str
    current_phase: str
    status: str
    silent: bool


class PositioningArtifact(BaseModel):
    statement: str = Field(description="One-sentence positioning statement")
    headline: str = Field(description="Short landing-page headline")
    target_customer: str
    painful_problem: str
    differentiated_value: str
    proof_needed: str


class PositioningEvaluation(BaseModel):
    clarity: float = Field(ge=0, le=10)
    specificity: float = Field(ge=0, le=10)
    customer_relevance: float = Field(ge=0, le=10)
    differentiation: float = Field(ge=0, le=10)
    credibility: float = Field(ge=0, le=10)
    strengths: list[str]
    feedback: list[str]


StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


def make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("STARTUP_AGENT_MODEL", "gpt-5.6-terra"),
        temperature=0,
    )


def run_llm(prompt: str) -> str:
    response = make_llm().invoke(prompt)
    return str(response.content)


def run_structured(prompt: str, schema: type[StructuredModel]) -> StructuredModel:
    model = make_llm().with_structured_output(schema)
    return model.invoke(prompt)


def announce(step: int, title: str) -> None:
    print(f"\n[{step}/8] {title}", flush=True)


def plan_research(state: StartupState) -> dict[str, str]:
    announce(1, "Planning the opportunity research")
    prompt = f"""
You are a startup research agent. Build a concise research plan for this idea:

{state['startup_idea']}

Goal: {state['goal']}

Investigate target users, their jobs-to-be-done, recurring workflow problems,
existing alternatives, likely competitors, and areas where AI could create
measurable value. State what evidence is needed. Do not recommend a product yet.
Infer the relevant market and users only from the submitted idea. Do not assume
an industry, customer type, or business model that the founder did not provide.
Use clear Markdown headings and bullets.
"""
    return {
        "research_plan": run_llm(prompt),
        "current_phase": "research",
        "status": "running",
    }


def research(state: StartupState) -> dict[str, str]:
    announce(2, "Producing preliminary market findings")
    prompt = f"""
Act as a skeptical startup market researcher.

Startup idea: {state['startup_idea']}
Research plan:
{state['research_plan']}

Using existing knowledge, produce an initial market analysis. Identify major
workflows, painful or repetitive tasks, important decisions and interactions,
existing solution categories, and gaps in current alternatives. Label every material
claim as either OBSERVATION or ASSUMPTION. This is preliminary research, not proof.
Adapt the analysis to the idea's actual market; do not default to real estate or
any other example industry.
Use concise Markdown.
"""
    return {"research_findings": run_llm(prompt)}


def synthesize_pain_points(state: StartupState) -> dict[str, str]:
    announce(3, "Synthesizing concrete pain points")
    prompt = f"""
Analyze these preliminary findings:

{state['research_findings']}

Extract exactly five concrete pain points. For each give: affected user, triggering
workflow, current workaround, business consequence, possible AI advantage,
confidence (high/medium/low), and evidence still required. Avoid generic claims
such as 'save time'. Use concise Markdown.
"""
    return {"pain_points": run_llm(prompt)}


def generate_hypotheses(state: StartupState) -> dict[str, str]:
    announce(4, "Generating competing hypotheses")
    prompt = f"""
Startup idea: {state['startup_idea']}

Candidate pain points:
{state['pain_points']}

Generate exactly three meaningfully different startup hypotheses. For each use:
HYPOTHESIS N, User, Problem, Proposed AI solution, Why promising, Riskiest
assumption, and Cheapest falsification test. Make each option easy to compare.
"""
    return {
        "hypotheses": run_llm(prompt),
        "current_phase": "hypothesis_selection",
        "status": "waiting_for_founder",
    }


def human_selection(state: StartupState) -> dict[str, str]:
    answer = interrupt(
        {
            "type": "human_decision",
            "question": "Which hypothesis should we validate?",
            "hypotheses": state["hypotheses"],
            "instructions": "Choose 1, 2, or 3, or provide written feedback.",
        }
    )
    return {
        "selected_hypothesis": str(answer).strip(),
        "status": "human_decision_received",
        "current_phase": "positioning_generation",
    }


def positioning_markdown(positioning: dict[str, str]) -> str:
    return "\n".join(
        [
            f"## {positioning['headline']}",
            "",
            positioning["statement"],
            "",
            f"**Target customer:** {positioning['target_customer']}",
            f"**Painful problem:** {positioning['painful_problem']}",
            f"**Differentiated value:** {positioning['differentiated_value']}",
            f"**Proof still needed:** {positioning['proof_needed']}",
        ]
    )


def generate_positioning(state: StartupState) -> dict[str, Any]:
    iteration = state.get("positioning_iteration", 0) + 1
    if not state.get("silent"):
        print(f"\n[5/8] Positioning iteration {iteration}", flush=True)

    previous = state.get("positioning_evaluation")
    improvement_context = ""
    if previous:
        improvement_context = f"""
Best positioning so far:
{json.dumps(state.get('best_positioning', state.get('positioning', {})), indent=2)}

Evaluator feedback:
{json.dumps(previous.get('feedback', []), indent=2)}

Create a materially improved version. Address the feedback without adding claims
that have not been validated.
"""

    prompt = f"""
You are a startup positioning strategist.

Startup idea:
{state['startup_idea']}

Selected problem hypothesis or founder feedback:
{state['selected_hypothesis']}

Candidate hypotheses shown to the founder:
{state.get('hypotheses', 'The evaluation supplied the selected hypothesis directly.')}

Relevant preliminary findings:
{state.get('research_findings', 'No external findings supplied.')}
{improvement_context}

Create positioning that names a specific customer, a concrete painful situation,
a valuable outcome, and a believable difference from alternatives. Do not invent
traction, customer quotes, performance numbers, or proof.
"""
    artifact = run_structured(prompt, PositioningArtifact)
    return {
        "positioning": artifact.model_dump(),
        "positioning_iteration": iteration,
        "current_phase": "positioning_evaluation",
        "status": "running",
    }


def evaluate_positioning(state: StartupState) -> dict[str, Any]:
    if not state.get("silent"):
        print("[6/8] Evaluating positioning quality", flush=True)
    prompt = f"""
You are a strict startup-positioning evaluator. Score the candidate independently.

Startup idea:
{state['startup_idea']}

Selected hypothesis:
{state['selected_hypothesis']}

Candidate positioning:
{json.dumps(state['positioning'], indent=2)}

Score each dimension from 0 to 10:
- clarity: understandable on first reading
- specificity: precise customer, situation, and outcome
- customer_relevance: addresses an urgent and meaningful problem
- differentiation: gives a reason to choose it over alternatives
- credibility: avoids unsupported promises and identifies proof still needed

Use 8+ only for unusually strong work. Give concrete feedback that can guide the
next iteration. Do not reward polished language when the strategy is vague.
"""
    raw = run_structured(prompt, PositioningEvaluation)
    values = raw.model_dump()
    dimensions = {
        key: values[key]
        for key in (
            "clarity",
            "specificity",
            "customer_relevance",
            "differentiation",
            "credibility",
        )
    }
    score = round(sum(dimensions.values()) / len(dimensions), 2)
    threshold = state.get("positioning_threshold", 8.0)
    passed = score >= threshold
    evaluation = {
        "score": score,
        "threshold": threshold,
        "passed": passed,
        "dimensions": dimensions,
        "strengths": values["strengths"],
        "feedback": values["feedback"],
    }
    attempt = {
        "iteration": state["positioning_iteration"],
        "positioning": state["positioning"],
        "evaluation": evaluation,
    }
    attempts = [*state.get("positioning_attempts", []), attempt]
    best_evaluation = state.get("best_positioning_evaluation")
    if best_evaluation is None or score > best_evaluation["score"]:
        best_positioning = state["positioning"]
        best_evaluation = evaluation
    else:
        best_positioning = state["best_positioning"]
    return {
        "positioning_evaluation": evaluation,
        "positioning_attempts": attempts,
        "best_positioning": best_positioning,
        "best_positioning_evaluation": best_evaluation,
        "current_phase": "positioning_ready" if passed else "positioning_improvement",
    }


def route_positioning(
    state: StartupState,
) -> Literal["generate_positioning", "select_best_positioning"]:
    if state["best_positioning_evaluation"]["passed"]:
        return "select_best_positioning"
    if state["positioning_iteration"] >= state.get("positioning_max_iterations", 3):
        return "select_best_positioning"
    return "generate_positioning"


def select_best_positioning(state: StartupState) -> dict[str, Any]:
    """Carry the strongest attempt forward, even if a later retry regressed."""
    return {
        "positioning": state["best_positioning"],
        "positioning_evaluation": state["best_positioning_evaluation"],
        "current_phase": "validation_planning",
    }


def create_validation_plan(state: StartupState) -> dict[str, str]:
    announce(7, "Creating the validation plan")
    prompt = f"""
You are a customer-discovery strategist.

Startup idea: {state['startup_idea']}
Founder selection or feedback: {state['selected_hypothesis']}
Candidate hypotheses:
{state['hypotheses']}

Best positioning after {state.get('positioning_iteration', 0)} iteration(s):
{positioning_markdown(state['positioning'])}

Positioning evaluation:
{json.dumps(state.get('positioning_evaluation', {}), indent=2)}

Create a pre-product validation plan. Define the ICP, exact problem, alternatives,
five critical assumptions, interview recruiting strategy, ten non-leading interview
questions, supporting evidence, rejection evidence, quantitative success criteria,
and the cheapest next experiment. Treat the hypothesis as unproven. Use Markdown.
"""
    return {
        "validation_plan": run_llm(prompt),
        "current_phase": "roadmap_planning",
        "status": "running",
    }


def create_thirty_day_roadmap(state: StartupState) -> dict[str, str]:
    announce(8, "Turning strategy into a 30-day roadmap")
    prompt = f"""
Turn this validation plan into a practical 30-day founder roadmap:

{state['validation_plan']}

Organize it into Week 1 through Week 4. Include no more than five tasks per week.
For every task specify owner (Founder or Agent), deliverable, dependency, evidence
captured, and done criterion. Add three decision gates: continue, revise, or stop.
Prioritize learning over building. End with a compact demo-ready scorecard.
Use clear Markdown tables or bullets.
"""
    return {
        "thirty_day_roadmap": run_llm(prompt),
        "current_phase": "validation_ready",
        "status": "completed",
    }


def build_graph(checkpointer: SqliteSaver):
    builder = StateGraph(StartupState)
    builder.add_node("plan_research", plan_research)
    builder.add_node("research", research)
    builder.add_node("synthesize", synthesize_pain_points)
    builder.add_node("hypotheses", generate_hypotheses)
    builder.add_node("human_selection", human_selection)
    builder.add_node("generate_positioning", generate_positioning)
    builder.add_node("evaluate_positioning", evaluate_positioning)
    builder.add_node("select_best_positioning", select_best_positioning)
    builder.add_node("validation_plan", create_validation_plan)
    builder.add_node("roadmap", create_thirty_day_roadmap)
    builder.add_edge(START, "plan_research")
    builder.add_edge("plan_research", "research")
    builder.add_edge("research", "synthesize")
    builder.add_edge("synthesize", "hypotheses")
    builder.add_edge("hypotheses", "human_selection")
    builder.add_edge("human_selection", "generate_positioning")
    builder.add_edge("generate_positioning", "evaluate_positioning")
    builder.add_conditional_edges(
        "evaluate_positioning",
        route_positioning,
        {
            "generate_positioning": "generate_positioning",
            "select_best_positioning": "select_best_positioning",
        },
    )
    builder.add_edge("select_best_positioning", "validation_plan")
    builder.add_edge("validation_plan", "roadmap")
    builder.add_edge("roadmap", END)
    return builder.compile(checkpointer=checkpointer)


def build_positioning_graph():
    """Build the isolated recursive loop used by automated evaluations."""
    builder = StateGraph(StartupState)
    builder.add_node("generate_positioning", generate_positioning)
    builder.add_node("evaluate_positioning", evaluate_positioning)
    builder.add_node("select_best_positioning", select_best_positioning)
    builder.add_edge(START, "generate_positioning")
    builder.add_edge("generate_positioning", "evaluate_positioning")
    builder.add_conditional_edges(
        "evaluate_positioning",
        route_positioning,
        {
            "generate_positioning": "generate_positioning",
            "select_best_positioning": "select_best_positioning",
        },
    )
    builder.add_edge("select_best_positioning", END)
    return builder.compile()


def safe_project_id(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    if not cleaned:
        raise argparse.ArgumentTypeError("Project ID must contain a letter or number.")
    return cleaned


def default_project_id() -> str:
    return f"startup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def save_artifact(state: StartupState) -> Path:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    path = ARTIFACTS_DIR / f"{state['project_id']}.md"
    sections = [
        ("Startup Launch Brief", state.get("startup_idea", "")),
        ("Goal", state.get("goal", "")),
        ("Research Plan", state.get("research_plan", "")),
        ("Preliminary Findings", state.get("research_findings", "")),
        ("Pain Points", state.get("pain_points", "")),
        ("Competing Hypotheses", state.get("hypotheses", "")),
        ("Founder Decision", state.get("selected_hypothesis", "")),
        (
            "Positioning Iteration History",
            "\n\n".join(
                f"## Iteration {attempt['iteration']} — "
                f"{attempt['evaluation']['score']}/10\n\n"
                f"{positioning_markdown(attempt['positioning'])}\n\n"
                f"**Feedback:** "
                f"{' '.join(attempt['evaluation']['feedback'])}"
                for attempt in state.get("positioning_attempts", [])
            ),
        ),
        ("Validation Plan", state.get("validation_plan", "")),
        ("30-Day Roadmap", state.get("thirty_day_roadmap", "")),
    ]
    body = "\n\n".join(f"# {title}\n\n{content}" for title, content in sections)
    path.write_text(body + "\n", encoding="utf-8")
    return path


def show_decision(interrupt_data: dict) -> None:
    print("\n" + "=" * 72)
    print("FOUNDER DECISION REQUIRED")
    print("=" * 72)
    print(interrupt_data["hypotheses"])
    print(f"\n{interrupt_data['question']}")
    print(interrupt_data["instructions"])


def finish_project(graph, config: dict, result: dict, choice: str | None) -> None:
    if "__interrupt__" in result:
        data = result["__interrupt__"][0].value
        show_decision(data)
        if choice is None:
            choice = input("\nYour choice: ").strip()
        if not choice:
            print("No choice entered. Resume later with --resume and --choice.")
            return
        result = graph.invoke(Command(resume=choice), config=config)

    state = dict(graph.get_state(config).values)
    if state.get("status") == "completed":
        artifact = save_artifact(state)
        print("\n" + "=" * 72)
        print("VALIDATION ROADMAP READY")
        print("=" * 72)
        print(state["thirty_day_roadmap"])
        print(f"\nSaved project brief: {artifact}")
    else:
        print(f"Project paused in phase: {state.get('current_phase', 'unknown')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an evidence-driven startup validation roadmap."
    )
    parser.add_argument("idea", nargs="?", help="The startup idea to investigate")
    parser.add_argument("--project", type=safe_project_id, help="New project ID")
    parser.add_argument("--resume", type=safe_project_id, help="Resume a saved project")
    parser.add_argument("--choice", help="Hypothesis number or founder feedback")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.project and args.resume:
        raise SystemExit("Use either --project or --resume, not both.")

    project_id = args.resume or args.project or default_project_id()
    config = {"configurable": {"thread_id": project_id}}

    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        graph = build_graph(SqliteSaver(connection))
        if args.resume:
            snapshot = graph.get_state(config)
            if not snapshot.values:
                raise SystemExit(f"No saved project named '{project_id}'.")
            if snapshot.values.get("status") == "completed":
                artifact = save_artifact(dict(snapshot.values))
                print(f"Project '{project_id}' is already complete: {artifact}")
                print(snapshot.values.get("thirty_day_roadmap", ""))
                return
            result = graph.invoke(None, config=config)
        else:
            idea = args.idea or input("Startup idea: ").strip()
            if not idea:
                raise SystemExit("A startup idea is required.")
            print(f"\nProject: {project_id}")
            result = graph.invoke(
                {
                    "project_id": project_id,
                    "startup_idea": idea,
                    "goal": (
                        "Identify the highest-value problem to validate before "
                        "building an MVP."
                    ),
                    "current_phase": "planning",
                    "status": "running",
                    "positioning_attempts": [],
                    "positioning_iteration": 0,
                    "positioning_threshold": 8.0,
                    "positioning_max_iterations": 3,
                },
                config=config,
            )
        finish_project(graph, config, result, args.choice)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
