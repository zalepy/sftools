import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent

DATA_DIR = Path(os.environ.get("SFTOOLS_DATA_DIR", PACKAGE_DIR / "data"))
TEMPLATES_DIR = PACKAGE_DIR / "web" / "templates"
DEFAULT_COLORS_FILE = DATA_DIR / "node_colors.json"
