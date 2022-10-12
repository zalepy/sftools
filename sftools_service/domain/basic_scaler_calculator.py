from sftools_service.domain.models.demand import Demand
from sftools_service.domain.models.recipe import Recipe
from sftools_service.domain.scaler_calculator import ScalerCalculator


class BasicScalerCalculator(ScalerCalculator):

    @classmethod
    def get_scaler(cls, demand: Demand, recipe: Recipe) -> float:
        target_recipe_product = recipe.get_product_by_name(demand.item.name)
        return demand.rate / target_recipe_product.rate
