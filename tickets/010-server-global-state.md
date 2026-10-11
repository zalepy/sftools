# 010 — Shared GLOBAL_STATE is unsafe for multiple users

**Type:** bug / architecture · **Priority:** P1 (before sharing the Render URL) · **Status:** Done

> **Update (2026-10-11):** Option 1: `POST /api/calculate` takes the full plan and replays it (`engine/calculator.build_plan`). Removed `/api/recalculate`, `/api/merge_nodes`, `/api/unmerge_node`, `/api/switch_recipe`.

## Problem
`GLOBAL_STATE` is one process-wide dict. On Render, every visitor overwrites every other visitor's graph, and it isn't thread-safe. All state is also lost when the instance restarts or the free tier spins down.

## Options
1. **Stateless (recommended):** the client already keeps `items`, `rates`, `merges` and `overrides` in localStorage. Each mutating endpoint gets the full plan (+ recipe switches, see 012), rebuilds the graph and returns it. Building the graph is fast.
2. Store state per session in memory, keyed by a client-generated plan ID (still lost on restart).
3. Persistent storage (SQLite or Postgres). Only worth it if plans should be shareable or survive across devices.

## Acceptance criteria
- Two browser sessions can edit different plans at the same time without interfering
