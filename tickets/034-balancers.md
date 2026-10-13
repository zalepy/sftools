# 034 — Balancers with loop-backs (logistics mode)

**Type:** feature · **Priority:** P3 · **Status:** Open · **Related:** [033](done/033-logistics-mode.md)

## Goal
Logistics nodes allow only trees today: a belt that leads back to where it started is refused. Real load balancers loop belts back (the classic 5- and 7-way), so allow loops in the zoomed-in view and simulate them.

## Notes
- `simulate` already repeats until the flows settle; with loops it needs an order that tolerates cycles (e.g. Gauss-Seidel over all nodes until stable) and a cap with a warning when it doesn't settle, as for by-product loops (032).
- `validate` (server) and `problem` (browser) refuse loops today; lift that together.
- Maybe offer common balancers as ready-made parts (n:m), rather than only drawing them belt by belt.
