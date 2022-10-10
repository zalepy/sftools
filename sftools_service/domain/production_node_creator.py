from typing import Callable, Type

from sftools_service.domain.models.demand import Demand
from sftools_service.domain.models.production_node import ProductionNode
from sftools_service.domain.models.recipe import Recipe
from sftools_service.domain.scaler_calculator import ScalerCalculator


class ProductionNodeCreator:
    def __init__(self, demand: Demand, recipe: Recipe, scaler_calculator: Type[ScalerCalculator]):
        self._demand = demand
        self._recipe = recipe
        self._scaler_calculator = scaler_calculator
        self._scaler: float = self._scaler_calculator.get_scaler(self._demand, self._recipe)

    @property
    def demand(self) -> Demand:
        return self._demand

    @property
    def recipe(self) -> Recipe:
        return self._recipe

    @property
    def scaler(self) -> float:
        return self._scaler

    def generate_production_node(self, depth: int, target_output_name: str):
        if self.recipe.output2_item and self.recipe.output2_item.name == target_output_name:
            target_output_item = self.recipe.output2_item
            target_output_rate = self.recipe.output2_rate
        else:
            target_output_item = self.recipe.output1_item
            target_output_rate = self.recipe.output1_rate

        # if target_output_name not in (self.recipe.output1_item.name, self.recipe.output2_item.name):
        #     print(f'Warning: provided target output name {target_output_name} does not match any of the recipe outputs {self.recipe}')
        #     target_output_name = self.recipe.output1_item.name

        return ProductionNode(target_output_name, self.recipe.building, self.scaler, target_output_rate * self.scaler,
                              target_output_item, self.recipe.building.power_generated * self.scaler, depth, self.recipe)
