# 001 — Restructure project: uv, src layout, single FastAPI app

**Type:** chore / structure · **Priority:** P1 · **Blocks:** most other tickets (paths change) · **Status:** Done

> **Update (2026-10-11):** Done on `chore/uv-src-layout`. Python 3.13 (`.python-version`); `uv_build` backend; `httpx2` for the test client. The Render settings still need to be applied (see README).

## Context
- The live app is FastAPI in the root `main.py`. It serves the Jinja UI at `/` and JSON at `/api/*`.
- `sftools_service/` holds the business logic plus a dead Falcon app (`main.py`, `sftools_service.py`, `middleware.py`, `api/test_resource.py`). Falcon is not even in the requirements.
- Paths are relative to the working directory (`DATA_PATH = 'data'`, `Jinja2Templates(directory="templates")`), so the app only works when started from the repo root.
- Dependencies are unpinned, `pytest` ships in the prod requirements, and the scraper's `requests` is mixed in with the app's dependencies.
- Tests are split across `tests/` and `sftools_service/tests/`.

## Target layout
```
pyproject.toml  uv.lock  .python-version  render.yaml
README.md  ARCHITECTURE.md  LICENSE  tickets/
src/sftools/
  __init__.py
  config.py              # settings (data dir, colors file), env-overridable
  domain/                # enums + models (Item, Recipe, Building, Demand, ProductionNode, FactoryGraph)
  engine/                # loader.py (load_models), calculator.py (calculate_demands, expand/switch)
  api/
    app.py               # create_app() factory + `app = create_app()`
    routes.py            # /api/* routers
    schemas.py           # pydantic request/response models
  web/
    templates/index.html
    static/              # once JS/CSS is split out of index.html (see 017)
  data/*.json            # game data, loaded via package-relative path
scripts/scrape/          # former craw/ (optional dependency group `scrape`)
tests/                   # single test root
```

## Tasks
- [ ] `pyproject.toml` (`uv init --package` style):
  - project name `sftools`, `requires-python` matching `.python-version`
  - deps: `fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart`
  - dependency groups: `dev = [pytest, httpx]`, `scrape = [requests]`
- [ ] Move `sftools_service/{domain,logic,config}` to `src/sftools/...` and rename imports from `sftools_service.` to `sftools.`
- [ ] Root `main.py` becomes `src/sftools/api/app.py` with a `create_app()` factory. Routes go in `routes.py`, pydantic models in `schemas.py`.
- [ ] Resolve the data and templates directories relative to the package (`Path(__file__).parent`), overridable via `SFTOOLS_DATA_DIR`
- [ ] Add a `GET /healthz` endpoint for the Render health check
- [ ] Delete the Falcon leftovers, `requirements*.txt`, and stray `__pycache__`
- [ ] Merge `sftools_service/tests` into `tests/` and set `[tool.pytest.ini_options] testpaths = ["tests"]`
- [ ] Move `craw/` to `scripts/scrape/` and point its output at `src/sftools/data/`
- [ ] `render.yaml`:
  - build: `pip install uv && uv sync --frozen --no-dev`
  - start: `uv run --no-sync uvicorn sftools.api.app:app --host 0.0.0.0 --port $PORT`
  - health check path: `/healthz`
  - Check whether Render's native uv detection makes the explicit `pip install uv` step unnecessary.
- [ ] Update the README run instructions: `uv sync`, then `uv run uvicorn sftools.api.app:app --reload`

## Acceptance criteria
- `uv sync && uv run pytest` passes from a clean clone
- `uv run uvicorn sftools.api.app:app --reload` serves the UI at `/` and the API at `/api/*` from **any** working directory
- A Render deploy from `render.yaml` serves https://sftools.onrender.com/ and `/healthz` returns 200
- No references to `sftools_service`, Falcon, or `requirements.txt` remain
