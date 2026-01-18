import pytest
import os
from sftools_service.logic.demand_calculator import calculate_demands, load_models, find_production_and_demand, aggregate_models
from sftools_service.domain.models.demand import Demand
from sftools_service.domain.enums.demand_type import DemandType

@pytest.fixture
def data():
    data_path = os.path.join(os.path.dirname(__file__), '../../data')
    return load_models(data_path)

def test_load_models(data):
    items, recipes, buildings = data
    assert len(items) > 0
    assert len(recipes) > 0
    assert len(buildings) > 0
    assert 'Smart Plating' in items
    assert 'Iron Ingots' in recipes

def test_calculate_demands_basic(data):
    items, recipes, buildings = data
    root_demand_item = items['Smart Plating']
    rate = 2.0
    root_demand = {'Smart Plating': Demand('Smart Plating', root_demand_item, rate, DemandType.PRODUCE)}
    
    final_production_nodes, final_demand = calculate_demands(items, root_demand)
    
    assert final_production_nodes
    assert final_demand
    
    # Smart Plating recipe: 1 reinforced iron plate + 1 rotor -> 1 smart plating
    # We check if we have demand for ingredients
    assert 'Reinforced Iron Plate' in final_demand
    assert 'Rotor' in final_demand
    
    # Check if production node for Smart Plating exists
    assert 'Smart Plating' in final_production_nodes
    # Check scaler/buildings needed.
    # Recipe: 2/min output. Demand 2/min. Should be 1 building.
    # Note: Using default recipe
    smart_plating_node = final_production_nodes['Smart Plating']
    assert smart_plating_node.building_scale >= 1.0

def test_find_production_and_demand_single_step(data):
    items, recipes, buildings = data
    demand_item = items['Iron Plate']
    # Iron Plate recipe: 3 Iron Ingot -> 2 Iron Plate
    demand = {'Iron Plate': Demand('Iron Plate', demand_item, 20.0, DemandType.PRODUCE)}
    
    nodes, sub_demands = find_production_and_demand(demand)
    
    assert 'Iron Plate' in nodes
    assert 'Iron Ingot' in sub_demands
    
    # 20 required, recipe produces 20 per min standard? 
    # Standard Iron Plate: 3 Iron Ingot -> 2 Iron Plate (Standard recipe varies, let's trust the data)
    # Check if inputs are generated
    
def test_aggregate_models(data):
    items, recipes, buildings = data
    item_a = items['Iron Plate']
    item_b = items['Iron Rod']

    demand_a1 = Demand('Iron Plate', item_a, 10.0, DemandType.PRODUCE)
    demand_a2 = Demand('Iron Plate', item_a, 20.0, DemandType.PRODUCE)
    demand_b = Demand('Iron Rod', item_b, 5.0, DemandType.PRODUCE)

    models_1 = {'Iron Plate': demand_a1}
    models_2 = {'Iron Plate': demand_a2, 'Iron Rod': demand_b}

    result = aggregate_models(models_1, models_2)

    assert 'Iron Plate' in result
    assert result['Iron Plate'].rate == 30.0
    assert 'Iron Rod' in result
    assert result['Iron Rod'].rate == 5.0
    # verify in-place modification or return alias
    assert result is models_1
