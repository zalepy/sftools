from sftools_service.domain.models.item import Item


class RecipeComponent:
    def __init__(self, item: Item, rate: float, stack: int,):
        self._item = item
        self._rate = rate
        self._stack = stack

    @property
    def item(self):
        return self._item

    @property
    def rate(self):
        return self._rate

    @property
    def stack(self):
        return self._stack

    def __repr__(self):
        return self.item.name + '[' + str(self.rate) + ']'
