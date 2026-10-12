# 009 — API validation and error responses

**Type:** bug · **Priority:** P2 · **Depends on:** 001 · **Status:** Done

> **Update (2026-10-11):** Done with 010: `HTTPException` everywhere, `demands: [{item, rate}]` schema, 422 for unknown items, 400 for an invalid merge, endpoint tests in `tests/unit/test_api.py`. Left: unknown or unresolvable recipe names are skipped silently.

> **Fixed (2026-10-11):** Plan entries that can't apply are now *reported, not rejected*. A 422 would make a stale saved plan fail on every load (e.g. after default recipes or recipe names change). `POST /api/calculate` builds what it can and returns `ignored: [{kind, node_id, reason}]` for:
> - recipe switches on unknown nodes, with unknown recipe names, or with recipes that don't produce the node's item
> - merges and overrides on unknown nodes
>
> Entries for dormant nodes or inactive branches (created under an upstream recipe that was switched away from) are kept silently, because they apply again if that recipe is switched back. Node IDs contain the parent's recipe, so `_on_inactive_branch` can tell the two cases apart. (Superseded by 022: entries on dropped inputs are now discarded.)
> The UI removes the ignored entries from the saved plan and shows a dismissible notice listing them. Tests: `test_stale_entries_are_reported_not_rejected`, `test_entries_on_inactive_branches_are_kept_silently`.

- [ ] `api_merge_nodes` returns `{"error": ...}, 404`, which FastAPI sends as a list with HTTP 200. Raise `HTTPException(404)` instead.
- [ ] `CalculateRequest`: an `items`/`rates` length mismatch causes an `IndexError` and a 500. Validate it, or change the schema to `demands: [{item, rate}]`.
- [ ] Unknown item or recipe names are silently dropped. Return 422 with the names that weren't found.
- [ ] Use `HTTPException` everywhere instead of hand-built `JSONResponse` error bodies
- [ ] Endpoint tests with `fastapi.testclient`
