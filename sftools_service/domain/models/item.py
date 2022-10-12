from typing import List

from sftools_service.domain.enums.item_categories import ItemCategory
# from sftools_service.domain.models.recipe import Recipe  # (most likely due to a circular import)


class Item:
    def __init__(self, name: str, category: ItemCategory, stack_size: int, sink_points: int, recipe_names: list):
        self._name = name
        self._category = category
        self._stack_size = stack_size
        self._sink_points = sink_points
        self._recipes = recipe_names

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

    def add_recipe(self, recipe):
        self._recipes.append(recipe)

    def __repr__(self):
        return 'name: ' + self.name + '; category: ' + self.category.name + '; recipes: \n' + '\n'.join([r.name for r in self.recipes])
