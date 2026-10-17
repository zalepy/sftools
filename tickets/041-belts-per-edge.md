# 041 — Belts per edge, matched across both ends (logistics mode)

**Type:** feature · **Priority:** P2 · **Status:** Open · **Related:** [033](done/033-logistics-mode.md), [034](034-balancers.md), [036](done/036-logistics-editing-issues.md)

## Problem
An edge of the production graph is planned as one bundle of belts, its count set by the rate alone (`belts_needed`). On the producer's output side the edge is one exit, a sink of the consumer's whole rate with a merger built in: every belt brought to it shares that rate as one pool. On the consumer's input side it is one entry. Neither end knows where each belt goes at the other end.

But often more belts than needed is the better build. Rotor takes 100 Screws/min per building, while Cast Screws make 50 per building: run two Screws producers onto a Mk.2 belt to each Rotor, and skip the splitters and mergers a single belt would need. That's the user's call (if the two are far apart, one belt may be better), so the count has to be editable.

Example (AW tab): 8 Stator Assemblers (40/m) feed Motor 27/m on three belts: b1+b2, b3+b4, and b5 plus a split of b8. Motor runs 2 buildings at 100% (10/m Stator each) and one at 70% (7/m). In the game the first two belts carry 10/m each, so b1–b4 send a full 5/m, and the third carries 7 of its 8.33. The zoomed-in view shares the 27 over the pool instead: 9.33 / 9.33 / 8.33, so b1–b4 show 4.67/m.

(Before `9eca64c` the pool's shares didn't even settle, and the exit showed 26.33 of 27 with a "short" warning.)

## Decision
Keep the zoomed-in views per node side (inputs, outputs), and make the edge the interface between them. Splitters and mergers belong to a side: one splitter can feed two consumers (Stator: Motor and the demand), and one building takes inputs from several edges. A view per edge couldn't hold them. It also keeps balancer loops (034) inside one side's simulation.

## Plan
- **Belt count per edge**, in the plan: `logistics.edges: {"<producer>><consumer>|<item>": n}`. The default is `belts_needed` (as now). More is allowed; fewer than the rate needs gives a warning. Edited on the selected edge (side panel) and with +/− on a belt end in the zoomed-in view; both change the same entry. Undo/redo, tabs and files carry it with the rest of the plan.
- **One node per belt at each end**: "to Motor · belt 2/3" on the output side, "from Stator · belt 2/3" on the input side. Belt k at one end is belt k at the other (which buildings it reaches is the input side's layout). Each belt end takes exactly one belt: the merger built into an exit (036) goes, so mergers are explicit and the splitter/merger count changes. Clicking a belt end could open the other side's view with that belt highlighted.
- **Simulation across the two sides**: each side is still simulated on its own; on top, each belt's limit on the producer's side is what the consumer's input layout lets it take, and what it carries is what that entry gets. Repeat over the production graph (a DAG) until the flows settle, with the same round cap and warning as `simulate`. This makes the AW case read 10 / 10 / 7.
- **Main graph**: the edge label shows the count ("3× Mk.2", as now). The amber `multi` highlight means only that the rate forces more than one belt of the top tier, not a count the user chose.
- **Pooled ends**: edges to the demand and to the Sink have no input side, so they stay pooled at that end; inbound production has no producer side, so its belts are set at the consumer only.
- **By-product edges** get the same per-edge count and follow the same rules.
- **Edited layouts**: one that connects to the old single exit/entry keeps its belts when the count is 1 (moved to the belt end); otherwise it is reset with a reason, as now (`logistics_resets`). The same applies when the count changes later.

## Open
- Matching belts by number (k = k) should do, since the input layout decides where each belt goes; pair them explicitly only if that turns out to be confusing.
