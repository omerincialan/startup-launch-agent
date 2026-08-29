# Startup Launch Agent Demo

A LangGraph vertical slice that turns a startup idea into competing problem
hypotheses, pauses for a founder decision, and produces an evidence-driven 30-day
validation roadmap.

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

## Demo story

1. Enter an idea and watch six visible phases progress.
2. Compare three meaningfully different hypotheses.
3. Make the strategic decision as the founder.
4. Show the generated validation plan and 30-day task roadmap.
5. Open the saved Markdown brief and explain that future company-building phases
   can be added as subgraphs after validation gates are passed.
