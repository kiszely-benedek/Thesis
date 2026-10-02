"""The plant API: six composable graph primitives over the resolver's output.

Design: `question-aware-retrieval.md` §3.

A *P&ID* (piping and instrumentation diagram) is one engineering drawing page;
a plant is many pages. The resolver stitches the pages together, and this
package presents the result as **one connected graph of plant items**:

- `model`: the item, edge and filter types, and the one error type.
- `contraction`: merges repeated drawings of one item and joins off-page
  connector pairs, so a walk crosses sheets as if they were one page.
- `item_graph`: the merged graph, built once per corpus from a `GraphView`.
- `traversal`: pure breadth-first closure and shortest path.
- `results`: what a primitive returns, and how it renders to bounded text.
- `primitives`: `PlantApi`, the six operations with result handles.
- `tool_registry`: the primitives as named tools with argument schemas, for an agent.

Nothing here reads the answer key (`SplitManifest`, `OccurrenceMap`, the gold plant).
"""
