import pytest
from calc_by_demand import find_production_and_demand, load_models, aggregate_models
from sftools_service.domain.enums.demand_type import DemandType
from sftools_service.domain.models.demand import Demand


@pytest.fixture
def data():
    return load_models('../../data/')

def test_scaling_does_not_inflate_sub_demands(data):
    items, recipes, buildings = data
    root_demand = {'Concrete': Demand('Concrete', items['Concrete'], 20.0, DemandType.PRODUCE)}
    new_demand = root_demand
    final_demand = root_demand
    final_production_nodes = {}
    for depth in range(10):
        new_nodes, new_demand = find_production_and_demand(new_demand)
        print('new nodes:', new_nodes, '\nnew demand', new_demand)
        # aggregate
        final_demand = aggregate_models(final_demand, new_demand)
        final_production_nodes = aggregate_models(final_production_nodes, new_nodes)

    assert final_production_nodes.get('Limestone').building_scale == 1
    assert final_demand.get('Limestone').rate == 60.0