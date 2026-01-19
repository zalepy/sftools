from typing import List, Dict
from sftools_service.domain.models.building import Building


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
        base_inputs: List[Dict] = None
    ):
        self._id = node_id
        self._node_name = node_name
        self._building = building
        self._building_scale = building_scale
        self._output_item_name = output_item_name
        
        # Base rates (per 1x building/recipe)
        self._base_output_rate = base_output_rate
        self._base_power = base_power
        self._base_inputs = base_inputs or []  # List of {"item": str, "rate": float}
        
        # Graph relationships
        self._parents = set()
        self._children = set()

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._node_name

    @property
    def building(self):
        return self._building

    @property
    def building_scale(self):
        return self._building_scale

    @property
    def output_item_name(self):
        return self._output_item_name

    # --- Computed Scaled Properties ---
    
    @property
    def scaled_output(self):
        """Scaled output rate based on building_scale."""
        return self._base_output_rate * self._building_scale

    @property
    def scaled_power(self):
        """Scaled power consumption/generation based on building_scale."""
        return self._base_power * self._building_scale

    @property
    def scaled_inputs(self):
        """List of scaled input rates based on building_scale."""
        return [
            {"item": inp["item"], "rate": inp["rate"] * self._building_scale}
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

    # --- Scale Adjustment ---
    
    def update_building_scale(self, new_scale: float):
        """
        Update the building scale. All scaled properties (output, power, inputs) 
        are automatically recomputed since they are derived properties.
        """
        self._building_scale = new_scale

    # --- Operators ---

    def __add__(self, other: 'ProductionNode'):
        if self._node_name != other._node_name:
            raise TypeError('Cannot add ProductionNodes with different names')
        if self._building != other._building:
            raise TypeError('Cannot add ProductionNodes with different buildings')

        self._building_scale += other._building_scale
        self._parents.update(other._parents)
        self._children.update(other._children)
        return self

    def __repr__(self):
        return (
            f"{self.name}: {self._building_scale:6.2f}x {self._building.name} "
            f"-> {self.scaled_output:6.2f} of {self._output_item_name} "
            f"at {self.scaled_power:6.2f}MW"
        )
