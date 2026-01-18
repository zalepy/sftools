import pytest
from unittest.mock import MagicMock
from sftools_service.domain.models.production_node import ProductionNode
from sftools_service.domain.models.building import Building

class TestProductionNodeGraph:
    
    def test_initial_state(self):
        building_mock = MagicMock(spec=Building)
        node = ProductionNode("TestNode", building_mock, 1.0, 10.0, "Item", 5.0)
        assert len(node.parents) == 0
        assert len(node.children) == 0

    def test_add_parent_and_child(self):
        building_mock = MagicMock(spec=Building)
        parent = ProductionNode("Parent", building_mock, 1.0, 10.0, "PItem", 5.0)
        child = ProductionNode("Child", building_mock, 1.0, 10.0, "CItem", 5.0)

        parent.add_child(child)
        child.add_parent(parent)

        assert child in parent.children
        assert parent in child.parents

    def test_add_operator_merges_links(self):
        building_mock = MagicMock(spec=Building)
        # Equality check in __add__ relies on objects being same or __eq__
        # Mocks might not compare equal unless it's the same instance.
        
        node_a1 = ProductionNode("Iron Ingots", building_mock, 1.0, 30.0, "Iron Ingot", 4.0)
        node_a2 = ProductionNode("Iron Ingots", building_mock, 2.0, 60.0, "Iron Ingot", 8.0)
        
        child_1 = ProductionNode("Child1", building_mock, 1.0, 30.0, "Ore", 4.0)
        child_2 = ProductionNode("Child2", building_mock, 1.0, 30.0, "Coal", 4.0)
        
        parent_1 = ProductionNode("Parent1", building_mock, 1.0, 30.0, "Plate", 4.0)

        # A1 has Child1
        node_a1.add_child(child_1)
        # A2 has Child2 and Parent1
        node_a2.add_child(child_2)
        node_a2.add_parent(parent_1)

        # Merge A1 + A2
        # Note: __add__ modifies the left operand (node_a1)
        result = node_a1 + node_a2

        assert result is node_a1
        assert result.building_scale == 3.0
        
        # Check Children merged
        assert child_1 in result.children
        assert child_2 in result.children
        assert len(result.children) == 2

        # Check Parents merged
        assert parent_1 in result.parents
        assert len(result.parents) == 1

