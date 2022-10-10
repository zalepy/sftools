from typing import Optional

from sftools_service.domain.models.building import Building
from sftools_service.domain.models.item import Item
from sftools_service.domain.models.recipe import Recipe


class ProductionNode:
    def __init__(self, node_name: str, building: Building, building_scale: float, scaled_output: float, output_item: Item, scaled_power: float, depth: int, recipe: Optional[Recipe]):
        self._node_name = node_name
        self._building = building
        self._building_scale = building_scale
        self._scaled_output = scaled_output
        self._output_item = output_item
        self._scaled_power = scaled_power
        self._depth = depth
        self._recipe = recipe

    @property
    def name(self) -> str:
        return self._node_name

    @property
    def building(self) -> Building:
        return self._building

    @property
    def building_scale(self) -> float:
        return self._building_scale

    @property
    def scaled_output(self) -> float:
        return self._scaled_output

    @property
    def output_item(self) -> Item:
        return self._output_item

    @property
    def scaled_power(self) -> float:
        return self._scaled_power

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def recipe(self) -> Optional[Recipe]:
        return self._recipe

    @property
    def nx_name(self) -> str:
        return f'[{self.depth}] {self.name}'

    def __add__(self, other: 'ProductionNode'):
        if self._node_name != other._node_name:
            raise TypeError('Cannot add ProductionNodes with different names')
        if self._building != other._building:
            raise TypeError('Cannot add ProductionNodes with different buildings')

        self._building_scale += other._building_scale
        self._scaled_output += other._scaled_output
        self._scaled_power += other._scaled_power
        return self

    def __repr__(self):
        return self.name + ': {:6.2f}'.format(self.building_scale) + 'x' + self.building.name + ' -> {:6.2f}'.format(self.scaled_output) + ' of ' + str(self.output_item.name) + ' at ' + '{:6.2f}'.format(self.scaled_power) + 'MW'
