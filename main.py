from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Request, Form, Body
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
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

class UnmergeRequest(BaseModel):
    node_id: str
    overrides: Dict[str, float] = {}

# In-memory store for the last calculated graph
# Keys: 'graph', 'items', 'rates', 'round_up'
GLOBAL_STATE = {
    "graph": None,
    "items": None,
    "rates": None,
    "round_up": True,
    "merges": {}
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
    graph = calculate_demands(
        items_map, 
        root_demands, 
        scale_overrides={}, 
        round_up=payload.round_up
    )
    
    # Apply merges from persistence
    if payload.merges:
        for source_id, target_id in payload.merges.items():
            graph.apply_merge(source_id, target_id)
        
        # Recalculate to update following the structural changes
        # Use provided overrides to preserve manual adjustments
        graph.recalculate(overrides=payload.overrides, round_up=payload.round_up)
    elif payload.overrides:
        # Even if no merges, apply overrides to the fresh graph
        graph.recalculate(overrides=payload.overrides, round_up=payload.round_up)

    # Update GLOBAL_STATE
    GLOBAL_STATE["graph"] = graph
    GLOBAL_STATE["items"] = payload.items
    GLOBAL_STATE["rates"] = payload.rates
    GLOBAL_STATE["round_up"] = payload.round_up
    GLOBAL_STATE["merges"] = payload.merges
    
    return {"nodes": graph.get_ui_data()}

@app.post("/api/recalculate")
def api_recalculate(payload: RecalculateRequest):
    if GLOBAL_STATE["graph"] is None:
        return JSONResponse(status_code=400, content={"error": "No graph has been calculated yet. Click Calculate first."})
    
    # Recalculate values using the existing graph structure and stored round_up setting
    graph = GLOBAL_STATE["graph"]
    graph.recalculate(
        payload.scale_overrides, 
        round_up=GLOBAL_STATE["round_up"]
    )
    
    return {"nodes": graph.get_ui_data()}

@app.post("/api/merge_nodes")
def api_merge_nodes(payload: MergeRequest):
    if GLOBAL_STATE["graph"] is None:
        return JSONResponse(status_code=400, content={"error": "No graph has been calculated yet."})
    
    graph = GLOBAL_STATE["graph"]
    source_node = graph.get_node(payload.source_id)
    target_node = graph.get_node(payload.target_id)
    
    if not source_node or not target_node:
        return {"error": "Source or target node not found."}, 404
    
    if source_node.output_item_name != target_node.output_item_name:
        return JSONResponse(status_code=400, content={"error": "Cannot merge nodes with different output items."})

    # Execute merge
    graph.apply_merge(payload.source_id, payload.target_id)
    
    # Record merge in GLOBAL_STATE for persistence
    if "merges" not in GLOBAL_STATE: GLOBAL_STATE["merges"] = {}
    GLOBAL_STATE["merges"][payload.source_id] = payload.target_id

    # Recalculate graph to propagate changes
    graph.recalculate(
        None, # Preserve existing overrides
        round_up=GLOBAL_STATE["round_up"]
    )
    
    return {"nodes": graph.get_ui_data()}

@app.post("/api/unmerge_node")
def api_unmerge_node(payload: UnmergeRequest):
    if GLOBAL_STATE["graph"] is None:
        return JSONResponse(status_code=400, content={"error": "No graph has been calculated yet."})
    
    # Remove all merges targeting this node from persistence
    if "merges" in GLOBAL_STATE:
        keys_to_remove = [s_id for s_id, t_id in GLOBAL_STATE["merges"].items() if t_id == payload.node_id]
        for k in keys_to_remove:
            del GLOBAL_STATE["merges"][k]

    graph = GLOBAL_STATE["graph"]
    graph.remove_merge(payload.node_id)
    
    # Recalculate with provided overrides
    graph.recalculate(overrides=payload.overrides, round_up=GLOBAL_STATE["round_up"])
    
    return {"nodes": graph.get_ui_data()}

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
