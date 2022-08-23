from models.building import Building


class ProductionNode:
    def __init__(self, node_name: str, building: Building, building_scale: float, scaled_output: float, output_item_name: str, scaled_power: float):
        self._node_name = node_name
        self._building = building
        self._building_scale = building_scale
        self._scaled_output = scaled_output
        self._output_item_name = output_item_name
        self._scaled_power = scaled_power

    @property
    def name(self):
        return self._node_name

    @property
    def ing(self):
        return self._building

    @property
    def building_scale(self):
        return self._building_scale

    @property
    def scaled_output(self):
        return self._scaled_output

    @property
    def output_item_name(self):
        return self._output_item_name

    @property
    def scaled_power(self):
        return self._scaled_power

    def __add__(self, other: 'ProductionNode'):
        if self._node_name != other._node_name:
            raise TypeError('Cannot add ProductionNodes with different names')
        if self._building != other._building:
            raise TypeError('Cannot add ProductionNodes with different buildings')

        self._building_scale += other._building_scale
        self._scaled_power += other._scaled_power
        return self

    def __repr__(self):
        return self.name + ': {:6.2f}'.format(self._building_scale) + 'x' + self._building.name + ' -> {:6.2f}'.format(self._scaled_output) + ' of ' + self._output_item_name + ' at ' + '{:6.2f}'.format(self._scaled_power) + 'MW'
