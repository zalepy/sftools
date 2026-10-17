from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DemandIn(BaseModel):
    item: str
    rate: float = Field(gt=0)


class PlanRequest(BaseModel):
    """Full description of a plan. The server keeps no state between requests."""
    demands: List[DemandIn]
    recipes: Dict[str, str] = {}  # node_id -> recipe name
    preferred: Dict[str, str] = {}  # item -> the recipe new nodes of it run (ticket 043); `recipes` wins
    merges: Dict[str, str] = {}  # source node_id -> target node_id
    clocks: Dict[str, List[Dict[str, Any]]] = {}  # node_id -> [{"clock": 1.0}, {"count": 1, "clock": 0.6}]
    inbound: List[DemandIn] = []  # production supplied from outside the plan, used before producing anything
    byproducts: Dict[str, Literal["use", "sink", "solve"]] = {}  # node_id -> what its by-products do
    byproducts_default: Literal["use", "sink"] = "sink"  # for nodes not in `byproducts`: "use" for Calculate
    logistics: Dict[str, Any] = {}  # {"settings": {belt_tier, pipe_tier, smart}, "layouts": {"<id>|in|out": ...}}


class IgnoredEntry(BaseModel):
    """A plan entry that no longer matches the graph (usually a stale saved plan)."""
    kind: Literal["recipe", "merge", "clock"]
    node_id: str
    reason: str
    dropped: bool = False  # on an input the current recipe doesn't use; the UI removes it quietly
    replacement: Optional[str] = None  # merges only: the new merge target


class PlanResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    ignored: List[IgnoredEntry] = []
    byproducts: Dict[str, str] = {}  # the by-product choices to keep in the plan (see resolved_byproduct_choices)
    logistics_resets: List[Dict[str, str]] = []  # edited layouts that no longer fit: [{key, reason}]


class RecipeInfo(BaseModel):
    name: str
    type: str
    building: str
    output_rate: float  # per building, of the requested item
    byproduct: bool  # the requested item is the recipe's by-product


class RecipeChoice(BaseModel):
    """An item made by more than one recipe, and the one its nodes run by default."""
    item: str
    default: str
    recipes: List[RecipeInfo]
