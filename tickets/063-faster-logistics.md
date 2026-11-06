# 063 — Faster logistics: drop the work nobody reads

**Type:** performance · **Priority:** P3 · **Status:** Open · **Related:** [034](034-balancers.md), [042](done/042-push-output-sides.md)

## Goal
`/api/calculate` spends most of its time in the logistics simulation. Remove the work whose result is thrown away, without a second way of computing flows.

## Measured
One end-game plan (1/min each of Nuclear Pasta, Thermal Propulsion Rocket, Ballistic Warp Drive, Assembly Director System, Singularity Cell; by-products `use`): 741 nodes, default layouts, about 5 MB of JSON, medians of 8 requests with a fixed hash seed.

Under cProfile, `attach_logistics` is 85% of `calculate`, `simulate` 72%, `build_plan` 9%. `simulate` runs about 2,243 times per request, in 2 or 3 rounds each.

| Variant | ms | Response |
|---|---|---|
| Today | 238 | |
| Skip the unused input pass | 202 (-15%) | identical |
| Stop after 2 rounds | 219 (-8%) | identical |
| Both | 189 (-20%) | identical |
| Stop after 1 round | 179 (-25%) | wrong on 44% of belts |

## Do
1. **Skip the unused pass.** The first input-side `simulate` in `attach_logistics` is only read for edges in `matched` (the plan sets their belt count). Run it only for sides with a matched entry: with no belt counts set, that's a third of all the calls. Needs a test with a plan that sets belt counts, as the measured plan doesn't reach this path.
2. **Cache the fluid check.** `is_fluid` (the lambda in `routes.py`) is called about 35,000 times per request, about 4% of the time, for an answer that depends only on the item.

## Decided against, for now
- **Computing flows directly, for shapes that allow it.** A splitter tree could go backward once, then forward once, but one round is about the most it could save (-25%, on those shapes only), and it adds a second path that has to agree with `simulate`. Mergers and splitters together do depend on each other, and so will 034's loops, so `simulate` stays anyway.
- **Capping rounds at 2.** It held for default layouts on one plan. Nothing shows it holds for edited layouts or overflow splitters, and the saving is small.

## Notes
- Round 1 can't be enough: the first forward pass only knows belt capacities, not what the sinks take. The extra round in the 3-round calls only confirms.
- 034's order for loops (Gauss-Seidel until stable) means more rounds. Keep today's ordered pass for layouts without a cycle.
- The numbers are from after the hash-seed fix (`tests/unit/test_determinism.py`); before it, a plan's result could change per process, which made timings hard to compare.
