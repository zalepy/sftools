# 025 — Recipe rates are rounded to two decimals

**Type:** data bug · **Priority:** P2 · **Status:** Done · **Related:** 014, 019

> **Done (2026-10-12).** `loader.cycle_seconds` finds each recipe's cycle time: the one with the fewest decimals that gives every listed rate back to within the two-decimal rounding (Turbo Electric Motor 64 s, pure Mk.3 miners 0.125 s). `build_recipe` then sets each rate to `amount × 60 / cycle`. All 380 recipes have a cycle time; 19 rates in 9 recipes change, each by less than 0.005. A plan for 1.875 Supercomputers/min now needs exactly 1.0 buildings (was 0.997). `items.json` is unchanged, so a new scrape gets the same treatment. Tests: `test_rates_are_exact`, `test_exact_rates_stay_within_the_scraped_rounding`.

## Problem
The scraped wiki tables show rates with two decimals, so some rates in `data/items.json` are rounded: 1.875 is stored as 1.88, 5.625 as 5.63, 9.375 as 9.38, 1.6667 as 1.67. Affected recipes include Turbo Motor, Supercomputer, Stitched Iron Plate, Heavy Encased Frame, Turbo Electric Motor, Crystal Computer and Insulated Crystal Oscillator. The error is under 0.3%, but in long chains it turns a perfect match into a tiny surplus or shortage, and status dots show it. Found by comparing with the author's planning spreadsheet, which has the exact values.

## Fix
Every input and output of a recipe shares one cycle. The data has `*_stack` (items per cycle) next to each `*_rate`, and `rate / stack` = 60 / cycle seconds is the same for all of them. For example, Turbo Motor: 7.5/4 = 3.75/2 = 45/24 = 1.875 and 1.88/1 ≈ 1.875.
- In the loader (`build_recipe`): take the recipe's `rate / stack` from its most precise entry (the largest stack), or round the cycle time to a sensible precision. Then set every rate to `stack × that ratio`.
- Fluid stacks are in m³ and follow the same rule (Turbofuel: 22.5/6 = 15/4 = 18.75/5).
- 014 stopped keeping `*_stack` on `Recipe` because nothing used it. The loader only needs it while building rates; the model doesn't need it back.
- Add a test to `test_game_data.py`: every recipe's `rate / stack` agrees across its entries, and the known cases (Turbo Motor 1.875, Supercomputer 5.625 High-Speed Connectors) are exact.
