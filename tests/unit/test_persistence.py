import pytest
from sftools.engine.calculator import calculate_demands, recalculate_graph
from sftools.engine.loader import load_models
from sftools.domain.models.demand import Demand
from sftools.domain.enums.demand_type import DemandType

@pytest.fixture(scope="module")
def data():
    return load_models()

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
    rip_nodes = [n for n in nodes.all_nodes.values() if n.output_item_name == 'Reinforced Iron Plate']
    assert len(rip_nodes) == 2
    
    node_a = rip_nodes[0]
    node_b = rip_nodes[1]
    
    source_id = node_b.id
    target_id = node_a.id
    
    # 2. Simulate Merge (Absorption)
    nodes.apply_merge(source_id, target_id)
    
    # Recalculate to verify consistency
    recalculate_graph(nodes, overrides={}, round_up=False)
    assert node_a.building_scale == pytest.approx(1.0)

    # 3. Test "Load" Simulation
    merges = {source_id: target_id}
    fresh_nodes = calculate_demands(items_map, root_demands, round_up=False)
    
    for s_id, t_id in merges.items():
        fresh_nodes.apply_merge(s_id, t_id)
            
    recalculate_graph(fresh_nodes, overrides={}, round_up=False)
    
    remaining_rip = [n for n in fresh_nodes.all_nodes.values() if n.output_item_name == 'Reinforced Iron Plate' and not n.absorbed_by]
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
    rip_nodes = [n for n in nodes.all_nodes.values() if n.output_item_name == 'Reinforced Iron Plate']
    source_id = rip_nodes[1].id
    target_id = rip_nodes[0].id
    
    overrides = {target_id: 10.0}
    merges = {source_id: target_id}
    
    # Simulate api_calculate with merges and overrides
    fresh_nodes = calculate_demands(items_map, root_demands, round_up=False)
    
    # Apply merges
    for s_id, t_id in merges.items():
        fresh_nodes.apply_merge(s_id, t_id)
            
    # Apply overrides
    recalculate_graph(fresh_nodes, overrides=overrides, round_up=False)
    
    node = fresh_nodes.get_node(target_id)
    assert node.user_scale == 10.0
    assert node.building_scale == 10.0
    
    # Child of RIP (Screw) should scale up. 
    # 10 RIPs @ 60 Screws/each = 600. 
    # Screw recipe = 40/min output. 600/40 = 15.
    for child in node.children:
        if child.output_item_name == 'Screw':
            assert child.original_building_scale == pytest.approx(15.0)

def test_unmerge_flow(data):
    items_map, _, _ = data
    
    # 1. Setup initial graph
    root_demands = [
        Demand('Smart Plating', items_map['Smart Plating'], 2.0, DemandType.PRODUCE),
        Demand('Modular Frame', items_map['Modular Frame'], 2.0, DemandType.PRODUCE)
    ]
    
    initial_nodes = calculate_demands(items_map, root_demands, round_up=False)
    initial_ids = set(initial_nodes.all_nodes.keys())
    initial_rip_scales = {n.id: n.original_building_scale for n in initial_nodes.all_nodes.values() if n.output_item_name == 'Reinforced Iron Plate'}
    assert len(initial_rip_scales) == 2
    
    # 2. Perform Merge
    rip_ids = list(initial_rip_scales.keys())
    source_id = rip_ids[1]
    target_id = rip_ids[0]
    
    merges = {source_id: target_id}
    
    # Simulate first build with merge
    merged_nodes = calculate_demands(items_map, root_demands, round_up=False)
    for s_id, t_id in merges.items():
        merged_nodes.apply_merge(s_id, t_id)
    
    recalculate_graph(merged_nodes, overrides={}, round_up=False)
    
    assert source_id in merged_nodes.all_nodes
    assert target_id in merged_nodes.all_nodes
    assert merged_nodes.get_node(source_id).absorbed_by == target_id
    # Sum of scales should be correct (e.g. 0.5 + 0.5 = 1.0)
    expected_sum = sum(initial_rip_scales.values())
    # Note: building_scale on the node itself is its OWN scale. 
    # The UI representation sums them up.
    # In recalculate, nodes are separate?
    # Wait, my FactoryGraph.recalculate treats them as separate nodes unless merged?
    # Yes, but merges REDIRECT children to target.
    # So target.building_scale will depend on its own needs + source's needs.
    # If initial_rip_scales were [0.5, 0.5], and they are merged into target:
    # target now needs to satisfy all consumers.
    # So target.building_scale should be 1.0.
    assert merged_nodes.get_node(target_id).building_scale == pytest.approx(expected_sum)
    
    # 3. Perform Unmerge (simulate backend logic)
    # Remove the specific merge
    keys_to_remove = [s_id for s_id, t_id in merges.items() if t_id == target_id]
    for k in keys_to_remove:
        del merges[k]
        
    # Full rebuild
    unmerged_nodes = calculate_demands(items_map, root_demands, round_up=False)
    # Re-apply remaining merges (if any)
    for s_id, t_id in merges.items():
        unmerged_nodes.apply_merge(s_id, t_id)
            
    recalculate_graph(unmerged_nodes, overrides={}, round_up=False)
    
    # 4. Compare to initial
    assert set(unmerged_nodes.all_nodes.keys()) == initial_ids
    for node_id, node in unmerged_nodes.all_nodes.items():
        assert node.original_building_scale == pytest.approx(initial_nodes.get_node(node_id).original_building_scale)

def test_unmerge_with_overrides(data):
    items_map, _, _ = data
    
    root_demands = [
        Demand('Smart Plating', items_map['Smart Plating'], 2.0, DemandType.PRODUCE),
        Demand('Modular Frame', items_map['Modular Frame'], 2.0, DemandType.PRODUCE)
    ]
    
    # 1. Setup initial graph
    nodes = calculate_demands(items_map, root_demands, round_up=False)
    rip_nodes = [n for n in nodes.all_nodes.values() if n.output_item_name == 'Reinforced Iron Plate']
    source_id = rip_nodes[1].id
    target_id = rip_nodes[0].id
    
    # 2. Add override to the target
    overrides = {target_id: 100.0}
    recalculate_graph(nodes, overrides=overrides, round_up=False)
    assert nodes.get_node(target_id).user_scale == 100.0
    
    # 3. Perform Merge
    # In practice, merge transfers links. Recalculate will apply the override.
    fresh_nodes = calculate_demands(items_map, root_demands, round_up=False)
    fresh_nodes.apply_merge(source_id, target_id)
    
    recalculate_graph(fresh_nodes, overrides=overrides, round_up=False)
    assert fresh_nodes.get_node(target_id).building_scale == 100.0 # Override wins
    
    # 4. Perform Unmerge (unmerge instruction removed, overrides preserved)
    # The logic in api_unmerge_node: rebuild and re-apply overrides
    unmerged_nodes = calculate_demands(items_map, root_demands, round_up=False)
    # No merges applied here to simulate the unmerged state
    recalculate_graph(unmerged_nodes, overrides=overrides, round_up=False)
    
    assert source_id in unmerged_nodes.all_nodes
    assert target_id in unmerged_nodes.all_nodes
    assert unmerged_nodes.get_node(target_id).user_scale == 100.0
    assert unmerged_nodes.get_node(target_id).building_scale == 100.0
    assert unmerged_nodes.get_node(source_id).user_scale is None
    # Source node should have its original calculated scale (Modular Frame needs 3.0 RIP, recipe is 5.0, so 3/5 = 0.6)
    assert unmerged_nodes.get_node(source_id).original_building_scale == pytest.approx(0.6) 
