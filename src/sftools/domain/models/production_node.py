from typing import List, Dict
from sftools.domain.models.building import Building


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
        return self._user_scale if self._user_scale is not None else self._original_building_scale

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
        """Scaled power consumption/generation based on building_scale."""
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

    # --- Scale Adjustment ---
    
    def update_building_scale(self, new_scale: float):
        """
        Update the building scale. All scaled properties (output, power, inputs) 
        are automatically recomputed since they are derived properties.
        """
        self._original_building_scale = new_scale

    def clear_user_scale(self):
        self._user_scale = None

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
        self._base_power = recipe.building.power_generated
        self._base_inputs = recipe.base_inputs()

    # --- Operators ---

    def absorb_node(self, other: 'ProductionNode'):
        """
        Absorbs another ProductionNode into this one.
        This transfers all parents and children from 'other' to 'self',
        and updates those parents/children to point to 'self' instead.
        """
        if self._output_item_name != other._output_item_name:
            raise TypeError('Cannot merge ProductionNodes with different output items')
        
        # Transfer parents
        for parent in list(other.parents):
            # Remove from other's parents set
            other.parents.remove(parent)
            # Remove other from parent's children set
            if other in parent.children:
                parent.children.remove(other)
            
            # Add self to parent's children set if not already there
            parent.add_child(self)
            # Add parent to self's parents set
            self.add_parent(parent)

        # Transfer children
        for child in list(other.children):
            # Remove from other's children set
            other.children.remove(child)
            # Remove other from child's parents set
            if other in child.parents:
                child.parents.remove(other)
            
            # Add self to child's parents set if not already there
            child.add_parent(self)
            # Add child to self's children set
            self.add_child(child)

    def __add__(self, other: 'ProductionNode'):
        if self._node_name != other._node_name:
            raise TypeError('Cannot add ProductionNodes with different names')
        if self._building != other._building:
            raise TypeError('Cannot add ProductionNodes with different buildings')

        self._original_building_scale += other._original_building_scale
        # If adding nodes, user scale reset? or sum? 
        # Usually adding happens during initial construction.
        # Let's just sum original.
        self._parents.update(other._parents)
        self._children.update(other._children)
        return self

    def __repr__(self):
        return (
            f"{self.name}: {self.building_scale:6.2f}x {self._building.name} "
            f"-> {self.scaled_output:6.2f} of {self._output_item_name} "
            f"at {self.scaled_power:6.2f}MW"
        )
