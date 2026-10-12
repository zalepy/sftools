# 018 — UI and feature backlog (from scratch.txt)

**Type:** feature · **Priority:** P3 — split into separate tickets when picked up · **Status:** Done

- [x] Collapsible side panel, to give the graph more room (done 2026-10-12)
- [x] "Last building" clock speed: moved to [023](done/023-clock-speeds.md)
- ~~Per-building configurator: set each building's clock individually~~ dropped (2026-10-12); 023's clock groups could still store it
- [x] Node splitting: done in [021](done/021-node-splitting.md)
- [x] "External input" nodes (items supplied from outside the plan): "Supplied from outside" in the recipe list; the node keeps its rate and loses its buildings, inputs and clocks. Sky-blue border (done 2026-10-12)
- [x] Separate border color for external-demand nodes: purple, also on a merge group that includes a demanded node (done 2026-10-12; the old branch `distinct_extrenal_demand` was not used)
- [x] Dark text on bright node colors: light or dark text, whichever has the higher WCAG contrast (done 2026-10-12)
