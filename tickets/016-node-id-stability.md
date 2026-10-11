# 016 — Path-based node IDs are long and fragile

**Type:** tech debt · **Priority:** P3 · **Related:** SPLIT_PLAN.md · **Status:** Open

- IDs look like `root_0__Recipe__[r]Recipe__Recipe…` and grow with depth.
- Any upstream change (a recipe switch, a different root order) invalidates the saved merges and overrides below it.

## Tasks
- [ ] Decide on an ID scheme before implementing splits (e.g. stable hash of (root key, path of item names) + instance index)
- [ ] Root keys should be based on the item, not on its list position (`root_{i}`), so removing a root doesn't renumber the others
