from typing import Any, Dict, List, Literal, Optional

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
    splits: Dict[str, int] = {}  # node_id -> number of equal parts


class IgnoredEntry(BaseModel):
    """A plan entry that no longer matches the graph (usually a stale saved plan)."""
    kind: Literal["recipe", "merge", "override", "split"]
    node_id: str
    reason: str
    dropped: bool = False  # on an input the current recipe doesn't use; the UI removes it quietly
    replacement: Optional[str] = None  # merges only: the new merge target


class PlanResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    ignored: List[IgnoredEntry] = []


class RecipeInfo(BaseModel):
    name: str
    type: str
    building: str
    output_rate: float  # per building, of the requested item
    byproduct: bool  # the requested item is the recipe's by-product
