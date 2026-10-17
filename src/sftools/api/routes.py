import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from sftools.api.schemas import PlanRequest, PlanResponse, RecipeInfo
from sftools.config import DEFAULT_COLORS_FILE
from sftools.engine.calculator import build_plan
from sftools.engine.game_data import GameData, get_game_data
from sftools.engine.logistics import FLUIDS, Settings, attach_logistics

router = APIRouter(prefix="/api")


@router.post("/calculate", response_model=PlanResponse)
def calculate(plan: PlanRequest, data: GameData = Depends(get_game_data)):
    unknown = sorted({d.item for d in [*plan.demands, *plan.inbound] if d.item not in data.items})
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown items: {', '.join(unknown)}")

    try:
        graph = build_plan(
            data.items,
            data.recipes,
            [(d.item, d.rate) for d in plan.demands],
            recipes=plan.recipes,
            merges=plan.merges,
            clocks=plan.clocks,
            inbound=[(d.item, d.rate) for d in plan.inbound],
            byproducts=plan.byproducts,
            byproducts_default=plan.byproducts_default,
        )
    except ValueError as ex:
        # e.g. merging nodes with different output items
        raise HTTPException(status_code=400, detail=str(ex))

    nodes = graph.get_ui_data()
    resets = attach_logistics(nodes, lambda item: data.items[item].category in FLUIDS,
                              Settings.parse(plan.logistics.get("settings")), plan.logistics.get("layouts") or {},
                              plan.logistics.get("edges") or {})
    return {"nodes": nodes, "ignored": graph.ignored, "byproducts": graph.resolved_byproduct_choices(),
            "logistics_resets": resets}


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


@router.get("/colors")
def colors():
    """Default palette. User changes are kept in the browser."""
    if DEFAULT_COLORS_FILE.exists():
        return json.loads(DEFAULT_COLORS_FILE.read_text(encoding="utf-8"))
    return {}
