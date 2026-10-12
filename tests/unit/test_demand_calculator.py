import pytest
from sftools.engine.calculator import calculate_demands
from sftools.engine.loader import load_models
from sftools.domain.models.demand import Demand
from sftools.domain.enums.demand_type import DemandType

@pytest.fixture
def data():
    return load_models()

def test_load_models(data):
    items, recipes, buildings = data
    assert len(items) > 0
    assert len(recipes) > 0
    assert len(buildings) > 0
    assert 'Smart Plating' in items
    assert 'Iron Plate' in recipes

def test_calculate_demands_basic(data):
    items, recipes, buildings = data
    root_demand_item = items['Smart Plating']
    rate = 2.0
    # New signature takes a List[Demand]
    root_demands = [Demand('Smart Plating', root_demand_item, rate, DemandType.PRODUCE)]
    
    final_production_nodes = calculate_demands(items, root_demands)
    
    assert final_production_nodes
    
    # Smart Plating recipe: 1 reinforced iron plate + 1 rotor -> 1 smart plating
    # In the new logic, node IDs are f"{parent_path}__{recipe.name}"
    # For a root, parent_path is "root"
    
    # Let's find the smart plating node
    smart_plating_nodes = [node for node in final_production_nodes.all_nodes.values() if node.name == 'Smart Plating']
    assert len(smart_plating_nodes) > 0
    node = smart_plating_nodes[0]
    
    assert node.building_scale >= 1.0
    
    # Check if children (ingredients) were created
    # Reinforced Iron Plate and Rotor should be in the graph
    child_names = [child.name for child in node.children]
    assert 'Reinforced Iron Plate' in child_names
    assert 'Rotor' in child_names

def test_calculate_demands_with_overrides(data):
    items, recipes, buildings = data
    root_demand_item = items['Smart Plating']
    rate = 2.0
    root_demands = [Demand('Smart Plating', root_demand_item, rate, DemandType.PRODUCE)]
    
    # First get the node ID
    initial_nodes = calculate_demands(items, root_demands, round_up=True)
    smart_plating_node_id = next(nid for nid, node in initial_nodes.all_nodes.items() if node.name == 'Smart Plating')
    
    # Apply override via recalculate_graph
    from sftools.engine.calculator import recalculate_graph
    final_nodes = recalculate_graph(initial_nodes, {smart_plating_node_id: 5.0})
    
    assert final_nodes.get_node(smart_plating_node_id).user_scale == 5.0
    assert final_nodes.get_node(smart_plating_node_id).building_scale == 5.0
