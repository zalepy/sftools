from enums.demand_type import DemandType
from models.item import Item


class Demand:
    def __init__(self, name: str,  item: Item, rate: float, _type: DemandType):
        self._name = name
        self._item = item
        self._rate = rate
        self._type = _type

    @property
    def name(self):
        return self._name

    @property
    def item(self):
        return self._item

    @property
    def rate(self):
        return self._rate

    @property
    def type(self):
        return self._type

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
            self._rate = -self.rate
            if self._type == DemandType.PRODUCE:
                self._type = DemandType.SINK
            else:
                self._type = DemandType.PRODUCE

        return self

    def __repr__(self):
        return 'name: ' + self._name + '; rate: ' + str(self._rate) + '; type: ' + str(self._type) + '; item: ' + str(self._item)
