# 003 — Fluid rates parsed 10× too high (+3)

**Type:** bug · **Priority:** P0 · **Status:** Open

## Problem
`get_float_or_none` / `get_int_or_none` (`src/sftools/engine/loader.py`) remove everything except `[-0-9.]`, so the "3" in the unit is kept: `"10m3"` → `103.0` and `"120m3"` → `1203.0`.
Every fluid ingredient and output is wrong. 20+ recipes show rates of 1003, 1203 or 2403.

## Fix
- [ ] Parse only the leading number (e.g. `^\s*(-?[\d,]*\.?\d+)`), or strip known unit suffixes (`m3`, `m³`, `/min`, `MW`, `MJ`, `m`) **before** filtering digits
- [ ] Remove the unused `strippings` parameter
- [ ] Regression test: Alumina Solution and Unpackage Water have the correct rates

## Acceptance criteria
- No recipe rate in the loaded models exceeds a sane maximum (checked by the validation in 013)
