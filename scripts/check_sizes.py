"""
Reports source files past the size where they should be split (see CLAUDE.md, "Code structure").

It warns and exits 0: in CI the warnings show on the run, nothing is blocked. Run: uv run python scripts/check_sizes.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [ROOT / "src" / "sftools", ROOT / "scripts"]
LIMIT = 500  # lines

# Over the limit on purpose, and why
KNOWN = {
    "src/sftools/engine/logistics.py": "one algorithm (the belt simulation), explained in docs/ALGO.md; splitting it would scatter it",
    "src/sftools/web/static/js/logistics.js": "the zoomed-in view's editing; placement is already split out",
}


def main():
    over = []
    for base in SOURCES:
        for path in sorted(base.rglob("*")):
            if path.suffix not in (".py", ".js") or not path.is_file():
                continue
            name = path.relative_to(ROOT).as_posix()
            lines = len(path.read_text(encoding="utf-8").splitlines())
            if lines > LIMIT and name not in KNOWN:
                over.append((name, lines))
    for name, lines in over:
        # GitHub Actions shows this as a warning on the run (and on the file)
        print(f"::warning file={name}::{name} has {lines} lines (over {LIMIT}): split it by concern, see CLAUDE.md")
    for name, why in KNOWN.items():
        print(f"{name}: allowed over {LIMIT} lines ({why})")
    if not over:
        print(f"No other file is over {LIMIT} lines.")


if __name__ == "__main__":
    main()
