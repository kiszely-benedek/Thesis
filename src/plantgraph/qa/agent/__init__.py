"""The graph-tool agent: a language model composes plant-API primitives to gather evidence.

Design: `question-aware-retrieval.md` §5 and §6.1; ADR-0034.

An *agent* here is a short loop. The model sees the question and a list of graph tools
(`plant_api/`), replies with one tool call at a time, reads the result, and says `done` when it
has gathered enough. The agent never writes the answer: what it gathered goes to the shared
final-answer step, like every other strategy's context.

- `models`: loop parameters, one step of the loop, and the loop's outcome.
- `actions`: reads one model reply as a tool call or `done`.
- `loop`: the bounded loop itself (pure given a sender; no I/O of its own).
- `prompts`: the system prompt and the first user message.
- `seed`: the free starting map of `hier_agent` (anchors plus the rule classifier's program).
- `strategies`: `GraphAgent` and `HierAgent`, the two `Strategy` implementations.
"""
