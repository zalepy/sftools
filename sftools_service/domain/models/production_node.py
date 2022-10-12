import random
import uuid
from typing import List

from sftools_service.domain.models.building import Building
from sftools_service.domain.models.item import Item
from sftools_service.domain.models.recipe import Recipe


HORIZONTAL_NODE_SEPARATION_STEP = 0.1
HORIZONTAL_NODE_VARIATION = 0.01


class ProductionNode:
    def __init__(self, node_name: str, item: Item, recipe: Recipe, scaler: float, depth: int, y_pos: float, outbound_links: List[str], inbound_links: List[str] = None):
        self._node_name = node_name
        self._item = item
        self._recipe = recipe
        self._building = recipe.building
        self._scaler = scaler
        self._depth = depth
        self._x_pos = 1 - self._depth * HORIZONTAL_NODE_SEPARATION_STEP + random.uniform(-HORIZONTAL_NODE_VARIATION, HORIZONTAL_NODE_VARIATION)
        self._y_pos = y_pos
        self._outbound_links = outbound_links  # downstream - the Demands that were the basis for creating this node
        self._inbound_links = inbound_links  # upstream - Outputs that satisfy this production
        self._scaled_output_rate = self._scaler * recipe.get_product_by_name(self._item.name).rate
        self._scaled_power = self._scaler * self._building.power_generated
        self._label = '{:6.2f}'.format(self._scaler) + 'x' + self._building.name + ' -> {:6.2f}'.format(self._scaled_output_rate) + ' of ' + self._item.name
        self._uuid = uuid.uuid4()

    @property
    def uuid(self):
        return self._uuid

    @property
    def name(self) -> str:
        return self._node_name

    @name.setter
    def name(self, name):
        self._node_name = name

    @property
    def item(self) -> Item:
        return self._item

    @property
    def recipe(self) -> Recipe:
        return self._recipe

    @property
    def building(self) -> Building:
        return self._building

    @property
    def scaler(self) -> float:
        return self._scaler

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def y_pos(self):
        return self._y_pos

    @y_pos.setter
    def y_pos(self, y_pos):
        self._y_pos = y_pos

    @property
    def position(self):
        return self._x_pos, self._y_pos

    @property
    def outbound_links(self):
        return self._outbound_links

    @property
    def inbound_links(self):
        return self._inbound_links

    @inbound_links.setter
    def inbound_links(self, inbound_links):
        self._inbound_links = inbound_links

    @property
    def scaled_output_rate(self):
        return self._scaled_output_rate

    @property
    def scaled_power(self):
        return self._scaled_power

    @property
    def nx_name(self) -> str:
        return f'[{self.depth}] {self.name}'

    @property
    def label(self):
        return self._label

    def __repr__(self):
        return self.name + ': {:6.2f}'.format(self.scaler) + 'x' + self.building.name + ' -> {:6.2f}'.format(self.scaled_output_rate) + ' of ' + str(self.item.name) + ' at ' + '{:6.2f}'.format(self.scaled_power) + 'MW'

    def add_to_nx(self, production_graph):
        production_graph.add_node(self.name, pos=self.position, node_size=300 * self.scaler)
