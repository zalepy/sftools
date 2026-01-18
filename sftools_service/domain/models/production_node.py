from sftools_service.domain.models.building import Building


class ProductionNode:
    def __init__(self, node_id: str, node_name: str, building: Building, building_scale: float, scaled_output: float, output_item_name: str, scaled_power: float):
        self._id = node_id
        self._node_name = node_name
        self._building = building
        self._building_scale = building_scale
        self._scaled_output = scaled_output
        self._output_item_name = output_item_name
        self._scaled_power = scaled_power
        self._parents = set()
        self._children = set()

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._node_name

    @property
    def building(self):
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

    @property
    def parents(self):
        return self._parents

    @property
    def children(self):
        return self._children

    def add_parent(self, node: 'ProductionNode'):
        self._parents.add(node)

    def add_child(self, node: 'ProductionNode'):
        self._children.add(node)

    def __add__(self, other: 'ProductionNode'):
        if self._node_name != other._node_name:
            raise TypeError('Cannot add ProductionNodes with different names')
        if self._building != other._building:
            raise TypeError('Cannot add ProductionNodes with different buildings')

        self._building_scale += other._building_scale
        self._scaled_power += other._scaled_power
        self._parents.update(other._parents)
        self._children.update(other._children)
        return self

    def __repr__(self):
        return self.name + ': {:6.2f}'.format(self._building_scale) + 'x' + self._building.name + ' -> {:6.2f}'.format(self._scaled_output) + ' of ' + self._output_item_name + ' at ' + '{:6.2f}'.format(self._scaled_power) + 'MW'
