# Stage-1 bake-off pins (technology note 2026-10-10-faster-openrouter-models.md)

Each config has `<letter>_answer.json` (graph agent: steps and FINAL answer) and
`<letter>_cypher.json` (`cypher_rag_plant` Cypher writer, reasoning effort low).
All are `ModelPin` JSON, max_output_tokens 16384. Hosts are OpenRouter endpoint tags from
`docs/private/30-experiments/openrouter-endpoints-2026-10-10.json`, sent as
`provider.order=[tag]`, `allow_fallbacks=false`, plus `require_parameters=true`.

| Config | Model id | Host tag | Final effort | temperature / seed | Strategy |
|---|---|---|---|---|---|
| A baseline | z-ai/glm-5.3-flash | none (unpinned) | model default (max) | 0.0 / 0 | graph_agent_low_steps |
| B host lever | z-ai/glm-5.3-flash | fireworks | model default (max) | 0.0 / None | graph_agent_low_steps |
| C effort lever | z-ai/glm-5.3-flash | fireworks | high | 0.0 / None | graph_agent_low_steps |
| D | anthropic/claude-haiku-5.5 | anthropic | low | None / None | graph_agent_low_steps |
| E | deepseek/deepseek-v4.1-flash | parasail/fp8 | low | 0.0 / 0 | graph_agent_low_steps |
| F | openai/gpt-6-luna | openai | low | None / 0 | graph_agent_low_steps |
| G | openai/gpt-oss-120b | cerebras/fp16 | low | 0.0 / 0 | graph_agent_low_steps |

Strategy: `graph_agent_low_steps` (graph_agent v2 with `step_effort="low"`) for every config. It
overwrites `extra.reasoning` with `low` on STEP requests (`_step_pin`, qa/agent/loop.py) and
leaves the FINAL answer on the pin's own reasoning, which is what A, B (model default) and C
(high) need. D-G are low everywhere, so the override changes nothing for them. No config here
turns reasoning off; one that did would need `graph_agent` (`step_effort="default"`).

Notes: A's answer pin is byte-for-byte `pin_default.json` and its Cypher pin is `pin_low.json`.
B and C share the same Cypher pin content (GLM @ fireworks, low). Seed/temperature are None
exactly where the endpoint snapshot says the host lacks them (Fireworks GLM: seed; Anthropic:
both; OpenAI Luna: temperature). `ModelPin` supports every field the note asked for.
