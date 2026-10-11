from typing import List

from sftools.domain.enums.demand_type import DemandType
from sftools.domain.enums.recipe_type import RecipeType
from sftools.domain.models.building import Building
from sftools.domain.models.demand import Demand
from sftools.domain.models.item import Item
from sftools.domain.models.production_node import ProductionNode


class Recipe:
    def __init__(self,
                 name: str,
                 building: Building,
                 output1_item: Item,
                 output1_rate: float,
                 output1_stack: int,
                 output2_item: Item = None,
                 output2_rate: float = None,
                 output2_stack: int = None,
                 ingredient1_item: Item = None,
                 ingredient1_rate: float = None,
                 ingredient1_stack: int = None,
                 ingredient2_item: Item = None,
                 ingredient2_rate: float = None,
                 ingredient2_stack: int = None,
                 ingredient3_item: Item = None,
                 ingredient3_rate: float = None,
                 ingredient3_stack: int = None,
                 ingredient4_item: Item = None,
                 ingredient4_rate: float = None,
                 ingredient4_stack: int = None,
                 recipe_type: RecipeType = None
                 ):
        self._name = name
        self._building = building
        self._output1_item = output1_item
        self._output1_rate = output1_rate
        self._output1_stack = output1_stack
        self._output2_item = output2_item
        self._output2_rate = output2_rate
        self._output2_stack = output2_stack
        self._ingredient1_item = ingredient1_item
        self._ingredient1_rate = ingredient1_rate
        self._ingredient1_stack = ingredient1_stack
        self._ingredient2_item = ingredient2_item
        self._ingredient2_rate = ingredient2_rate
        self._ingredient2_stack = ingredient2_stack
        self._ingredient3_item = ingredient3_item
        self._ingredient3_rate = ingredient3_rate
        self._ingredient3_stack = ingredient3_stack
        self._ingredient4_item = ingredient4_item
        self._ingredient4_rate = ingredient4_rate
        self._ingredient4_stack = ingredient4_stack

        if recipe_type:
            self._type = recipe_type
        else:
            self._type = RecipeType.ALTERNATE if self._name.count('Alternate') else RecipeType.BASIC

    @property
    def name(self):
        return self._name

    @property
    def type(self):
        return self._type

    @property
    def building(self):
        return self._building

    # --- Outputs -----------------------------------------------------------------------------------------------
    # output1 is the main product and output2 the optional by-product, as listed in the game data.
    # A node can run a recipe for either output (e.g. Polymer Resin from the Fuel recipe), so the
    # methods below take the item the node produces.

    @property
    def output_item(self):
        """The recipe's main product."""
        return self._output1_item

    @property
    def output_rate(self):
        """Per-building rate of the main product."""
        return self._output1_rate

    def outputs(self):
        return [(item, rate) for item, rate in ((self._output1_item, self._output1_rate),
                                                 (self._output2_item, self._output2_rate)) if item]

    def produces(self, item_name: str) -> bool:
        return any(item.name == item_name for item, _ in self.outputs())

    def is_main_product(self, item_name: str) -> bool:
        return self._output1_item is not None and self._output1_item.name == item_name

    def rate_of(self, item_name: str):
        for item, rate in self.outputs():
            if item.name == item_name:
                return rate
        raise ValueError(f'Recipe {self._name} does not produce {item_name}')

    def byproducts(self, item_name: str):
        """Outputs other than the one being produced."""
        return [(item, rate) for item, rate in self.outputs() if item.name != item_name]

    def generate_demands(self, scaler: float = 1.0, product_name: str = None) -> List[Demand]:
        product_name = product_name or self._output1_item.name
        demands = []
        for item, rate in self.ingredients():
            demands.append(Demand(item.name, item, rate * scaler, DemandType.PRODUCE))
        for item, rate in self.byproducts(product_name):
            demands.append(Demand(item.name, item, rate * scaler, DemandType.SINK))

        return demands

    def ingredients(self):
        return [(item, rate) for item, rate in (
            (self._ingredient1_item, self._ingredient1_rate),
            (self._ingredient2_item, self._ingredient2_rate),
            (self._ingredient3_item, self._ingredient3_rate),
            (self._ingredient4_item, self._ingredient4_rate),
        ) if item]

    def base_inputs(self):
        return [{"item": item.name, "rate": rate} for item, rate in self.ingredients()]

    def generate_production_node(self, node_id: str, scaler: float = 1.0, product_name: str = None):
        product_name = product_name or self._output1_item.name
        return ProductionNode(
            node_id=node_id,
            node_name=self._name,
            building=self.building,
            building_scale=scaler,
            output_item_name=product_name,
            base_output_rate=self.rate_of(product_name),
            base_power=self.building.power_for(self._name),
            base_inputs=self.base_inputs(),
            recipe=self
        )

    # ----------------------------------------------------------------------------------------------------------------

    @property
    def output1_item(self):
        return self._output1_item

    @property
    def output1_rate(self):
        return self._output1_rate

    @property
    def output1_stack(self):
        return self._output1_stack

    @property
    def output2_item(self):
        return self._output2_item

    @property
    def output2_rate(self):
        return self._output2_rate

    @property
    def output2_stack(self):
        return self._output2_stack

    @property
    def ingredient1_item(self):
        return self._ingredient1_item

    @property
    def ingredient1_rate(self):
        return self._ingredient1_rate

    @property
    def ingredient1_stack(self):
        return self._ingredient1_stack

    @property
    def ingredient2_item(self):
        return self._ingredient2_item

    @property
    def ingredient2_rate(self):
        return self._ingredient2_rate

    @property
    def ingredient2_stack(self):
        return self._ingredient2_stack

    @property
    def ingredient3_item(self):
        return self._ingredient3_item

    @property
    def ingredient3_rate(self):
        return self._ingredient3_rate

    @property
    def ingredient3_stack(self):
        return self._ingredient3_stack

    @property
    def ingredient4_item(self):
        return self._ingredient4_item

    @property
    def ingredient4_rate(self):
        return self._ingredient4_rate

    @property
    def ingredient4_stack(self):
        return self._ingredient4_stack

    def __repr_ingredients(self):
        result = ''
        if self._ingredient1_item:
            result += self._ingredient1_item.name + '[' + str(self._ingredient1_rate) + ']'

        if self._ingredient2_item:
            result += ' & ' + self._ingredient2_item.name + '[' + str(self._ingredient2_rate) + ']'

        if self._ingredient3_item:
            result += ' & ' + self._ingredient3_item.name + '[' + str(self._ingredient3_rate) + ']'

        if self._ingredient4_item:
            result += ' & ' + self._ingredient4_item.name + '[' + str(self._ingredient4_rate) + ']'

        if self._output2_item:
            result += ' >>> ' + self._output2_item.name + '[' + str(self._output2_rate) + ']'

        return result

    def __repr__(self):
        return self._name + ' <<< ' + self.__repr_ingredients()
