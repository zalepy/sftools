import pytest
import os
from sftools_service.logic.demand_calculator import calculate_demands, load_models
from sftools_service.domain.enums.demand_type import DemandType
from sftools_service.domain.models.demand import Demand


@pytest.fixture
def data():
    data_path = os.path.join(os.path.dirname(__file__), '../../data')
    return load_models(data_path)

def test_scaling_does_not_inflate_sub_demands(data):
    items, recipes, buildings = data
    
    # Concrete recipe: 45 Limestone -> 15 Concrete (Standard Basic Recipe)
    concrete_item = items['Concrete']
    rate = 20.0
    root_demands = [Demand('Concrete', concrete_item, rate, DemandType.PRODUCE)]
    
    # calculate_demands with round_up=True
    final_nodes, _ = calculate_demands(items, root_demands, round_up=True)
    
    # 20 required, recipe produces 15 per min.
    # 20 / 15 = 1.33... -> ceiling(1.33) = 2 buildings.
    
    concrete_nodes = [n for n in final_nodes.values() if n.name == 'Concrete']
    assert len(concrete_nodes) == 1
    concrete_node = concrete_nodes[0]
    
    assert concrete_node.building_scale == 2.0
    
    # Now check Limestone demand.
    # Since Limestone is a raw material, if it has no basic recipes it won't have a node.
    # But wait, in the new logic it ONLY selects BASIC recipes.
    # Limestone might have a Miner recipe which is BASIC.
    
    limestone_nodes = [n for n in final_nodes.values() if n.name == 'Limestone']
    if limestone_nodes:
        # If Limestone has a node (e.g. Miner), verify its output matches 2 * 45 = 90
        # However, many items like Limestone might not have a 'Basic' recipe in the data if they are considered raw
        # Let's check the child of the concrete node
        pass
    
    # Verify demand via scaled_inputs
    limestone_input = next((i for i in concrete_node.scaled_inputs if i['item'] == 'Limestone'), None)
    assert limestone_input is not None
    
    # 1 building of concrete needs 45/min Limestone. 
    # 2 buildings need 90/min.
    assert limestone_input['rate'] == 90.0
    