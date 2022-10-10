from sftools_service.domain.models.demand import Demand
from sftools_service.domain.models.recipe import Recipe
from sftools_service.domain.scaler_calculator import ScalerCalculator


class RoundupScalerCalculator(ScalerCalculator):

    @classmethod
    def get_scaler(cls, demand: Demand, recipe: Recipe) -> float:
        buildings_needed = demand.rate // recipe.output_rate
        if demand.rate % recipe.output_rate:
            buildings_needed += 1

        return buildings_needed
