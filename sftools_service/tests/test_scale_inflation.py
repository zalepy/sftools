import pytest
import os
from sftools_service.logic.demand_calculator import find_production_and_demand, load_models, aggregate_models
from sftools_service.domain.enums.demand_type import DemandType
from sftools_service.domain.models.demand import Demand


@pytest.fixture
def data():
    data_path = os.path.join(os.path.dirname(__file__), '../../data')
    return load_models(data_path)

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

    # assert final_production_nodes.get('Limestone').building_scale == 1
    assert final_demand.get('Limestone').rate == 90.0
    # Explanation: 
    # 1. We start with 20 Concrete demand (/min).
    # 2. We find recipe and demand for Concrete, which is Limestone->Concrete and 45 Limestone /min.
    # 3. We find the output of the recipe for Concrete, which is 15 Concrete /min.
    # 4. Since demand is 20 and output is 15, we need to scale the production node by 20/15.
    # 5. We round up because the number of buildings must be an integer, and that results in scale factor of 2.
    # 6. We compute the demand for 2 buildings which is 90 Limestone /min.
    