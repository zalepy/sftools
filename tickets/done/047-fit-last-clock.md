# 047 — Fit the last building's clock to the demand

**Type:** feature · **Priority:** P3 · **Status:** Done · **Related:** [023](023-clock-speeds.md)

## Goal
A button on the Node tab that sets the Last clock so that the node makes exactly what's demanded: no surplus.

## Decisions (agreed with the user, 2026-10-20)
- **All clock assumed 100%.** The fit computes Last only, and resets All to 100%. If All was touched, it's expected to solve the surplus already.
- **Rule.** S is the demand in buildings at 100% (`ideal_building_scale`) and N = ceil(S) is the count without a Last clock. With `count` buildings, Last = S − (count − 1).
  1. If N−1 is not 5 or 7 and Last ≤ 150% with N−1 buildings: N−1 buildings, Last overclocked (1 shard).
  2. Otherwise, if N is not 5 or 7: N buildings, Last underclocked (no shards).
  3. If N is 5 or 7 and Last ≤ 200% with N−1 buildings: 4 or 6 buildings (up to 2 shards).
  4. Otherwise: N buildings, Last underclocked.
  - Only 5 and 7 are avoided. With more buildings the logistics are generally overflow rather than balanced.
  - Cases: N=6, where 5 would work with 1 shard, gives 6 underclocked. N=5, where 4 needs 180%, gives 4 with 2 shards. N=1 gives 1 underclocked.
- **Precision:** Last is rounded up to 4 decimals of a percent (e.g. 63.4567%), so the node never falls short. The surplus left (≤ 0.000001 building) is far below the surplus dot's threshold (0.0001).
- **Applies right away,** as one undo step (no Apply Clock Speeds needed).
- **Disabled** (tooltip says why) when there's no surplus to fix, e.g. already fitted or whole buildings exactly. Hidden on inbound nodes and the Sink, like the clock boxes.
- **Buttons:** ⚖️ (fit) and 🚫 (clear, replacing the "Clear" text button) as small square buttons after the Last box, as high as the inputs, with tooltips "Fit the last building to the demand" and "Clear the clock speeds". Apply Clock Speeds stays a full-width button below.

## Notes
- Implemented 2026-10-20, client-side (`panel.fitLastClock`, `main.fitClock`); the server is unchanged.
- Step 4 of the rule never happens: with N−1 buildings the last needs 100% + the fraction, which is at most 200%.
- If the underclocked last would be under 1% (the lowest clock), the fit uses one building fewer, just over 100%, even when that makes 5 or 7.
- Tests: `tests/integration/test_fit_clock.py`.
