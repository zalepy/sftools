from typing import Optional

from sftools_service.domain.enums.demand_type import DemandType
from sftools_service.domain.models.item import Item
from sftools_service.domain.models.production_node import ProductionNode


class Demand:
    def __init__(self, name: str,  item: Item, rate: float, _type: DemandType, depth: int, demander: Optional[ProductionNode] = None):
        self._name = name
        self._item = item
        self._rate = rate
        self._type = _type
        self._depth = depth
        self._demander = demander

    @property
    def name(self) -> str:
        return self._name

    @property
    def item(self) -> Item:
        return self._item

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def type(self) -> DemandType:
        return self._type

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def demander(self) -> Optional[ProductionNode]:
        return self._demander

    @property
    def nx_name(self) -> str:
        return f'[D{self.depth}] {self.name}'

    def __add__(self, other: 'Demand'):
        if self._name != other.name:
            raise TypeError('Cannot add demands with different names')
        if self._item != other.item:
            raise TypeError('Cannot add demands with different items')

        # handle type mismatch
        if self._type == other.type:
            self._rate += other.rate
        else:
            self._rate -= other._rate

        # handle negative rate
        if self._rate < 0:
            self._rate = abs(self._rate)
            if self._type == DemandType.PRODUCE:
                self._type = DemandType.SINK
            else:
                self._type = DemandType.PRODUCE

        return self

    def __repr__(self):
        return 'name: ' + self._name + '; rate: ' + str(self._rate) + '; type: ' + str(self._type) + '; item: ' + str(self._item)
