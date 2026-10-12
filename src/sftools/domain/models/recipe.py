from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from sftools.domain.enums.demand_type import DemandType
from sftools.domain.enums.recipe_type import RecipeType
from sftools.domain.models.building import Building
from sftools.domain.models.demand import Demand
from sftools.domain.models.item import Item
from sftools.domain.models.production_node import ProductionNode

ItemRate = Tuple[Item, float]  # an item and its per-building rate (per minute)


@dataclass(eq=False, repr=False)  # identity equality: recipes are compared with `is`
class Recipe:
    """
    `product` is the main product and `byproducts` the other outputs, as listed in the game data
    (output1 and output2). A node can run a recipe for any of its outputs (e.g. Polymer Resin from
    the Fuel recipe), so the methods below take the item the node produces.
    """
    name: str
    building: Optional[Building]
    product: ItemRate
    byproducts: List[ItemRate] = field(default_factory=list)
    ingredients: List[ItemRate] = field(default_factory=list)
    type: RecipeType = RecipeType.BASIC

    @property
    def output_item(self) -> Item:
        """The recipe's main product."""
        return self.product[0]

    @property
    def output_rate(self) -> float:
        """Per-building rate of the main product."""
        return self.product[1]

    def outputs(self) -> List[ItemRate]:
        return [self.product, *self.byproducts]

    def produces(self, item_name: str) -> bool:
        return any(item.name == item_name for item, _ in self.outputs())

    def is_main_product(self, item_name: str) -> bool:
        return self.output_item.name == item_name

    def rate_of(self, item_name: str) -> float:
        for item, rate in self.outputs():
            if item.name == item_name:
                return rate
        raise ValueError(f'Recipe {self.name} does not produce {item_name}')

    def other_outputs(self, item_name: str) -> List[ItemRate]:
        """Outputs other than the one being produced."""
        return [(item, rate) for item, rate in self.outputs() if item.name != item_name]

    def generate_demands(self, scaler: float = 1.0, product_name: str = None) -> List[Demand]:
        product_name = product_name or self.output_item.name
        return [Demand(item.name, item, rate * scaler, DemandType.PRODUCE) for item, rate in self.ingredients] + [
            Demand(item.name, item, rate * scaler, DemandType.SINK) for item, rate in self.other_outputs(product_name)]

    def base_inputs(self):
        return [{"item": item.name, "rate": rate} for item, rate in self.ingredients]

    def generate_production_node(self, node_id: str, scaler: float = 1.0, product_name: str = None):
        product_name = product_name or self.output_item.name
        return ProductionNode(
            node_id=node_id,
            node_name=self.name,
            building=self.building,
            building_scale=scaler,
            output_item_name=product_name,
            base_output_rate=self.rate_of(product_name),
            base_power=self.building.power_for(self.name),
            base_inputs=self.base_inputs(),
            recipe=self
        )

    def __repr__(self):
        def listed(pairs):
            return ' & '.join(f'{item.name}[{rate}]' for item, rate in pairs)
        byproducts = f' >>> {listed(self.byproducts)}' if self.byproducts else ''
        return f'{self.name} <<< {listed(self.ingredients)}{byproducts}'
