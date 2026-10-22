"""
After a push to master: waits until the deployed site runs that commit (its /healthz reports it), then
runs the browser tests against it.

    uv run python scripts/release_check.py [--url https://sftools.onrender.com] [--commit <sha>]

The commit defaults to HEAD. Exits with the tests' status, or 1 if the deploy doesn't show up in time.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

DEFAULT_URL = "https://sftools.onrender.com"
TIMEOUT = 15 * 60  # Render's free tier can take a while to build and swap
POLL = 15


def deployed_commit(url):
    try:
        with urllib.request.urlopen(f"{url}/healthz", timeout=30) as response:
            return json.load(response).get("commit")
    except (OSError, ValueError):
        return None  # asleep, restarting, or an older deploy without the field


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--commit", default=None)
    args = parser.parse_args()
    url = args.url.rstrip("/")
    commit = args.commit or subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                           check=True).stdout.strip()

    deadline = time.time() + TIMEOUT
    while (current := deployed_commit(url)) != commit:
        if time.time() > deadline:
            print(f"{url} still runs {current}, not {commit[:7]}", file=sys.stderr)
            return 1
        time.sleep(POLL)
    print(f"{url} runs {commit[:7]}; running the browser tests against it")
    env = {**os.environ, "SFTOOLS_BASE_URL": url}
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/integration"], env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
