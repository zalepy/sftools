# 057 — Supply-driven power plans: use the inbound as the limit

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** [055](055-burn-residue.md), [056](056-reference-layouts.md), [040](040-chain-tab.md), [045](045-move-branch-to-inbound.md)

## Goal
Plan power from a supply: given what a coal or oil field (or a uranium node) gives, how much fuel it makes, how many generators burn it and what that powers. The main use is a small concept plan, e.g. at 1/5 of a layout such as 056, to check flows and compare options. The plan changes often, so it's an ordinary plan with all its tools (recipes, merges, clocks, logistics), not a fixed layout.

The whole plan is driven by its supply. It isn't mixed with demand-driven branches, so nothing has to decide how much each side drives the graph (that was the concern in TODO.md).

## When it applies
- The plan's demand rows are **only fuels**, and it has **at least one inbound row**. Fuels:
  - Fuel-Powered Generator: Fuel, Liquid Biofuel, Turbofuel, Rocket Fuel, Ionized Fuel.
  - Coal-Powered Generator: Coal, Compacted Coal, Petroleum Coke.
  - Nuclear Power Plant: Uranium Fuel Rod, Plutonium Fuel Rod, Ficsonium Fuel Rod.
  - Left out: Biomass Burner fuels (they can't be fully automated) and Alien Power Matrix (late game; maybe later).
- When the rule matches, the panel shows a checkbox **Use inbound as the limit**. The checkbox is shown only then. It's saved in the plan (a flag such as `supply_limit`). With it off, or when the rule no longer matches, the plan works as it does today. A plan can be fuel-only with inbound and still mean "make this much Fuel, partly from this crude".
- The checkbox turns on everything below. The panel names the limiting inbound row (e.g. "Limited by Crude Oil").

## What it computes
- **Demand rates are ratios.** With one fuel, its rate is ignored. With several, their rates give the proportion between them (Turbofuel 2 + Fuel 1 stays 2:1). The demand rows show the computed rates.
- **Every inbound row is a limit.** Grow the demands together (one factor *k*) until the first inbound row is used up:
  1. Run the plan in exact mode at the demand rates as given, and read what it uses of each inbound item.
  2. *k* = the smallest of (inbound rate ÷ use) over the inbound rows. That row is the limit; the others show what's left over.
  3. Run the normal calculation with the demands × *k*.
  The plan is linear in its demands, so merges, recipe switches, by-product uses and loops (031, 032) and residue burning (055) work as before.
- **Side inputs are derived.** Anything not in the inbound rows, e.g. Sulfur for Compacted Coal, Water for the generators, the concrete and steel for fuel rods, gets the amount the plan at *k* needs. Its miners, extractors or production are sized from that, as today.
- **Whole buildings:** the plan uses whole buildings as usual. Rounding up the last building of a node can use a little more than the limit. Then the extraction shows the excess beyond the inbound, the same as an overshoot does today. Fit Last Building (047) trims it by hand. No search for a *k* that fits whole buildings.

## Raw and non-raw inbound rows
- An inbound row of a **raw resource** (Coal, Crude Oil, Uranium, Sulfur, ...) only sets the limit. The plan shows that resource's miners, extractors or wells sized to what it uses. No `inbound:<item>` node is drawn for it, and it isn't a need in the Chain tab.
- A **non-raw** inbound row (e.g. Steel Beam for a fuel rod chain) works as today. It's an `inbound:<item>` node, it's a need in the Chain tab (040), and it's also a limit.

## Generators
- Demanded fuels are burned in **one node per generator type**: Fuel Generators, Coal Generators, Nuclear Power Plants. A generator burns one fuel at a time, so the node shows a count for each fuel (e.g. ⌈Turbofuel / 7.5⌉ + ⌈Fuel / 20⌉), the fuel fed and MW. It replaces the demand circle of each fuel it burns.
- This generalizes the residue's `generators` node (055): when the plan burns Fuel, the residue's Fuel goes to the same Fuel Generators. Residue Fuel is extra power. It doesn't count toward the limit, as it's what's left after the plan's own uses. Outside supply mode, the Fuel Generators appear only for residue, as today.
- **Underfed generators** follow 055 for every type: ⌈fuel / burn rate⌉ at 100%, no clocks (the last one runs with gaps), and MW is the average the fuel gives (fuel/min × MW ÷ burn rate).
- **MW, gross and net:** gross on each generator node; net is gross minus the plan's own consumption, Water Extractors included (the 056 layout shows the same thing as "about 3.1 GW of the 25"). The panel shows both next to the limit: "Limited by Crude Oil · 1,250 MW gross / 1,060 net".
- The scraped data has only the Nuclear Power Plant (2,500 MW, 240 m³/min water). The generators and burn rates are constants, in a pure module with a unit test (checked against satisfactory.wiki.gg, 2026-10-24):

  | Generator | MW | Fuel per minute at 100% | Water per minute |
  |---|---|---|---|
  | Fuel-Powered | 250 | Fuel 20, Liquid Biofuel 20, Turbofuel 7.5, Rocket Fuel 25/6 (≈4.167), Ionized Fuel 3 | — |
  | Coal-Powered | 75 | Coal 15, Compacted Coal 50/7 (≈7.143), Petroleum Coke 25 | 45 m³ |
  | Nuclear Power Plant | 2,500 | Uranium Fuel Rod 0.2, Plutonium Fuel Rod 0.1, Ficsonium Fuel Rod 1 | 240 m³ |

- **Water** for Coal Generators and Nuclear Power Plants is a demand of those nodes, so they take part in the calculation (055's node is only added to the view). The normal expansion turns it into Water Extractors, with their power. A Water inbound row is a limit like any other.
- **Nuclear waste** (Uranium Waste 10/min per plant on Uranium rods, Plutonium Waste 1/min on Plutonium rods, none on Ficsonium) is the Nuclear Power Plants' by-product. It can't be sunk: it's marked like the fluids on the Sink and shown with a warning that it's left over. What to do with it is up to the user for now. Later: offer waste as a Chain supply, so a plutonium plan can take a uranium plan's waste (the Chain lists only demand targets today).

## Logistics
- Fuel Generators: an input side only, a pipe per fuel (as in 055).
- Coal Generators: an input side with the fuel belt(s) and the water pipe.
- Nuclear Power Plants: an input side with the rod belt(s) and the water pipe, and an output side for the waste.

## Edge cases
- An inbound row the plan uses none of can't be a limit: it's shown as unused.
- If no inbound row is used at all, nothing limits the plan: a notice says so and the plan runs at the typed rates.

## Built
- The demand rows keep their typed rates (the ratio); the computed rates are listed in the summary under the checkbox, with each inbound row's use, rather than written into the rows.
- The Chain tab also leaves out a limited plan's fuels as supplies: the plan burns them.
- Burn rates are checked against the items' energy in the game data (MW × 60 / MJ), in `tests/unit/test_supply.py`.
