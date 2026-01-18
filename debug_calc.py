from calc_by_demand import load_models, calculate_demands, DATA_PATH
from sftools_service.domain.models.demand import Demand
from sftools_service.domain.enums.demand_type import DemandType

def debug():
    print("Loading data...")
    items_map, recipes_map, buildings_map = load_models(DATA_PATH)
    
    root_demand = {}
    item_name = "Smart Plating"
    rate = 2.0
    item = items_map.get(item_name)
    if not item:
        print(f"Item {item_name} not found")
        return

    root_demand[item_name] = Demand(item_name, item, rate, DemandType.PRODUCE)
    
    print("Calculating...")
    final_production_nodes, sub_demands = calculate_demands(items_map, root_demand)
    
    print("Nodes type:", type(final_production_nodes))
    if final_production_nodes:
        first_key = list(final_production_nodes.keys())[0]
        first_val = final_production_nodes[first_key]
        print("First node key:", first_key)
        print("First node value type:", type(first_val))
        print("First node value:", first_val)
        
        if hasattr(first_val, 'num_buildings'):
            print("Has num_buildings")
        else:
            print("No num_buildings attribute")
            
        if isinstance(first_val, tuple):
             print("IT IS A TUPLE!", first_val)

if __name__ == "__main__":
    debug()
