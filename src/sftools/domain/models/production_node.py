import math
from typing import List, Dict, Optional, Tuple
from sftools.domain.models.building import Building

# Power draw at clock c is c ** k times the 100% draw (satisfactory.wiki.gg, "Clock speed": 1.321928 = log2 2.5
# since Update 7; 1.6 before). Worth confirming in game.
CLOCK_POWER_EXPONENT = 1.321928
SHARD_STEP = 0.5  # each power shard allows 50 more percentage points above 100%


class ProductionNode:
    """
    Represents a production node in the factory graph.
    
    Stores base recipe rates and computes scaled values internally based on building_scale.
    The building_scale represents the number of buildings (can be fractional) operating this recipe.
    """
    
    def __init__(
        self, 
        node_id: str, 
        node_name: str, 
        building: Building, 
        building_scale: float,
        output_item_name: str,
        base_output_rate: float,
        base_power: float,
        base_inputs: List[Dict] = None,
        recipe = None
    ):
        self._id = node_id
        self._node_name = node_name
        self._building = building
        self._original_building_scale = building_scale
        self._user_scale = None
        self._output_item_name = output_item_name
        
        # Base rates (per 1x building/recipe)
        self._base_output_rate = base_output_rate
        self._base_power = base_power
        self._base_inputs = base_inputs or []  # List of {"item": str, "rate": float}
        self._ideal_building_scale = building_scale # Default to same as initial
        
        # Graph relationships
        self._parents = set()
        self._children = set()
        self._parent_demands = {} # parent_id -> rate
        self._external_demand = None # rate demanded directly by the user (root nodes)
        self._building_clocks: Optional[List[Tuple[int, float]]] = None  # (count, clock) groups, see set_clocks

        # Stateful attributes
        self._absorbed_by = None # ID of the node this node is merged into
        self._recipe = recipe
        self._is_dormant = False

    @property
    def id(self):
        return self._id

    @property
    def absorbed_by(self):
        return self._absorbed_by

    @absorbed_by.setter
    def absorbed_by(self, value: str):
        self._absorbed_by = value

    @property
    def external_demand(self):
        return self._external_demand

    @external_demand.setter
    def external_demand(self, value: float):
        self._external_demand = value

    @property
    def parent_demands(self):
        return self._parent_demands

    @parent_demands.setter
    def parent_demands(self, value: Dict[str, float]):
        self._parent_demands = value

    @property
    def name(self):
        return self._node_name

    @property
    def building(self):
        return self._building

    @property
    def building_scale(self):
        """Building-equivalents at 100%: the sum of each building's clock (fractional without round-up)."""
        if self._user_scale is not None:
            return self._user_scale
        if self._building_clocks is not None:
            return sum(count * clock for count, clock in self._building_clocks)
        return self._original_building_scale

    def set_clocks(self, groups: Optional[List[Tuple[int, float]]]):
        """Whole buildings as (count, clock) groups, or None for a fractional scale (original_building_scale)."""
        self._building_clocks = [(count, clock) for count, clock in groups if count > 0] if groups is not None else None

    @property
    def building_clocks(self) -> Optional[List[Tuple[int, float]]]:
        if self._user_scale is not None:
            return None
        return self._building_clocks

    @property
    def buildings(self) -> float:
        """Number of buildings: whole when clocks are set, otherwise the (possibly fractional) scale."""
        if self.building_clocks is not None:
            return sum(count for count, _ in self.building_clocks)
        return self.building_scale

    @property
    def power_shards(self) -> int:
        if self.building_clocks is None:
            return 0
        return sum(count * max(0, math.ceil((clock - 1) / SHARD_STEP - 1e-9)) for count, clock in self.building_clocks)

    @property
    def original_building_scale(self):
        return self._original_building_scale

    @original_building_scale.setter
    def original_building_scale(self, value: float):
        self._original_building_scale = value

    @property
    def user_scale(self):
        return self._user_scale

    @user_scale.setter
    def user_scale(self, value: float):
        self._user_scale = value

    @property
    def ideal_building_scale(self):
        return self._ideal_building_scale

    @ideal_building_scale.setter
    def ideal_building_scale(self, value: float):
        self._ideal_building_scale = value

    @property
    def output_item_name(self):
        return self._output_item_name

    @property
    def recipe(self):
        return self._recipe

    @recipe.setter
    def recipe(self, value):
        self._recipe = value

    @property
    def is_dormant(self):
        return self._is_dormant

    @is_dormant.setter
    def is_dormant(self, value: bool):
        self._is_dormant = value

    # --- Computed Scaled Properties ---
    
    @property
    def scaled_output(self):
        """Scaled output rate based on building_scale."""
        return self._base_output_rate * self.building_scale

    @property
    def scaled_power(self):
        """Power of all buildings: each draws base power x clock ** CLOCK_POWER_EXPONENT."""
        if self.building_clocks is not None:
            return self._base_power * sum(count * clock ** CLOCK_POWER_EXPONENT for count, clock in self.building_clocks)
        return self._base_power * self.building_scale

    @property
    def scaled_inputs(self):
        """List of scaled input rates based on building_scale."""
        return [
            {"item": inp["item"], "rate": inp["rate"] * self.building_scale}
            for inp in self._base_inputs
        ]

    # --- Base Rate Accessors (for reference) ---
    
    @property
    def base_output_rate(self):
        return self._base_output_rate
    
    @property
    def base_power(self):
        return self._base_power
    
    @property
    def base_inputs(self):
        return self._base_inputs

    # --- Graph Relationships ---

    @property
    def parents(self):
        return self._parents

    @property
    def children(self):
        return self._children

    def add_parent(self, node: 'ProductionNode'):
        self._parents.add(node)

    def add_child(self, node: 'ProductionNode'):
        self._children.add(node)

    # --- Recipe ---

    def update_from_recipe(self, recipe):
        """
        Updates the node's base properties from a new recipe.
        Does NOT toggle dormancy, but prepares rates for the new state.
        """
        # The node keeps producing the same item; the new recipe may make it as main product or by-product.
        self._recipe = recipe
        self._node_name = recipe.name
        self._building = recipe.building
        self._base_output_rate = recipe.rate_of(self._output_item_name)
        self._base_power = recipe.building.power_for(recipe.name)
        self._base_inputs = recipe.base_inputs()

    def __repr__(self):
        return (
            f"{self.name}: {self.building_scale:6.2f}x {self._building.name} "
            f"-> {self.scaled_output:6.2f} of {self._output_item_name} "
            f"at {self.scaled_power:6.2f}MW"
        )
