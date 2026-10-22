import hashlib
import mimetypes
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sftools import __version__
from sftools.api.routes import router
from sftools.api.guide import guide_html
from sftools.config import GUIDE_DIR, STATIC_DIR, TEMPLATES_DIR
from sftools.engine.game_data import get_game_data


# Browsers refuse ES modules served as text/plain, which some Windows registries map .js to
mimetypes.add_type("text/javascript", ".js")


class RevalidatedStaticFiles(StaticFiles):
    """
    Static files that browsers must revalidate (cheap 304s via ETag), so a deploy is picked up
    right away. Module imports between JS files can't carry the ?v= query the page uses.
    """
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


def asset_version() -> str:
    """Short hash of the static files, appended to the page's CSS/JS URLs."""
    digest = hashlib.sha256()
    for path in sorted(STATIC_DIR.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(STATIC_DIR).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def create_app() -> FastAPI:
    app = FastAPI(title="sftools", version=__version__)
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    version = asset_version()

    # Load game data at startup so the first request is fast and bad data fails the deploy.
    get_game_data()
    guide_html()  # a guide that doesn't render fails the deploy too

    @app.get("/", include_in_schema=False)
    def index(request: Request):
        return templates.TemplateResponse(
            request, "index.html", {"all_items": sorted(get_game_data().items), "asset_version": version},
        )

    @app.get("/logistics", include_in_schema=False)
    def logistics():
        """The old address of logistics mode, the only mode since simple mode was removed."""
        return RedirectResponse("/", status_code=301)

    @app.get("/guide", include_in_schema=False, response_class=HTMLResponse)
    def guide():
        """The user guide as an HTML fragment, for the Guide panel."""
        return HTMLResponse(guide_html(), headers={"Cache-Control": "no-cache"})

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        """Liveness, and the deployed commit (Render sets RENDER_GIT_COMMIT), so a release check waits for its own."""
        return {"status": "ok", "commit": os.environ.get("RENDER_GIT_COMMIT", "local")}

    app.include_router(router)
    app.mount("/static", RevalidatedStaticFiles(directory=STATIC_DIR), name="static")
    # Only the guide's images: the Markdown is served rendered, by /guide
    app.mount("/guide/images", RevalidatedStaticFiles(directory=GUIDE_DIR / "images"), name="guide-images")
    return app


app = create_app()
