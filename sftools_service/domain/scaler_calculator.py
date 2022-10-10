from abc import ABC, abstractmethod

from sftools_service.domain.models.demand import Demand
from sftools_service.domain.models.recipe import Recipe


class ScalerCalculator(ABC):

    @classmethod
    @abstractmethod
    def get_scaler(cls, demand: Demand, recipe: Recipe) -> float:
        return NotImplemented
