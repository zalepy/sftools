import pytest
import math
from sftools_service.logic.demand_calculator import calculate_demands, recalculate_graph, load_models, DATA_PATH
from sftools_service.domain.models.demand import Demand
from sftools_service.domain.enums.demand_type import DemandType

@pytest.fixture(scope="module")
def project_data():
    return load_models(DATA_PATH)

def test_basic_recalculation(project_data):
    items_map, recipes_map, buildings_map = project_data
    
    # Root: Smart Plating (2/min)
    root_item = items_map['Smart Plating']
    root_demand = Demand('Smart Plating', root_item, 2.0, DemandType.PRODUCE)
    
    # 1. Base Calculation
    nodes, _ = calculate_demands(items_map, [root_demand], round_up=False)
    
    # Find root node ID
    root_node_id = next(nid for nid, n in nodes.items() if n.output_item_name == 'Smart Plating')
    root_node = nodes[root_node_id]
    
    # Smart Plating recipe produces 2/min at 1.0 scale.
    # So 2/min demand = 1.0 scale.
    assert root_node.building_scale == pytest.approx(1.0)
    
    # 2. Recalculate with Override
    # Double the root scale
    overrides = {root_node_id: 2.0}
    recalculate_graph(nodes, overrides)
    
    assert root_node.user_scale == 2.0
    assert root_node.building_scale == 2.0
    
    # Check children - they should have doubled in original_building_scale
    for child in root_node.children:
        # Before: child produced for 1.0 parent
        # Now: child produces for 2.0 parent
        # Since parent scale doubled, child's required original_scale should double
        # (Assuming initial original_scale was correct)
        
        # We need to know previous scale. Let's just check relative.
        # But we can check specific item. Smart Plating needs Reinforced Iron Plate (2/min) and Rotor (2/min).
        # At 2.0 scale, it needs 4/min of each.
        if child.output_item_name == 'Reinforced Iron Plate':
            # Reinforced Iron Plate recipe produces 5/min at 1.0 scale.
            # 4/min required = 0.8 scale.
            assert child.original_building_scale == pytest.approx(0.8)

def test_complex_propagation(project_data):
    items_map, recipes_map, buildings_map = project_data
    
    # Root: Modular Frame (2/min)
    root_item = items_map['Modular Frame']
    root_demand = Demand('Modular Frame', root_item, 2.0, DemandType.PRODUCE)
    
    nodes, _ = calculate_demands(items_map, [root_demand], round_up=False)
    
    root_node_id = next(nid for nid, n in nodes.items() if n.output_item_name == 'Modular Frame')
    root_node = nodes[root_node_id]
    
    # Override a deep child
    # Find a Reinforced Iron Plate node (consumed by Modular Frame)
    rip_node = next(n for n in root_node.children if n.output_item_name == 'Reinforced Iron Plate')
    
    overrides = {rip_node.id: 5.0} # Set RIP to 5 buildings
    recalculate_graph(nodes, overrides)
    
    assert rip_node.user_scale == 5.0
    # Child of RIP (e.g. Iron Plate or Screw) should now scale relative to 5.0 RIPs
    for child in rip_node.children:
        # RIP needs 30/min Screws at 1.0 scale.
        # At 5.0 scale, it needs 150/min Screws.
        if child.output_item_name == 'Screw':
            # Screw recipe produces 40/min at 1.0 scale.
            # 150/min / 40/min = 3.75 scale.
            assert child.original_building_scale == pytest.approx(3.75)

def test_clearing_overrides(project_data):
    items_map, _, _ = project_data
    root_item = items_map['Smart Plating']
    root_demand = Demand('Smart Plating', root_item, 2.0, DemandType.PRODUCE)
    
    nodes, _ = calculate_demands(items_map, [root_demand], round_up=False)
    root_node_id = next(nid for nid, n in nodes.items() if n.output_item_name == 'Smart Plating')
    
    # Apply override
    recalculate_graph(nodes, {root_node_id: 10.0})
    assert nodes[root_node_id].building_scale == 10.0
    
    # Clear override
    recalculate_graph(nodes, {})
    assert nodes[root_node_id].user_scale is None
    assert nodes[root_node_id].building_scale == pytest.approx(1.0)
