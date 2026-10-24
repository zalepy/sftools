import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from sftools.api.schemas import PlanRequest, PlanResponse, RecipeChoice, RecipeInfo
from sftools.config import DEFAULT_COLORS_FILE
from sftools.domain.models.graph_view import ui_nodes
from sftools.domain.models.power import FUELS, power_summary
from sftools.engine.calculator import build_plan, default_recipe_for
from sftools.engine.game_data import GameData, get_game_data
from sftools.engine.logistics import FLUIDS, Settings, attach_logistics
from sftools.engine.supply import build_supply_plan, eligible, is_raw

router = APIRouter(prefix="/api")


@router.post("/calculate", response_model=PlanResponse)
def calculate(plan: PlanRequest, data: GameData = Depends(get_game_data)):
    unknown = sorted({d.item for d in [*plan.demands, *plan.inbound] if d.item not in data.items})
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown items: {', '.join(unknown)}")

    demands = [(d.item, d.rate) for d in plan.demands]
    inbound = [(d.item, d.rate) for d in plan.inbound]
    adjustments = dict(recipes=plan.recipes, merges=plan.merges, clocks=plan.clocks, byproducts=plan.byproducts,
                       byproducts_default=plan.byproducts_default, preferred=plan.preferred)
    supply = None
    try:
        if not eligible(demands, inbound):
            graph = build_plan(data.items, data.recipes, demands, inbound=inbound, **adjustments)
        elif plan.supply_limit:
            graph, supply = build_supply_plan(data.items, data.recipes, demands, inbound, **adjustments)
        else:
            graph, supply = build_plan(data.items, data.recipes, demands, inbound=inbound, **adjustments), {"active": False}
    except ValueError as ex:
        # e.g. merging nodes with different output items
        raise HTTPException(status_code=400, detail=str(ex)) from ex

    nodes = ui_nodes(graph)
    resets = attach_logistics(nodes, lambda item: data.items[item].category in FLUIDS,
                              Settings.parse(plan.logistics.get("settings")), plan.logistics.get("layouts") or {},
                              plan.logistics.get("edges") or {})
    if supply and supply["active"]:
        supply["power"] = power_summary(nodes)
    return {"nodes": nodes, "ignored": graph.ignored, "byproducts": graph.resolved_byproduct_choices(),
            "logistics_resets": resets, "supply": supply}


@router.get("/available_recipes", response_model=List[RecipeInfo])
def available_recipes(item_name: str, data: GameData = Depends(get_game_data)):
    item = data.items.get(item_name)
    if not item:
        raise HTTPException(status_code=404, detail=f"Unknown item: {item_name}")

    return [
        RecipeInfo(
            name=r.name,
            type=r.type.name,
            building=r.building.name,
            output_rate=r.rate_of(item_name),
            byproduct=not r.is_main_product(item_name),
        )
        for r in item.recipes
    ]


@router.get("/recipe_choices", response_model=List[RecipeChoice])
def recipe_choices(data: GameData = Depends(get_game_data)):
    """Every item made by more than one recipe: its default and the others (the Recipes tab, ticket 043)."""
    choices = []
    for name in sorted(data.items):
        item = data.items[name]
        recipes = [r for r in item.recipes if r.produces(name) and r.rate_of(name)]
        default = default_recipe_for(item)
        if len(recipes) < 2 or default is None:
            continue
        choices.append(RecipeChoice(item=name, default=default.name, recipes=[
            RecipeInfo(name=r.name, type=r.type.name, building=r.building.name, output_rate=r.rate_of(name),
                       byproduct=not r.is_main_product(name))
            for r in recipes]))
    return choices


@router.get("/power_items")
def power_items(data: GameData = Depends(get_game_data)):
    """
    The fuels a supply-driven plan burns, and the raw items (an inbound row of one only sets the limit), so
    the page can offer the limit and draw the Chain tab without asking the server per plan (ticket 057).
    """
    return {"fuels": sorted(FUELS), "raw": sorted(name for name, item in data.items.items() if is_raw(item))}


@router.get("/colors")
def colors():
    """Default palette. User changes are kept in the browser."""
    if DEFAULT_COLORS_FILE.exists():
        return json.loads(DEFAULT_COLORS_FILE.read_text(encoding="utf-8"))
    return {}
