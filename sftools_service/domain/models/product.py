from sftools_service.domain.models.item import Item
from sftools_service.domain.models.recipe_component import RecipeComponent


class Product(RecipeComponent):
    def __init__(self, item: Item, rate: float, stack: int):
        super().__init__(item, rate, stack)
