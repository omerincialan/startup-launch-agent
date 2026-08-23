# Startup Agent TODO

## Next milestone: stabilize the demo

- [ ] Refactor `agent.py` into the intended modules:
  - `coordinator.py`
  - `state.py`
  - `phases/research.py`
  - `phases/discovery.py`
  - `phases/validation.py`
- [ ] Fix UI phase tracking so all six displayed phases match backend state transitions.
- [ ] Add automated tests for:
  - New project creation
  - Founder-decision interrupt and resume
  - Completed project resume
  - Artifact generation
  - API validation and error responses
- [ ] Add a dependency manifest (`pyproject.toml` or `requirements.txt`).
- [ ] Run and document a complete CLI and browser end-to-end smoke test.

## Product expansion

- [ ] Add validation decision gates: continue, revise, or stop.
- [ ] Implement the MVP planning subgraph.
- [ ] Implement the experiments subgraph.
- [ ] Implement the competition-analysis subgraph.
- [ ] Implement the go-to-market subgraph.
- [ ] Implement the fundraising subgraph.
- [ ] Define how projects advance between subgraphs while preserving checkpoints and artifacts.

## Production readiness

- [ ] Add structured logging and clearer model/API failure handling.
- [ ] Add configuration validation for API keys and model selection.
- [ ] Decide whether the dependency-free local server is sufficient or should be replaced with a production web framework.
- [ ] Add deployment, persistence, backup, and access-control plans before exposing the app beyond localhost.
