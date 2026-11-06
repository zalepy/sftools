"""
The same plan gives the same response in every server process.

Python randomizes the order of a set of strings per process, so this can only be seen across processes:
each seed below runs in its own one. The plans are small ones that came out differently on these seeds
when the order the groups were calculated in followed a set: which consumer a by-product covers first
depended on it, so a plan could change after a restart, or between two workers.
"""
import json
import os
import subprocess
import sys

SEEDS = (1, 2, 3, 4)
PLANS = (["Battery"], ["Cooling System", "Aluminum Ingot"], ["Turbo Motor"])

RUN_PLANS = """
import json, sys
from fastapi.testclient import TestClient
from sftools.api.app import app

client = TestClient(app)
for plan in json.loads(sys.argv[1]):
    demands = [{"item": item, "rate": 1} for item in plan]
    print(client.post("/api/calculate", json={"demands": demands, "byproducts_default": "use"}).text)
"""


def responses(seed: int) -> list:
    result = subprocess.run([sys.executable, "-c", RUN_PLANS, json.dumps(PLANS)], capture_output=True, text=True,
                            env={**os.environ, "PYTHONHASHSEED": str(seed)}, check=True)
    return result.stdout.splitlines()


def test_a_plan_does_not_depend_on_the_process():
    first, *others = [responses(seed) for seed in SEEDS]
    assert len(first) == len(PLANS)
    for other in others:
        for plan, a, b in zip(PLANS, first, other, strict=True):
            assert a == b, f"{plan} differs between processes"
