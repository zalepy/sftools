from typing import Any, Dict, List

from pydantic import BaseModel, Field


class DemandIn(BaseModel):
    item: str
    rate: float = Field(gt=0)


class PlanRequest(BaseModel):
    """Full description of a plan. The server keeps no state between requests."""
    demands: List[DemandIn]
    round_up: bool = True
    recipes: Dict[str, str] = {}  # node_id -> recipe name
    merges: Dict[str, str] = {}  # source node_id -> target node_id
    overrides: Dict[str, float] = {}  # node_id -> building scale


class PlanResponse(BaseModel):
    nodes: List[Dict[str, Any]]


class RecipeInfo(BaseModel):
    name: str
    type: str
    building: str
    output_rate: float | None
