import pytest
import os
from sftools_service.logic.demand_calculator import calculate_demands, load_models, DATA_PATH, recalculate_graph
from sftools_service.domain.models.demand import Demand
from sftools_service.domain.enums.demand_type import DemandType

@pytest.fixture(scope="module")
def data():
    return load_models(DATA_PATH)

def test_persistence_logic(data):
    items_map, recipes_map, buildings_map = data
    
    # 1. Setup a scenario with multiple nodes of same item
    root_demands = [
        Demand('Smart Plating', items_map['Smart Plating'], 2.0, DemandType.PRODUCE),
        Demand('Modular Frame', items_map['Modular Frame'], 2.0, DemandType.PRODUCE)
    ]
    
    # Initial calculation (tree structure)
    nodes = calculate_demands(items_map, root_demands, round_up=False)
    
    # Find the two RIP nodes
    rip_nodes = [n for n in nodes.values() if n.output_item_name == 'Reinforced Iron Plate']
    assert len(rip_nodes) == 2
    
    node_a = rip_nodes[0]
    node_b = rip_nodes[1]
    
    source_id = node_b.id
    target_id = node_a.id
    
    # 2. Simulate Merge (Absorption)
    node_a.absorb_node(node_b)
    del nodes[source_id]
    
    # Recalculate to verify consistency
    recalculate_graph(nodes, overrides={}, round_up=False)
    assert node_a.building_scale == pytest.approx(1.0)

    # 3. Test "Load" Simulation
    merges = {source_id: target_id}
    fresh_nodes = calculate_demands(items_map, root_demands, round_up=False)
    
    for s_id, t_id in merges.items():
        if s_id in fresh_nodes and t_id in fresh_nodes:
            s_node = fresh_nodes[s_id]
            t_node = fresh_nodes[t_id]
            t_node.absorb_node(s_node)
            del fresh_nodes[s_id]
            
    recalculate_graph(fresh_nodes, overrides={}, round_up=False)
    
    remaining_rip = [n for n in fresh_nodes.values() if n.output_item_name == 'Reinforced Iron Plate']
    assert len(remaining_rip) == 1
    reconstructed_node = remaining_rip[0]
    assert reconstructed_node.id == target_id
    assert reconstructed_node.building_scale == pytest.approx(1.0)

def test_flattening_merges():
    # This test focuses on the dictionary transformation logic (flattening)
    # as implemented in index.html
    
    id1 = "root__A"
    id2 = "root__B"
    id3 = "root__C"
    
    # Merge 1 -> 2
    merges = {id1: id2}
    
    # Merge 2 -> 3
    sourceId = id2
    targetId = id3
    
    for mid in list(merges.keys()):
        if merges[mid] == sourceId:
            merges[mid] = targetId
    merges[sourceId] = targetId
    
    assert merges[id1] == id3
    assert merges[id2] == id3

def test_persistence_with_overrides(data):
    items_map, _, _ = data
    
    root_demands = [
        Demand('Smart Plating', items_map['Smart Plating'], 2.0, DemandType.PRODUCE),
        Demand('Modular Frame', items_map['Modular Frame'], 2.0, DemandType.PRODUCE)
    ]
    
    nodes = calculate_demands(items_map, root_demands, round_up=False)
    rip_nodes = [n for n in nodes.values() if n.output_item_name == 'Reinforced Iron Plate']
    source_id = rip_nodes[1].id
    target_id = rip_nodes[0].id
    
    overrides = {target_id: 10.0}
    merges = {source_id: target_id}
    
    # Simulate api_calculate with merges and overrides
    fresh_nodes = calculate_demands(items_map, root_demands, round_up=False)
    
    # Apply merges
    for s_id, t_id in merges.items():
        if s_id in fresh_nodes and t_id in fresh_nodes:
            s_node = fresh_nodes[s_id]
            t_node = fresh_nodes[t_id]
            t_node.absorb_node(s_node)
            del fresh_nodes[s_id]
            
    # Apply overrides
    recalculate_graph(fresh_nodes, overrides=overrides, round_up=False)
    
    node = fresh_nodes[target_id]
    assert node.user_scale == 10.0
    assert node.building_scale == 10.0
    
    # Child of RIP (Screw) should scale up. 
    # 10 RIPs @ 60 Screws/each = 600. 
    # Screw recipe = 40/min output. 600/40 = 15.
    for child in node.children:
        if child.output_item_name == 'Screw':
            assert child.original_building_scale == pytest.approx(15.0)
