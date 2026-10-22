# 054 — Split factory_graph.py: calculation and UI view

**Type:** refactor · **Priority:** P3 · **Status:** Done

## Goal
`domain/models/factory_graph.py` (614 lines) was the one file besides the allowed ones over the 500-line limit (ticket 052). It did two things: calculating the plan, and turning the result into what the UI gets.

## Decisions (agreed with the user, 2026-10-22)
- Split along that line, with no behavior change. `FactoryGraph` keeps the calculation (merges, propagation, by-product loops, scaling, and `resolved_byproduct_choices`, which is part of the plan the client keeps).
- The UI side becomes functions of the graph in `domain/models/graph_view.py`, not a second class.

## Notes
- Implemented 2026-10-22: `factory_graph.py` 428 lines, `graph_view.py` 202. `FactoryGraph.get_ui_data()` is now `graph_view.ui_nodes(graph)`, with `byproducts_of`, `sink_node`, `inbound_node`, `derivation` and `serialize_node`. The Sink and inbound-node constants moved with them.
- `FactoryGraph._external` became the module function `external_demand(node)`, as both halves use it.
- 128 unit and 62 browser tests pass; `check_sizes.py` now flags nothing outside its allowed list.
