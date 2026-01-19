from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Request, Form, Body
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json

from sftools_service.domain.models.demand import Demand
from sftools_service.domain.enums.demand_type import DemandType
from sftools_service.logic.demand_calculator import load_models, calculate_demands, recalculate_graph, DATA_PATH

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Load data on startup
print("Loading data...")
items_map, recipes_map, buildings_map = load_models(DATA_PATH)
all_item_names = sorted(list(items_map.keys()))
print(f"Data loaded: {len(items_map)} items, {len(recipes_map)} recipes.")


class ComparisonRequest(BaseModel):
    items: List[str]
    rates: List[float]
    scale_overrides: Optional[Dict[str, float]] = {}
    round_up: bool = True

def _serialize_node(node):
    # Build scaled input rates from the node's recipe data
    scaled_inputs = []
    if hasattr(node, 'scaled_inputs') and node.scaled_inputs:
        scaled_inputs = node.scaled_inputs
    
    return {
        "id": node.id,
        "name": node.name,
        "building": node.building.name,
        "building_scale": node.building_scale,
        "original_building_scale": node.original_building_scale,
        "user_scale": node.user_scale,
        "throughput": node.scaled_output,
        "power": node.scaled_power,
        "output_item": node.output_item_name,
        "parents": [p.id for p in node.parents],
        "children": [c.id for c in node.children],
        "scaled_inputs": scaled_inputs
    }

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "all_items": all_item_names,
        "existing_demands": None,
        "graph_json": "null"
    })


@app.post("/")
def calculate(
    request: Request,
    items: List[str] = Form(...),
    rates: List[float] = Form(...)
):
    root_demands = []
    input_demands = []
    
    for i in range(len(items)):
        item_name = items[i].strip()
        try:
            rate = float(rates[i])
        except (ValueError, IndexError):
            continue
            
        if not item_name or rate <= 0:
            continue
            
        item = items_map.get(item_name)
        if item:
             root_demands.append(Demand(item_name, item, rate, DemandType.PRODUCE))
             input_demands.append((item_name, rate))

    if not root_demands:
         return templates.TemplateResponse("index.html", {
            "request": request,
             "all_items": all_item_names,
             "error": "No valid items selected found in database.",
             "graph_json": "null"
        })

    # Initial calculation with defaults
    final_nodes, _ = calculate_demands(items_map, root_demands, overrides={}, round_up=True)

    # Serialize for Frontend
    nodes_data = [ _serialize_node(n) for n in final_nodes.values() ]
    graph_json = json.dumps(nodes_data)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "all_items": all_item_names,
        "production_nodes": final_nodes, # For fallback table
        "existing_demands": input_demands,
        "graph_json": graph_json
    })

@app.post("/api/calculate")
def api_calculate(payload: ComparisonRequest):
    root_demands = []
    for i in range(len(payload.items)):
        item_name = payload.items[i]
        rate = payload.rates[i]
        item = items_map.get(item_name)
        if item:
             root_demands.append(Demand(item_name, item, rate, DemandType.PRODUCE))
    
    # Step 1: Base calculation to build graph and initial scales
    base_nodes, _ = calculate_demands(
        items_map, 
        root_demands, 
        scale_overrides={}, # Start from fresh scales
        round_up=payload.round_up
    )
    
    # Step 2: Recalculate based on overrides, propagating changes
    final_nodes = recalculate_graph(base_nodes, payload.scale_overrides)
    
    nodes_data = [ _serialize_node(n) for n in final_nodes.values() ]
    
    return {
        "nodes": nodes_data
    }
