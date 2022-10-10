from typing import List, Optional

from sftools_service.domain.enums.recipe_type import RecipeType
from sftools_service.domain.models.recipe import Recipe


class RecipeSelector:

    @classmethod
    def auto_pick_recipe(cls, recipes_list: List[Recipe], item_name: str) -> Optional[Recipe]:
        named = [r for r in recipes_list if r.name == item_name]
        if named:
            return named[0]
        typed = [r for r in recipes_list if r.type == RecipeType.BASIC]
        if typed:
            return typed[0]

        if recipes_list:
            return recipes_list[0]

        return None

    @classmethod
    def get_recipe(cls, recipes: List[Recipe], recipe_name: str):
        result = [r for r in recipes if r.name == recipe_name]
        if result:
            return result[0]

        return None
