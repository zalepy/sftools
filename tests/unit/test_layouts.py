"""
The reference layouts (ticket 056) against the game data: their numbers are written in the data file, so a
game update that changes a recipe fails here instead of leaving a layout quietly wrong.
"""
import json
from collections import defaultdict

import pytest

from sftools.config import DATA_DIR, STATIC_DIR
from sftools.domain.models.graph_view import GENERATOR_POWER
from sftools.engine.game_data import get_game_data
from sftools.engine.logistics import PIPES

LAYOUTS = STATIC_DIR / "layouts"


def layouts():
    return [json.loads((LAYOUTS / f"{entry['id']}.json").read_text(encoding="utf-8"))
            for entry in json.loads((LAYOUTS / "index.json").read_text(encoding="utf-8"))]


def energy(item):
    """MJ per unit, from the raw data (the loader doesn't keep it), e.g. '2,000MJ'."""
    raw = json.loads((DATA_DIR / "items.json").read_text(encoding="utf-8"))
    entry = next(i for i in raw if i["name"] == item)
    return float(entry["Energy"].replace(",", "").removesuffix("MJ"))


@pytest.fixture(scope="module")
def recipes():
    return get_game_data().recipes


def flows(layout, recipes):
    """Per recipe: item -> rate in (negative) and out, from its buildings at their clocks."""
    totals = defaultdict(lambda: defaultdict(float))
    for building in layout["buildings"]:
        recipe = recipes[building["recipe"]]
        clock = building.get("clock", 1)
        for item, rate in recipe.ingredients:
            totals[recipe.name][item.name] -= rate * clock
        for item, rate in recipe.outputs():
            totals[recipe.name][item.name] += rate * clock
    return totals


@pytest.mark.parametrize("layout", layouts(), ids=lambda layout: layout["id"])
def test_the_table_matches_the_buildings(layout, recipes):
    by_recipe = flows(layout, recipes)
    used = defaultdict(float)  # what the layout's buildings take, net
    for made in by_recipe.values():
        for item, rate in made.items():
            used[item] -= rate
    for row in layout["table"]:
        if "count" in row:
            # A supply built elsewhere, e.g. the Compacted Coal: `count` buildings make what the layout takes
            recipe = recipes[row["recipe"]]
            assert dict((i.name, r * row["count"]) for i, r in recipe.ingredients) == pytest.approx(dict(row["in"])), row["step"]
            assert dict((i.name, r * row["count"]) for i, r in recipe.outputs()) == pytest.approx(dict(row["out"])), row["step"]
            for item, rate in row["out"]:
                assert used[item] == pytest.approx(rate, abs=0.01), row["step"]
        elif "recipe" in row:
            made = by_recipe[row["recipe"]]
            assert {item: -rate for item, rate in made.items() if rate < 0} == pytest.approx(dict(row["in"]), abs=0.01), row["step"]
            assert {item: rate for item, rate in made.items() if rate > 0} == pytest.approx(dict(row["out"]), abs=0.01), row["step"]
        elif "generators" in row:
            # Fuel Generators: 250 MW from the item's energy
            (item, rate), = row["in"]
            per_generator = GENERATOR_POWER * 60 / energy(item)
            assert row["generators"] == pytest.approx(rate / per_generator)
            assert dict(row["out"]) == {"MW": pytest.approx(row["generators"] * GENERATOR_POWER)}


@pytest.mark.parametrize("layout", layouts(), ids=lambda layout: layout["id"])
def test_pipe_totals_add_up_and_fit(layout, recipes):
    """Each pipe's last total is what its buildings put in; the running totals rise by one building's output
    at a time; no pipe carries more than its tier; and what the pipes of an item carry is what's taken from them."""
    traces = {t["id"]: t for t in layout["traces"]}
    put = defaultdict(float)
    taken = defaultdict(float)
    for building in layout["buildings"]:
        recipe = recipes[building["recipe"]]
        clock = building.get("clock", 1)
        into = traces[building["into"]]
        put[into["id"]] += recipe.rate_of(into["item"]) * clock
        if "from" in building:
            source = traces[building["from"]]
            taken[source["item"]] += dict((i.name, r) for i, r in recipe.ingredients)[source["item"]] * clock
    carried = defaultdict(float)
    for trace in traces.values():
        if trace["kind"] != "pipe":
            continue
        values = [value for _, value in trace.get("totals", [])]
        if values:
            assert values[-1] == pytest.approx(put[trace["id"]], abs=0.01), trace["id"]
            assert values == sorted(values), trace["id"]
        assert put[trace["id"]] <= PIPES[trace["tier"] - 1], trace["id"]
        carried[trace["item"]] += put[trace["id"]]
    for item, rate in taken.items():
        assert carried[item] == pytest.approx(rate, abs=0.01), item


@pytest.mark.parametrize("layout", layouts(), ids=lambda layout: layout["id"])
def test_everything_is_on_the_grid(layout):
    width, height = layout["size"]
    points = [(b["x"], b["y"]) for b in layout["buildings"]] + [(label["x"], label["y"]) for label in layout["labels"]]
    points += [tuple(p) for t in layout["traces"] for path in t["paths"] for p in path]
    assert all(0 <= x < width and 0 <= y < height for x, y in points)
    assert len({(b["x"], b["y"]) for b in layout["buildings"]}) == len(layout["buildings"])  # one per square
