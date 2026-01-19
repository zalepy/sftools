from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Request, Form, Body
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import os

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


class CalculateRequest(BaseModel):
    items: List[str]
    rates: List[float]
    round_up: bool = True
    merges: Dict[str, str] = {}
    overrides: Dict[str, float] = {}

class RecalculateRequest(BaseModel):
    scale_overrides: Dict[str, float]

class MergeRequest(BaseModel):
    source_id: str
    target_id: str

# In-memory store for the last calculated graph
# Keys: 'nodes', 'items', 'rates', 'round_up'
GLOBAL_STATE = {
    "nodes": None,
    "items": None,
    "rates": None,
    "round_up": True,
    "merges": {}
}

def _serialize_node(node):
    # Build scaled input rates from the node's recipe data
    scaled_inputs = []
    if hasattr(node, 'scaled_inputs') and node.scaled_inputs:
        scaled_inputs = node.scaled_inputs
    
    return {
        "id": node.id,
        "name": node.name,
        "recipe_name": node.name.split('__')[-1] if '__' in node.name else node.name,
        "building": node.building.name,
        "building_scale": node.building_scale,
        "original_building_scale": node.original_building_scale,
        "user_scale": node.user_scale,
        "ideal_building_scale": node.ideal_building_scale,
        "throughput": node.scaled_output,
        "power": node.scaled_power,
        "output_item": node.output_item_name,
        "parents": [p.id for p in node.parents],
        "children": [c.id for c in node.children],
        "scaled_inputs": scaled_inputs,
        "base_output_rate": node.base_output_rate,
        "base_inputs": node.base_inputs,
        "base_power": node.base_power
    }

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "all_items": all_item_names
    })

@app.post("/api/calculate")
def api_calculate(payload: CalculateRequest):
    root_demands = []
    for i in range(len(payload.items)):
        item_name = payload.items[i]
        rate = payload.rates[i]
        item = items_map.get(item_name)
        if item:
            root_demands.append(Demand(item_name, item, rate, DemandType.PRODUCE))
    
    # Fresh build of graph structure
    final_nodes = calculate_demands(
        items_map, 
        root_demands, 
        scale_overrides={}, 
        round_up=payload.round_up
    )
    
    # Apply merges from persistence
    if payload.merges:
        for source_id, target_id in payload.merges.items():
            if source_id in final_nodes and target_id in final_nodes:
                source_node = final_nodes[source_id]
                target_node = final_nodes[target_id]
                target_node.absorb_node(source_node)
                del final_nodes[source_id]
        
        # Recalculate to update following the structural changes
        # Use provided overrides to preserve manual adjustments
        recalculate_graph(final_nodes, overrides=payload.overrides, round_up=payload.round_up)
    elif payload.overrides:
        # Even if no merges, apply overrides to the fresh graph
        recalculate_graph(final_nodes, overrides=payload.overrides, round_up=payload.round_up)

    # Update GLOBAL_STATE
    GLOBAL_STATE["nodes"] = final_nodes
    GLOBAL_STATE["items"] = payload.items
    GLOBAL_STATE["rates"] = payload.rates
    GLOBAL_STATE["round_up"] = payload.round_up
    GLOBAL_STATE["merges"] = payload.merges
    
    nodes_data = [ _serialize_node(n) for n in final_nodes.values() ]
    return {"nodes": nodes_data}

@app.post("/api/recalculate")
def api_recalculate(payload: RecalculateRequest):
    if GLOBAL_STATE["nodes"] is None:
        return {"error": "No graph has been calculated yet. Click Calculate first."}, 400
    
    # Recalculate values using the existing graph structure and stored round_up setting
    final_nodes = recalculate_graph(
        GLOBAL_STATE["nodes"], 
        payload.scale_overrides, 
        round_up=GLOBAL_STATE["round_up"]
    )
    
    nodes_data = [ _serialize_node(n) for n in final_nodes.values() ]
    return {"nodes": nodes_data}

@app.post("/api/merge_nodes")
def api_merge_nodes(payload: MergeRequest):
    if GLOBAL_STATE["nodes"] is None:
        return {"error": "No graph has been calculated yet."}, 400
    
    nodes_map = GLOBAL_STATE["nodes"]
    source_node = nodes_map.get(payload.source_id)
    target_node = nodes_map.get(payload.target_id)
    
    if not source_node or not target_node:
        return {"error": "Source or target node not found."}, 404
    
    if source_node.output_item_name != target_node.output_item_name:
        return {"error": "Cannot merge nodes with different output items."}, 400

    # Execute merge
    target_node.absorb_node(source_node)
    
    # Remove source from global state
    del nodes_map[payload.source_id]

    # Record merge in GLOBAL_STATE for persistence
    if "merges" not in GLOBAL_STATE: GLOBAL_STATE["merges"] = {}
    GLOBAL_STATE["merges"][payload.source_id] = payload.target_id

    # Recalculate graph to propagate changes
    final_nodes = recalculate_graph(
        nodes_map, 
        None, # Preserve existing overrides
        round_up=GLOBAL_STATE["round_up"]
    )
    
    nodes_data = [ _serialize_node(n) for n in final_nodes.values() ]
    return {"nodes": nodes_data}

COLORS_FILE = os.path.join(DATA_PATH, 'node_colors.json')

@app.get("/api/colors")
def get_colors():
    if os.path.exists(COLORS_FILE):
        with open(COLORS_FILE, 'r') as f:
            return json.load(f)
    return {}

@app.post("/api/colors")
def save_colors(colors: Dict[str, str] = Body(...)):
    with open(COLORS_FILE, 'w') as f:
        json.dump(colors, f, indent=2)
    return {"status": "success"}
