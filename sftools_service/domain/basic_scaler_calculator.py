from sftools_service.domain.models.demand import Demand
from sftools_service.domain.models.recipe import Recipe
from sftools_service.domain.scaler_calculator import ScalerCalculator


class BasicScalerCalculator(ScalerCalculator):

    @classmethod
    def get_scaler(cls, demand: Demand, recipe: Recipe) -> float:
        return demand.rate / recipe.output_rate
