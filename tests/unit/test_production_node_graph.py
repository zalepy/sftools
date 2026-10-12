import pytest
from unittest.mock import MagicMock
from sftools.domain.models.production_node import ProductionNode
from sftools.domain.models.building import Building

class TestProductionNodeGraph:
    
    def test_initial_state(self):
        building_mock = MagicMock(spec=Building)
        # Signature: id, name, building, scale, item_name, output_rate, power
        node = ProductionNode("id1", "TestNode", building_mock, 1.0, "Item", 10.0, 5.0)
        assert len(node.parents) == 0
        assert len(node.children) == 0
        assert node.original_building_scale == 1.0
        assert node.user_scale is None
        assert node.building_scale == 1.0

    def test_add_parent_and_child(self):
        building_mock = MagicMock(spec=Building)
        parent = ProductionNode("id_p", "Parent", building_mock, 1.0, "PItem", 10.0, 5.0)
        child = ProductionNode("id_c", "Child", building_mock, 1.0, "CItem", 10.0, 5.0)

        parent.add_child(child)
        child.add_parent(parent)

        assert child in parent.children
        assert parent in child.parents
