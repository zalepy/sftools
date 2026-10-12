# 023 — "Last building" clock speed

**Type:** feature · **Priority:** P2 · **Status:** Open · **Related:** 018 (moved from its backlog)

## Goal
Run all of a node's buildings at one clock speed except the last, which runs at whatever speed covers the remainder exactly. For example, 5.2 buildings' worth of demand becomes "5 × 100% + 1 × 20%" instead of 6 buildings, each at 86.7%. This is how the game is usually built: whole buildings at a round clock, plus one tuned building.

## Prior art: the planning spreadsheet
The author's Google Sheets planner has this as two columns per item: `ocall` (the clock for all buildings) and `oclast` (the clock for the last one):
- buildings: `n = roundup((target − rate × oclast) / (rate × ocall) + 1)`
- output: `rate × ocall × (n − 1) + rate × oclast`, and each input likewise
- power: `unit MW × ocall^1.6 × (n − 1) + unit MW × oclast^1.6`

In the sheet the user sets `oclast`. Here it can be computed: `oclast = (demand − rate × ocall × (n − 1)) / rate`, with `n = ceil(demand / (rate × ocall))`.

## Design sketch
- New per-node setting, e.g. `clocks: {node_id: <clock for all buildings, default 1.0>}` in the plan. The last building's clock is derived from the demand. Clocks above 1 need power shards (up to 2.5 in 1.0).
- The node shows "n × A% + 1 × B%", and the status dot compares the planned output with the demand as now.
- `building_scale` stays the number of building-equivalents, `A × (n − 1) + B`, so the downstream maths doesn't change.
- **Power:** a clock changes power non-linearly. The game's exponent should be checked: the sheet uses 1.6, and I believe 1.0 changed it to about 1.32 (log2 2.5). sftools power is linear in `building_scale` today, which treats fractional scales as more buildings.

## Questions
- How does it combine with an override (a fixed building scale)? Probably: the override sets the total, and the clock decides how it's split into buildings.
- Should merged nodes and split parts each have their own clock? Probably yes, since each is built separately.
