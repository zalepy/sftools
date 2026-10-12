from enum import Enum


class RecipeType(Enum):
    BASIC = 0
    ALTERNATE = 1
    CONVERSION = 2
    OUTSIDE = 3  # supplied from outside the plan (see calculator.outside_supply_recipe)
