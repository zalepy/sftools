"""The user guide (USER_GUIDE.md): its links and images resolve, and the app serves it rendered."""
import re

import pytest
from fastapi.testclient import TestClient

from sftools.api.app import app
from sftools.api.guide import GUIDE_FILE, guide_html
from sftools.config import GUIDE_DIR, TEMPLATES_DIR

TEXT = GUIDE_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def section_ids():
    return set(re.findall(r'<h[1-6] id="([^"]+)"', guide_html()))


def test_images_exist():
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", TEXT)
    assert images
    for image in images:
        assert not image.startswith(("/", "http")), f"{image}: relative to the guide, so GitHub shows it too"
        assert (GUIDE_DIR / image).is_file(), image


def test_links_within_the_guide_resolve():
    ids = section_ids()
    for target in re.findall(r"\]\(#([^)]+)\)", TEXT):
        assert target in ids, f"#{target}"


def test_help_links_in_the_page_resolve():
    """Every "?" in the app opens the guide at a section that exists."""
    page = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    targets = re.findall(r'class="help-link" data-guide="([^"]+)"', page)
    assert len(targets) >= 10
    ids = section_ids()
    assert not sorted(set(targets) - ids)


def test_guide_is_served_rendered(client):
    response = client.get("/guide")
    assert response.status_code == 200
    html = response.text
    assert '<nav class="guide-toc"' in html
    assert '<h2 id="clock-speeds">' in html
    assert 'src="/guide/images/overview.png"' in html
    assert 'target="_blank" rel="noopener" href="https://www.satisfactorygame.com/"' in html


def test_only_the_images_are_served(client):
    response = client.get("/guide/images/overview.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert client.get("/guide/USER_GUIDE.md").status_code == 404
