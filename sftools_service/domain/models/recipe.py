from typing import List, Dict, Optional

from sftools_service.domain.enums.recipe_type import RecipeType
from sftools_service.domain.models.building import Building
from sftools_service.domain.models.ingredient import Ingredient
from sftools_service.domain.models.item import Item
from sftools_service.domain.models.product import Product


class Recipe:
    def __init__(self, name: str, building: Building, product_1: Product, product_2: Product = None,
                 ingredient_1: Ingredient = None, ingredient_2: Ingredient = None, ingredient_3: Ingredient = None,
                 ingredient_4: Ingredient = None, ):
        self._name = name
        self._building = building
        self._product_1 = product_1
        self._product_2 = product_2
        self._ingredient_1 = ingredient_1
        self._ingredient_2 = ingredient_2
        self._ingredient_3 = ingredient_3
        self._ingredient_4 = ingredient_4
        self._type = RecipeType.ALTERNATE if self._name.count('Alternate') else RecipeType.BASIC

    @property
    def name(self):
        return self._name

    @property
    def type(self):
        return self._type

    @property
    def building(self):
        return self._building

    @property
    def product_1(self):
        return self._product_1

    @property
    def product_2(self):
        return self._product_2

    @property
    def ingredient_1(self):
        return self._ingredient_1

    @property
    def ingredient_2(self):
        return self._ingredient_2

    @property
    def ingredient_3(self):
        return self._ingredient_3

    @property
    def ingredient_4(self):
        return self._ingredient_4

    @property
    def ingredients(self) -> List[Ingredient]:
        return [ingredient for ingredient in [self.ingredient_1, self._ingredient_2, self._ingredient_3, self._ingredient_4] if ingredient]

    @property
    def products(self) -> List[Product]:
        return [product for product in [self.product_1, self.product_2] if product]

    def get_product_by_name(self, item_name: str) -> Optional[Product]:
        result = [p for p in self.products if p.item.name == item_name]
        if result:
            return result[0]
        return None

    def __repr__(self):
        return self._name + ' <<< ' + ' & '.join([str(i) for i in self.ingredients])
