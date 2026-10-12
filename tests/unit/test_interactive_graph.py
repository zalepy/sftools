import pytest
from sftools.engine.calculator import calculate_demands
from sftools.engine.loader import load_models
from sftools.domain.models.demand import Demand, DemandType

@pytest.fixture(scope="module")
def data_models():
    return load_models()

def test_graph_structure_and_ids(data_models):
    items, _, _ = data_models
    root_item = items['Smart Plating']
    root_demand = Demand('Smart Plating', root_item, 2.0, DemandType.PRODUCE)
    
    nodes = calculate_demands(items, [root_demand], round_up=True)
    
    # Check we have nodes
    assert len(nodes.all_nodes) > 0
    
    # Find Smart Plating Node
    sp_nodes = [n for n in nodes.all_nodes.values() if n.output_item_name == 'Smart Plating']
    assert len(sp_nodes) == 1
    sp_node = sp_nodes[0]
    
    # Check children (ingredients)
    # Smart Plating needs Reinforced Iron Plate and Rotor
    child_items = set(c.output_item_name for c in sp_node.children)
    assert 'Reinforced Iron Plate' in child_items
    assert 'Rotor' in child_items
    
    # IDs are item paths: the root is keyed by its item, children extend the parent's ID
    assert sp_node.id == 'Smart Plating'
    for child in sp_node.children:
        assert child.id == f"Smart Plating__{child.output_item_name}"

def test_overrides(data_models):
    items, _, _ = data_models
    root_item = items['Smart Plating']
    # 2.0 Smart Plating -> Need 2.0 Reinforced Plate + 2.0 Rotor (Standard Recipe)
    root_demand = Demand('Smart Plating', root_item, 2.0, DemandType.PRODUCE)
    
    # 1. Initial Calculation to get IDs
    nodes = calculate_demands(items, [root_demand], round_up=False)
    
    rotor_node = next(n for n in nodes.all_nodes.values() if n.output_item_name == 'Rotor')
    original_rate = rotor_node.scaled_output
    # Standard: 2 Smart Plating needs 2 Rotors.
    assert abs(original_rate - 2.0) < 0.001
    
    # 2. Apply Override using the NEW logic
    from sftools.engine.calculator import recalculate_graph
    
    # Recalculate based on overrides, propagating changes
    new_nodes = recalculate_graph(nodes, {rotor_node.id: 10.0})
    
    new_rotor_node = new_nodes.get_node(rotor_node.id)
    # user_scale should be 10.0
    assert new_rotor_node.user_scale == 10.0
    assert abs(new_rotor_node.building_scale - 10.0) < 0.001
    
    # Check downstream (ingredients of Rotor)
    # Rotor needs Iron Rod and Screw.
    # Implementation might have "Screw" or "Screws"
    screw_nodes = [c for c in new_rotor_node.children if "Screw" in c.output_item_name]
    assert len(screw_nodes) > 0
    screw_node = screw_nodes[0]
    
    # Verify propagation - original_building_scale should have increased
    # Default: 2 Rotors needed. Now 10 Rotors (user_scale).
    # Child's original_building_scale should have scaled up by 5x (from 2 to 10)
    assert screw_node.original_building_scale > 1.0 
    
    # Check NON-impacted nodes
    # Reinforced Iron Plate also uses Screws. check that they are NOT scaled up if they are separate nodes.
    # In tree mode, they should be separate nodes.
    
    rip_node = next(n for n in new_nodes.all_nodes.values() if n.output_item_name == 'Reinforced Iron Plate')
    rip_screw_node = next(c for c in rip_node.children if c.output_item_name == 'Screws')
    
    # RIP needs 12 Screws for 2 Plates (Standard: 5 Reinf. Plates = 60 Screws -> 1 = 12).
    # 2 RIP = 24 Screws.
    # This node should NOT be affected by Rotor override.
    assert abs(rip_screw_node.scaled_output - 24.0) < 0.01
    assert rip_screw_node.id != screw_node.id

def test_rounding_toggle(data_models):
    items, _, _ = data_models
    root = Demand('Smart Plating', items['Smart Plating'], 0.1, DemandType.PRODUCE)
    
    # With Rounding
    nodes_up = calculate_demands(items, [root], round_up=True)
    sp_node_up = next(n for n in nodes_up.all_nodes.values() if n.output_item_name == 'Smart Plating')
    assert sp_node_up.building_scale == 1.0 # Ceil(0.1 / 2.5) -> Ceil(0.04) -> 1
    
    # Without Rounding
    nodes_float = calculate_demands(items, [root], round_up=False)
    sp_node_float = next(n for n in nodes_float.all_nodes.values() if n.output_item_name == 'Smart Plating')
    assert sp_node_float.building_scale < 1.0
