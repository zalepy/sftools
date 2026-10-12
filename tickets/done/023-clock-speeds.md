# 023 — Clock speeds per node (replaces building overrides)

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** 018, 026, 027, 028

> **Redesigned (2026-10-12)** in a design session with the user. The first version computed the last building's clock automatically; the user wants no automatic adjustment, ever.

> **Done (2026-10-12).** As designed below. Plan entry `clocks`; buildings, clock groups and shards on each node; label shows `(9× Constructor)` with a fourth line such as `8×100% + 1×200% · 2 shards` when any clock differs from 100%. Power exponent 1.321928 (satisfactory.wiki.gg, "Clock speed", since Update 7), still worth confirming in game. Plan-level overrides are retired; the engine keeps `ProductionNode.user_scale` as a fixed-scale primitive for low-level tests (a possible later cleanup). Tests: `tests/unit/test_clocks.py`; browser tests for applying and clearing clocks, saved overrides dropped with a notice, and no round-up toggle.

## Principles (from the user)
- **The tool never adjusts on its own.** Changes happen only when the user sets something, or explicitly runs an optimization (027).
- **Building counts are never edited directly**, as in the user's spreadsheet, where typing over a computed cell destroys its formula. The count is always calculated from the demand and the clocks, so it keeps following demand.
- **Clocks are what the user sets.** Example: 144 Iron Rod/min needs 9.6 buildings. 10 buildings at 100% is often what's wanted: the 0.4% extra rods go to a buffer, and the inputs stay on round numbers (120 + 30 ore). Another time, the last building may not fit physically, so it runs at 200% instead.

## Design
- Per node, both optional:
  - **clock**: the clock for all buildings, default 100%.
  - **last clock**: the last building's clock, default the same as clock. Never calculated.
- **Buildings** (read-only) = `ceil((demand − rate × last) / (rate × clock) + 1)`, at least 1 when there is demand. This is the spreadsheet's formula. With both clocks at 100% it is today's rounded-up count.
- **Output** = `rate × (clock × (buildings − 1) + last)`, which is at least the demand. The status dot shows the surplus as now. Inputs follow what the buildings use, so a clock change cascades down the chain.
- **Stored as groups**, `clocks: {node_id: [{"count": n, "clock": c}, ...]}`, where the last group has no count ("the rest"). The panel shows two fields, all and last, which covers today's needs. The format also covers "last two at 150%" and a later per-building configurator (018) without changing.
- **Power** follows the clocks: `unit MW × clock^k` per building, plus a **power shard** count (1 per 50% above 100%, up to 3 per building at 250%). Verify `k` in game: the spreadsheet uses 1.6, and 1.0 may have changed it to about 1.32 (log2 2.5). Keep it one constant.
- Clock range 1%–250%. Showing which clocks are unlocked yet (mid-game for above 100%) is out of scope.
- **Merged nodes:** the clocks are on the merge target (the shared buildings). **Split parts:** each part has its own.

## Retired
- **"Round Up Buildings" toggle:** buildings are always whole. The engine keeps an exact, fractional mode for the unit tests' balance checks; the UI no longer offers it.
- **Override Scale Factor** (a fractional building count): replaced by clocks. Saved overrides are dropped once, with the usual "no longer match" notice. They set a building count, which is no longer something the user sets.

## Display
- Node label: `n × 100%`, or `9 × 100% + 1 × 60%` when the last clock differs; shards if any.
- Panel: buildings (read-only), clock, last clock, output, surplus, power, shards.

## Tests
- Unit: buildings and output from clocks, including the examples above; power and shards; merged and split nodes; saved overrides reported.
- Browser: set clocks and see the label, buildings and the downstream change; no building-count field and no round-up toggle.
