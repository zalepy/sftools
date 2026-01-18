from typing import List, Optional
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sftools_service.domain.models.demand import Demand
from sftools_service.domain.enums.demand_type import DemandType
from sftools_service.logic.demand_calculator import load_models, calculate_demands, DATA_PATH

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Load data on startup
# In a production app you might want to do this in a lifespan event, 
# but for this script top-level load is fine as it's read-only.
print("Loading data...")
items_map, recipes_map, buildings_map = load_models(DATA_PATH)
all_item_names = sorted(list(items_map.keys()))
print(f"Data loaded: {len(items_map)} items, {len(recipes_map)} recipes.")


@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "all_items": all_item_names,
        "existing_demands": None
    })


@app.post("/")
def calculate(
    request: Request,
    items: List[str] = Form(...),
    rates: List[float] = Form(...)
):
    root_demand = {}
    input_demands = []
    
    # Process inputs
    # items and rates should correspond by index
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
             root_demand[item_name] = Demand(item_name, item, rate, DemandType.PRODUCE)
             input_demands.append((item_name, rate))

    if not root_demand:
         return templates.TemplateResponse("index.html", {
            "request": request,
             "all_items": all_item_names,
             "error": "No valid items selected found in database."
        })

    final_production_nodes, sub_demands = calculate_demands(items_map, root_demand)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "all_items": all_item_names,
        "production_nodes": final_production_nodes,
        "sub_demands": sub_demands,
        "existing_demands": input_demands
    })
