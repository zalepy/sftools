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

    def generate_production_node(self, depth: int, y_pos: float):
        target_recipe_product = self.recipe.get_product_by_name(self.demand.item.name)
        return ProductionNode(target_recipe_product.item.name, target_recipe_product.item, self.recipe, self.scaler, depth, y_pos, [self.demand.uuid])
