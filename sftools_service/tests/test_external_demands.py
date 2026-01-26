import pytest
import os
from sftools_service.logic.demand_calculator import calculate_demands, load_models
from sftools_service.domain.models.demand import Demand
from sftools_service.domain.enums.demand_type import DemandType

@pytest.fixture
def data():
    data_path = os.path.join(os.path.dirname(__file__), '../../data')
    return load_models(data_path)

def test_distinct_external_demands(data):
    items, recipes, buildings = data
    iron_plate = items['Iron Plate']
    
    # Request Iron Plate twice as root
    root_demands = [
        Demand('Iron Plate 1', iron_plate, 10.0, DemandType.PRODUCE),
        Demand('Iron Plate 2', iron_plate, 20.0, DemandType.PRODUCE)
    ]
    
    graph = calculate_demands(items, root_demands)
    
    # Verify there are two distinct Iron Plate nodes in the graph
    iron_plate_nodes = [node for node in graph.all_nodes.values() if node.output_item_name == 'Iron Plate']
    
    # We expect at least 2. (They might have children too, but those are sub-demands)
    # Actually, Iron Plate with basic recipe might be a leaf if it's considered raw or has no basic recipe.
    # Iron Plate needs Iron Ingot.
    
    # Filter for nodes that have "External Demand"
    external_nodes = [node for node in graph.all_nodes.values() if "External Demand" in node.parent_demands]
    
    assert len(external_nodes) == 2
    assert external_nodes[0].id != external_nodes[1].id
    assert external_nodes[0].output_item_name == 'Iron Plate'
    assert external_nodes[1].output_item_name == 'Iron Plate'

def test_root_vs_child_distinct(data):
    items, recipes, buildings = data
    reinforced_plate = items['Reinforced Iron Plate']
    iron_plate = items['Iron Plate']
    
    # Reinforced Iron Plate needs Iron Plate.
    # Request both as root.
    root_demands = [
        Demand('Reinforced', reinforced_plate, 5.0, DemandType.PRODUCE),
        Demand('Plates', iron_plate, 10.0, DemandType.PRODUCE)
    ]
    
    graph = calculate_demands(items, root_demands)
    
    # Filter for nodes that have "External Demand"
    external_nodes = [node for node in graph.all_nodes.values() if "External Demand" in node.parent_demands]
    assert len(external_nodes) == 2
    
    # Verify that the Iron Plate node used as ingredient for Reinforced Iron Plate is SEPARATE
    # from the Iron Plate node that is a root demand.
    
    all_iron_plate_nodes = [node for node in graph.all_nodes.values() if node.output_item_name == 'Iron Plate']
    # 1 for root, 1 for Reinforced Iron Plate ingredient = 2
    # Wait, Reinforced Iron Plate also needs Screw? Iron Plate? 
    # Basic RP recipe: 6 Iron Plate + 12 Screw -> 1 RP.
    assert len(all_iron_plate_nodes) >= 2
    
    # One should be external, one should not.
    ext_ip = [n for n in all_iron_plate_nodes if "External Demand" in n.parent_demands]
    child_ip = [n for n in all_iron_plate_nodes if "External Demand" not in n.parent_demands]
    
    assert len(ext_ip) == 1
    assert len(child_ip) >= 1
