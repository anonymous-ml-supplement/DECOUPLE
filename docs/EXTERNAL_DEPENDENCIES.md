# External dependencies for full historical re-execution

The one-command paper reproduction is self-contained apart from standard Python packages in `requirements.txt`. Full model-facing re-execution additionally requires external benchmark/model repositories and service access that are not redistributed in this anonymous snapshot.

| Interface used by retained source | External dependency | Purpose |
|---|---|---|
| `bfcl_eval` | Berkeley Function Calling Leaderboard repository | BFCL task/evaluator utilities and official multi-turn checker |
| bundled `pipeline/vendor/bfcl_tool_conversion/` | first-party frozen compatibility helper included here | BFCL tool-schema conversion for the OpenAI Responses interface |
| bundled `bfcl_docker_trajectory_worker.py` | first-party frozen worker included here | BFCL stateful Docker execution bridge |
| `model_utils` | Skywork PRM inference repository used by ToolPRMBench-compatible scoring | Skywork-o1-Open-PRM-Qwen-2.5-7B scoring |
| `prm_evaluation` | GenPRM inference repository | GenPRM-7B Math-Shepherd scoring |
| `openai`, `tiktoken` | Python packages | frozen generator/API interface and local 256-token scientific window |
| `torch`, `transformers` | Python packages | reward-model inference |

The frozen compute authority records GenPRM-7B model revision `0ea3fa755896b5448a33458fd0b010501dbea21e` and the Skywork snapshot identifier `b89a8956c8a39c75f8cc25064455c33f8f8831f2`. These identifiers are provenance, not a claim that every external service can be recreated from this archive alone.

`requirements-full.txt` covers the directly imported model-facing Python packages in this repository. The external benchmark/model repositories above must still be installed separately for Tier C historical re-execution.

Version provenance caveat: `requirements-full.txt` carries lower bounds only and is not the historical model-execution lock. `requirements.txt` pins only validated offline direct dependencies; see `docs/ENVIRONMENT.md`.
