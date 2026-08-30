# Startup Launch Agent Demo

A LangGraph vertical slice that turns a startup idea into competing problem
hypotheses, pauses for a founder decision, improves positioning through an
evaluate-and-retry loop, and produces an evidence-driven 30-day validation roadmap.

## Run the demo

Activate the existing environment and start a named project:

```bash
source .venv/bin/activate
python agent.py "A tool that helps small businesses follow up with leads" --project lead-demo
```

The agent pauses after presenting three hypotheses. Enter `1`, `2`, `3`, or give
written feedback. The completed brief is saved under `artifacts/` and the workflow
state is checkpointed in `startup_agent.db`.

### Browser interface

Launch the dependency-free web UI:

```bash
source .venv/bin/activate
python web_ui.py
```

It opens at `http://127.0.0.1:8000`. Use `python web_ui.py --no-browser` when you
do not want it to open a browser automatically.

Resume an interrupted project:

```bash
python agent.py --resume lead-demo
```

For a scripted demo, provide the founder decision up front:

```bash
python agent.py "A tool that helps small businesses follow up with leads" \
  --project lead-demo-2 --choice 2
```

Set `OPENAI_API_KEY` in `.env`. Optionally set `STARTUP_AGENT_MODEL` to override
the default model.

## Positioning evaluation

Verify the recursive loop without API calls:

```bash
python evaluations/run_positioning_eval.py --mock
```

Run the live benchmark on three fixed startup ideas:

```bash
python evaluations/run_positioning_eval.py
```

The command prints machine-readable JSON with per-case scores,
`aggregate_score`, and `pass_rate`. AutoLab should use the live command as its run
command. The loop passes at 8/10 or stops after three attempts.

## AutoLab configuration

After the live benchmark works locally, initialize this repository with `autolab
init` and use these settings:

- **Objective:** Maximize the `aggregate_score` emitted by the positioning
  evaluation while preserving truthful, specific positioning.
- **Setup command:** `python -m pip install -r requirements.txt`
- **Run command:** `python evaluations/run_positioning_eval.py`
- **Primary metric:** `aggregate_score` (higher is better)
- **Secondary metrics:** `pass_rate` (higher is better) and iterations (lower is
  better when quality does not decrease)
- **Stop policy:** Stop when aggregate score no longer improves meaningfully or
  the configured cost limit is reached.

Use these constraints so experiments remain comparable:

- Do not modify benchmark cases, scoring dimensions, threshold, or iteration cap.
- Do not hardcode benchmark answers or scores.
- Do not weaken the evaluator or bypass live model calls.
- Preserve the existing CLI, browser workflow, human checkpoint, and API safety.
- Product changes may modify positioning prompts and graph logic only when the
  same evaluation command continues to run successfully.

## Demo story

1. Enter an idea and watch eight visible phases progress.
2. Compare three meaningfully different hypotheses.
3. Make the strategic decision as the founder.
4. Show the positioning evaluation history, validation plan, and 30-day roadmap.
5. Open the saved Markdown brief and explain that future company-building phases
   can be added as subgraphs after validation gates are passed.
