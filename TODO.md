# Startup Agent TODO

## Stabilize the demo

- [ ] Refactor `agent.py` into `coordinator.py`, `state.py`, and the relevant `phases/` modules.
- [ ] Align browser UI phase tracking with backend state transitions.
- [ ] Add automated tests for project creation, founder decisions, resume behavior, artifact generation, and API errors.
- [ ] Add a dependency manifest (`pyproject.toml` or `requirements.txt`).
- [ ] Run and document complete CLI and browser smoke tests.

## Expand the product

- [ ] Add validation decision gates: continue, revise, or stop.
- [ ] Implement the MVP planning subgraph.
- [ ] Implement the experiments subgraph.
- [ ] Implement competition analysis.
- [ ] Implement the go-to-market subgraph.
- [ ] Implement the fundraising subgraph.
- [ ] Preserve checkpoints and artifacts as projects advance between phases.

## Prepare for production

- [ ] Add structured logging and clearer model/API error handling.
- [ ] Validate API keys, configuration, and model selection at startup.
- [ ] Decide whether to keep the local server or adopt a production web framework.
- [ ] Define deployment, persistence, backup, and access-control plans.
