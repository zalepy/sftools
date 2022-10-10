from typing import List

from sftools_service.domain.enums.demand_type import DemandType
from sftools_service.domain.models.demand import Demand
from sftools_service.domain.models.production_node import ProductionNode
from sftools_service.domain.models.recipe import Recipe


class DemandCreator:
    def __init__(self, production_node: ProductionNode, recipe: Recipe):
        self._production_node = production_node
        self._recipe = recipe
        
    @property
    def production_node(self) -> ProductionNode:
        return self._production_node

    @property
    def recipe(self) -> Recipe:
        return self._recipe

    def generate_demands(self, depth: int, scaler: float = 1.0) -> List[Demand]:
        demands = []
        if self.recipe.ingredient1_item:
            demands.append(Demand(self.recipe.ingredient1_item.name, self.recipe.ingredient1_item, self.recipe.ingredient1_rate * scaler, DemandType.PRODUCE, depth, self.production_node))
        if self.recipe.ingredient2_item:
            demands.append(Demand(self.recipe.ingredient2_item.name, self.recipe.ingredient2_item, self.recipe.ingredient2_rate * scaler, DemandType.PRODUCE, depth, self.production_node))
        if self.recipe.ingredient3_item:
            demands.append(Demand(self.recipe.ingredient3_item.name, self.recipe.ingredient3_item, self.recipe.ingredient3_rate * scaler, DemandType.PRODUCE, depth, self.production_node))
        if self.recipe.ingredient4_item:
            demands.append(Demand(self.recipe.ingredient4_item.name, self.recipe.ingredient4_item, self.recipe.ingredient4_rate * scaler, DemandType.PRODUCE, depth, self.production_node))
        if self.recipe.sink_item:
            demands.append(Demand(self.recipe.sink_item.name, self.recipe.sink_item, self.recipe.sink_rate * scaler, DemandType.SINK, depth, self.production_node))

        return demands
