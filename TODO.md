# TODO

Ideas and considerations that aren't pressing enough for a ticket. Promote an entry to `tickets/` when it's picked up.

## Planner

- **Heavy Oil Residue solver.** Heavy Oil Residue (a fluid by-product, e.g. of Plastic and Rubber) can't be sunk, so today it goes to the Sink as a red placeholder. The general solution in the game is to refine it into Fuel (Fuel recipe at a Refinery) and burn that in Fuel-Powered Generators. Offer to compute that instead: the Refineries and Generators needed for the residue, and the power they make.

## To investigate

- **Supply-driven planning.** Start from a supply instead of a demand: what a given input can feed. The main use is energy, e.g. how many generators would fully use this coal mine or this oil field. Mixing it with demand-driven planning in one graph is the hard part: it would be tricky to control how much each side drives the graph. It may need to be a separate mode or view.
