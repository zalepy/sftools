# 038 — Node tab in the side panel

**Type:** feature · **Priority:** P3 · **Status:** Done

> **Done (2026-10-14).** The side panel has three tabs: Planner (demands, inbound production, New Plan / Export / Import, the Clear buttons, logistics settings), Node (the selected node, by-product or logistics node) and Colors. Clicking something in the graph opens the Node tab; with nothing selected it says what to click. `panel.showTab`. Browser test: `test_selecting_opens_the_node_tab`.

## Request
Split the Planner tab: the plan-wide controls stay under Planner, the Selected Node controls move to their own tab, "Node".
