from typing import List

from sftools_service.domain.enums.item_categories import ItemCategory
from sftools_service.domain.enums.recipe_type import RecipeType
# from sftools_service.domain.models.recipe import Recipe  # creates circular import


class Item:
    def __init__(self, name: str, category: ItemCategory, stack_size: int, sink_points: int, recipes: list):
        self._name = name
        self._category = category
        self._stack_size = stack_size
        self._sink_points = sink_points
        self._recipes = recipes

    @property
    def name(self):
        return self._name

    @property
    def category(self):
        return self._category

    @property
    def stack_size(self):
        return self._stack_size

    @property
    def sink_points(self):
        return self._sink_points

    @property
    def recipes(self):
        return self._recipes

    @property
    def basic_recipe(self):
        return [r for r in self.recipes if r.type == RecipeType.BASIC][0]

    def add_recipe(self, recipe):
        self._recipes.append(recipe)

    def __repr__(self):
        return 'name: ' + self._name + '; category: ' + self._category.name + '; recipes: \n' + '\n'.join([str(r) for r in self._recipes if r.type == RecipeType.BASIC])
