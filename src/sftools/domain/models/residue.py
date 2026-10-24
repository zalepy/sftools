"""
Heavy Oil Residue left over is burned for power (ticket 055): the Sink can't take fluids, so the residue no
plan node uses goes to a Refinery running Residual Fuel (the node BURN_ID), which feeds Fuel Generators
(power.generator_nodes). The Refinery isn't part of the tree: FactoryGraph sizes it after everything else.
"""
RESIDUE = "Heavy Oil Residue"
BURN_RECIPE = "Residual Fuel"
BURN_ID = "burn"
GENERATORS_ID = "generators"
NEGLIGIBLE = 0.005  # as factory_graph.NEGLIGIBLE: less left over is rounding, not residue to burn


def makes_residue(node) -> bool:
    return node.recipe is not None and any(
        item.name == RESIDUE for item, _ in node.recipe.other_outputs(node.output_item_name))


def add_burner(graph, recipe):
    """The burn Refinery (running `recipe`), if a node of the plan makes Heavy Oil Residue as a by-product."""
    if recipe is None or BURN_ID in graph.all_nodes:
        return
    if any(not node.is_dormant and makes_residue(node) for node in graph.all_nodes.values()):
        graph.add_node(recipe.generate_production_node(BURN_ID, 0, recipe.output_item.name))


def burn(graph, round_up: bool):
    """
    Residue left over after its uses goes to the burn Refinery, recorded as a use of it
    (`graph.byproduct_used[(maker, RESIDUE)][BURN_ID]`), so it isn't sent to the Sink. The Refinery makes
    Fuel for the Generators (`parent_demands[GENERATORS_ID]`); with nothing to burn, it isn't shown.
    """
    burner = graph.all_nodes.get(BURN_ID)
    if burner is None:
        return
    residue = 0.0
    for node_id, node in graph.all_nodes.items():
        if node_id == BURN_ID or node.is_dormant or node.absorbed_by or not makes_residue(node):
            continue
        used = graph.byproduct_used.setdefault((node_id, RESIDUE), {})
        left = graph._byproduct_made(node_id, RESIDUE) - sum(used.values())
        if left >= NEGLIGIBLE:
            used[BURN_ID] = left
            residue += left
    per_building = next(inp["rate"] for inp in burner.base_inputs if inp["item"] == RESIDUE)
    fuel = residue / per_building * burner.base_output_rate
    burner.parent_demands = {GENERATORS_ID: fuel} if residue > 0 else {}
    graph._set_scale(burner, fuel, round_up)
    if residue <= 0:
        graph.unused.add(BURN_ID)
