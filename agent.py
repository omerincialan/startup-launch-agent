"""Demo-ready, long-horizon startup launch agent.

This vertical slice takes a founder from an idea to a selected problem hypothesis
and an evidence-driven 30-day validation roadmap. LangGraph checkpoints make the
human decision durable, so a project can be stopped and resumed later.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


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
    validation_plan: str
    thirty_day_roadmap: str
    current_phase: str
    status: str


def make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("STARTUP_AGENT_MODEL", "gpt-5.6-terra"),
        temperature=0,
    )


def run_llm(prompt: str) -> str:
    response = make_llm().invoke(prompt)
    return str(response.content)


def announce(step: int, title: str) -> None:
    print(f"\n[{step}/6] {title}", flush=True)


def plan_research(state: StartupState) -> dict[str, str]:
    announce(1, "Planning the opportunity research")
    prompt = f"""
You are a startup research agent. Build a concise research plan for this idea:

{state['startup_idea']}

Goal: {state['goal']}

Investigate target users, their jobs-to-be-done, recurring workflow problems,
existing alternatives, likely competitors, and areas where AI could create
measurable value. State what evidence is needed. Do not recommend a product yet.
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
workflows, painful or repetitive tasks, communication and lead-management tasks,
existing software categories, and gaps in current solutions. Label every material
claim as either OBSERVATION or ASSUMPTION. This is preliminary research, not proof.
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
        "current_phase": "validation_planning",
    }


def create_validation_plan(state: StartupState) -> dict[str, str]:
    announce(5, "Creating the validation plan")
    prompt = f"""
You are a customer-discovery strategist.

Startup idea: {state['startup_idea']}
Founder selection or feedback: {state['selected_hypothesis']}
Candidate hypotheses:
{state['hypotheses']}

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
    announce(6, "Turning strategy into a 30-day roadmap")
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
    builder.add_node("validation_plan", create_validation_plan)
    builder.add_node("roadmap", create_thirty_day_roadmap)
    builder.add_edge(START, "plan_research")
    builder.add_edge("plan_research", "research")
    builder.add_edge("research", "synthesize")
    builder.add_edge("synthesize", "hypotheses")
    builder.add_edge("hypotheses", "human_selection")
    builder.add_edge("human_selection", "validation_plan")
    builder.add_edge("validation_plan", "roadmap")
    builder.add_edge("roadmap", END)
    return builder.compile(checkpointer=checkpointer)


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
                },
                config=config,
            )
        finish_project(graph, config, result, args.choice)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
