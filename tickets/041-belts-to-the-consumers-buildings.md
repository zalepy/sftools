# 041 — Belts matched to the consumer's input side (logistics mode)

**Type:** feature · **Priority:** P2 · **Status:** Open · **Related:** [033](done/033-logistics-mode.md), [036](done/036-logistics-editing-issues.md)

## Problem
On a node's output side, an exit to a consumer is one sink of the consumer's whole rate, with a merger built in: all the belts brought to it share that rate as one pool. In the game, each of those belts goes somewhere on the consumer's input side, often to its own buildings, and takes only what those buildings use.

Example (AW tab): 8 Stator Assemblers (40/m) feed Motor 27/m on three belts: b1+b2, b3+b4, and b5 plus a split of b8. Motor runs 2 buildings at 100% (10/m Stator each) and one at 70% (7/m). In the game the first two belts carry 10/m each, so b1–b4 send a full 5/m, and the third carries 7 of its 8.33. The zoomed-in view instead shares the 27 over the pool: 9.33 / 9.33 / 8.33, so b1–b4 show 4.67/m.

(Before this, the pool's shares didn't even settle and the exit showed 26.33 of 27 with a "short" warning; fixed separately, so the pooled numbers now add up.)

## Goal
The flows on a producer's output side follow where each belt goes on the consumer's input side, so each building sends what is really taken from it.

## Notes
- An exit (out) and the matching entry (in, `e|<producer>|<item>`) are two ends of the same belts. Today each has `lines` from `belts_needed`, set independently. They need a shared belt count and a matching: belt k of the exit is belt k of the entry. Let the user set the count (more belts than needed, as in the example), on either side.
- The consumer's input side decides what each arriving belt can take (simulated with its own layout: what the buildings it reaches use). Those become per-belt limits for the exit on the producer's side, instead of one pooled rate. And what the producer sends per belt is what that entry gets.
- Both sides are simulated separately today (`simulate` per side). Cross-side, it's a fixed point over the production graph: consumers' acceptance flows back to producers, producers' supply flows forward. The production graph is a DAG, so an order (consumers first for acceptance, then producers for supply) repeated until stable should do, with the same round cap and warning as `simulate`.
- An edited layout on either side may stop fitting when the belt count changes: reset it with a reason, as now (`logistics_resets`).
- UI: show on an exit which belt goes where ("belt 2 → Motor b2"), and the same on the entry; the warnings should name the belt.
- The demand exit and the Sink have no input side: they stay pooled.
- By-products used as supply (`byproduct.used`) feed a consumer's input side too; they should follow the same rule.
