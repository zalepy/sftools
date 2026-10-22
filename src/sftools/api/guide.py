"""The user guide (USER_GUIDE.md) as HTML for the app's Guide panel; GitHub shows the same file."""
import re
from functools import lru_cache

import markdown

from sftools.config import GUIDE_DIR

GUIDE_FILE = GUIDE_DIR / "USER_GUIDE.md"
IMAGES_URL = "/guide/images/"


@lru_cache(maxsize=1)
def guide_html() -> str:
    """
    The guide rendered once, with a contents list of its sections before the first one. Headings get the ids
    GitHub gives them (e.g. "clock-speeds"), so the same "#..." links work in both places, and image
    paths relative to the file ("images/x.png") point to where the app serves them.
    """
    md = markdown.Markdown(extensions=["toc", "tables", "fenced_code", "sane_lists"],
                           extension_configs={"toc": {"toc_depth": "2-2"}})
    body = md.convert(GUIDE_FILE.read_text(encoding="utf-8"))
    body = re.sub(r'(<img[^>]*\ssrc=")images/', rf"\g<1>{IMAGES_URL}", body)
    # Links out of the guide open in a new tab, so the plan stays open
    body = body.replace('<a href="http', '<a target="_blank" rel="noopener" href="http')
    contents = f'<nav class="guide-toc" aria-label="Contents">{md.toc}</nav>\n'
    first = body.find("<h2")
    return body[:first] + contents + body[first:] if first >= 0 else contents + body
