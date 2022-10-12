import uuid
from typing import Optional

from sftools_service.domain.models.item import Item


class Output:
    def __init__(self, name: str,  item: Item, rate: float, depth: int, demander_name: str = None):
        self._name = name
        self._item = item
        self._rate = rate
        self._depth = depth
        self._demander = demander_name
        self._uuid = uuid.uuid4()

    @property
    def uuid(self):
        return self._uuid

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
    def depth(self) -> int:
        return self._depth

    @property
    def demander(self) -> Optional[str]:
        return self._demander

    # @property
    # def nx_name(self) -> str:
    #     return f'[D{self.depth}] {self.name}'

    def __add__(self, other: 'Output'):
        if self._name != other.name:
            raise TypeError('Cannot add demands with different names')
        if self._item != other.item:
            raise TypeError('Cannot add demands with different items')

        self._rate += other.rate

        return self

    def __repr__(self):
        return 'name: ' + self._name + '; rate: ' + str(self._rate) + '; item: ' + str(self._item)
