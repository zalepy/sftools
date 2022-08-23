from enums.building_category import BuildingCategory


class Building:
    def __init__(self, name: str, category: BuildingCategory, power_generated: int, width: int, length: int, height: int, input: int = None, output: int = None):
        self._name = name
        self._category = category
        self._power_generated = power_generated
        self._width = width
        self._length = length
        self._height = height
        self._input = input
        self._output = output

    @property
    def name(self):
        return self._name

    @property
    def category(self):
        return self._category

    @property
    def power_generated(self):
        return self._power_generated

    @property
    def width(self):
        return self._width

    @property
    def length(self):
        return self._length

    @property
    def height(self):
        return self._height

    @property
    def input(self):
        return self._input

    @property
    def output(self):
        return self._output
