# sftools
tools for satisfactory

Current operation:
* scripts under `craw` scraped data from 'https://satisfactory-calculator.com' and store it under the `data` directory
* setup root demand in `calc_by_demand`
  ```
    root_demand_item = items['Smart Plating']
    root_demand = {'Smart Plating': Demand(name='Smart Plating', item=root_demand_item, rate=2.0, _type=DemandType.PRODUCE)}
  ```
    where `items` is loaded from the json stored in the `data` directory

Calculation:
Each step of the calculation involves objects of the following types:

Output
 - name
 - item
 - (output) rate (positive value) float
 - depth
 - producer = prod_node.name Optional - none implies raw resource

Demand
 - name
 - item
 - (demand) rate (positive value) float
 - depth
 - demander = prod_node.name Optional - none implies user demand

ProductionNode
 - name
 - item
 - recipe
 - (building) just passthrough for recipe.building
 - scaler
 - depth
 - scaled_demand_rates {recipe.ingredient1_item.name: scaler * recipe.ingredient1_rate, ...}
 - scaled_output_rates {recipe.output1_item.name: scaler * recipe.output1_rate, ...}
 - demand - demand.name
 - output - output.name
 - x_pos - derived from depth
 - y_pos - init input
 - position = (x_pos, y_pos)
 - label
 
 
Notes on calculation:
* number of buildings needed to satisfy the demand could be shown as `float` if no rounding is used
* rounding up is optional and controlled by ROUND_UP_SCALER_FLAG and selection of `ScalerCalculator`

Notes on drawing graph:
* Networx lib doesn't use conventional models for nodes/edges, but dict of dicts. Provided drawing methods operates on full list of elements, rather than a single element.
<br>Example: attribute `pos` is added via the `add_to_nx`/`add_node` method. To use that detail, have to call `poses = nx.get_node_attributes(production_graph, 'pos')`
which is then used in draw - `nx.draw(production_graph, pos=poses, with_labels=True)`
* The default labels referred to in `with_labels=True` are the node names. Adding extra "sub" labels has to be an extra draw call with:
`nx.draw_networkx_labels(production_graph, pos=label_poses, labels={pn.name: pn.label for pn in all_prod_nodes.values()}, font_size=6, font_color='r')`
where `label_poses` are derived by node positions with vertical offset of -0.05
* similar for edge labels

---
To start web server execute:
`waitress-serve --port=8000 "sftools_service.main:app"`

ATM issue: ProdNode has single output, while we want single node, tied to a recipe with two outputs, to show/link two outputs

Experiment with:
* generate without round up, then pass over backwards to aggregate and round up
* round up preference by Item e.g. need Aluminum Casing at 2.6 scaler which will be satisfied by 4 Aluminum Ingot Foundry, while rounding up to scaler 3.0 will add 5th Aluminum Ingot Foundry. So try `rounding_preference = {'Aluminum Casing': False}` 
* sub graphs based on building type
* add recipe property for depth based on the place in the longest prod line
* 
