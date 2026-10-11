# 009 — API validation and error responses

**Type:** bug · **Priority:** P2 · **Depends on:** 001 · **Status:** Mostly done

> **Update (2026-10-11):** Done with 010: `HTTPException` everywhere, `demands: [{item, rate}]` schema, 422 for unknown items, 400 for an invalid merge, endpoint tests in `tests/test_api.py`. Left: unknown or unresolvable recipe names are skipped silently.

- [ ] `api_merge_nodes` returns `{"error": ...}, 404`, which FastAPI sends as a list with HTTP 200. Raise `HTTPException(404)` instead.
- [ ] `CalculateRequest`: an `items`/`rates` length mismatch causes an `IndexError` and a 500. Validate it, or change the schema to `demands: [{item, rate}]`.
- [ ] Unknown item or recipe names are silently dropped. Return 422 with the names that weren't found.
- [ ] Use `HTTPException` everywhere instead of hand-built `JSONResponse` error bodies
- [ ] Endpoint tests with `fastapi.testclient`
