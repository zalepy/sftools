# 035 — Legend

**Type:** feature · **Priority:** P3 · **Status:** Done

> **Done (2026-10-13).** A Legend button in the header shows or hides a legend over the top right of the graph, in both modes; the choice is remembered in the browser (`sf_legend_shown`). It explains the node borders (production, demanded, supplied from outside or inbound, clocks set, selected, the Sink and its fluid warning), the status dot, the edges (supply, by-products used or sunk, fluids to the Sink, loops), label marks ((A), split parts, clock groups), and, in logistics mode, the logistics nodes and belt tiers. A zoomed-in logistics node covers it. Browser test: toggling, remembered after a reload, logistics entries only in logistics mode.

## Request
Add a legend pane, maybe on the right side, with the common color annotations (purple border: external demand, blue border: external supply, ...). Show and hide it with a toggle in the header. Probably works in both modes.
