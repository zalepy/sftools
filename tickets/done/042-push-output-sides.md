# 042 — Output sides pushed, input sides pulled (logistics mode)

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** [033](done/033-logistics-mode.md), [041](done/041-belts-per-edge.md)

## Problem
Both sides of a node are simulated by pull: each exit takes at most what its edge needs (and, on a matched edge, what the consumer's entry lets through), and the rest backs up at the buildings. On an output side that hides how the layout splits what the buildings make: a splitter that sends 4.5/min to an exit that needs 4.33 shows "4.33 of 4.33", and the other exit is short with no sign of where the 0.17 went.

## Decision
- **Output sides push**: the buildings put out all they make; splitters share it evenly among outputs that aren't full (belt capacity only), so an exit shows what lands on its belt, which can be more than its edge needs. A smart (overflow) splitter is the exception by design: its main outputs back up when the exits they reach have what they need, and only then does it overflow.
- **Input sides pull**, as now: each entry brings what its exit pushes, and the buildings take what they need; the rest backs up on the belt.
- The output side no longer depends on the consumer's side: the coupling of 041 runs one way, the output sides first, then the input sides with what each belt brings.

## Plan
- `simulate`: on an output side, splitters and buildings see only how much room the belts have (`room`, from belt capacities, exits unlimited); overflow splitters keep the pull acceptance (`accept`, exits taking their edge's rate) for their main outputs. Exits report all they get.
- Warnings on exits: short only ("gets 4.33 of 4.67/min"). More than needed isn't a problem in itself (it backs up at the consumer), and a node with whole buildings usually makes some more than its edges take; it shows in the view instead.
- `attach_logistics`: simulate the output sides, hand each belt's push to its entry (a bundle: shared over the entries as they take it, the rest evenly), then the input sides. Exits get `limit` (what the entry takes) for display.
- Zoomed-in view: an exit getting more than it needs is amber ("4.50 of 4.33").
- Suggested layouts unchanged.

## Done (2026-10-17)
- `simulate`: output sides pushed (`room` for splitters and buildings, `accept` only for an overflow splitter's main outputs); exits report all they get, `pool_delivered` is their sum. The `limits` argument is gone.
- `attach_logistics`: output sides once, then input sides with what each belt brings (bundles: over the entries as they take it, the rest evenly up to belt capacity, over rounds); a matched exit's `limit` is what its entry takes, for display.
- Zoomed-in view: an exit getting more than the other end takes is amber (not the Sink).
- In the AW tab: Stator to Motor on 3 belts shows 10 / 10 / 7.5 (the third Motor takes 7). Four new warnings, all from edited AW output layouts that split a building evenly between two consumers (e.g. Rotor building 7: 2.5 each to Smart Plating, which needs 2, and Motor).
