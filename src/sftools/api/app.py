from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from sftools import __version__
from sftools.api.routes import router
from sftools.config import TEMPLATES_DIR
from sftools.engine.game_data import get_game_data


def create_app() -> FastAPI:
    app = FastAPI(title="sftools", version=__version__)
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    # Load game data at startup so the first request is fast and bad data fails the deploy.
    get_game_data()

    @app.get("/", include_in_schema=False)
    def index(request: Request):
        return templates.TemplateResponse(
            request, "index.html", {"all_items": sorted(get_game_data().items)}
        )

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    app.include_router(router)
    return app


app = create_app()
