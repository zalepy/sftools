from typing import Dict, List, Optional, Set
import math
from sftools.domain.models.production_node import ProductionNode

class FactoryGraph:
    """
    Manages a collection of ProductionNodes and their state (merges, overrides).
    Handles calculation and UI representation.
    """
    def __init__(self, nodes: Dict[str, ProductionNode] = None):
        self.all_nodes = nodes or {}
        self.merges: Dict[str, str] = {} # source_id -> target_id
        self.recipe_overrides: Dict[str, str] = {} # node_path -> recipe_name
        self._initial_structure: Dict[str, Dict[str, List[str]]] = {}

    def add_node(self, node: ProductionNode):
        self.all_nodes[node.id] = node

    def get_node(self, node_id: str) -> Optional[ProductionNode]:
        return self.all_nodes.get(node_id)

    def capture_initial_structure(self):
        """Records the parent/child relationships as they are right now."""
        self._initial_structure = {}
        for node_id, node in self.all_nodes.items():
            self._initial_structure[node_id] = {
                "parents": [p.id for p in node.parents],
                "children": [c.id for c in node.children]
            }

    def _reset_structure(self):
        """Restores all nodes to the captured initial structure."""
        if not self._initial_structure:
            return
            
        for node_id, node in self.all_nodes.items():
            node.parents.clear()
            node.children.clear()
            node.absorbed_by = None
            
            init = self._initial_structure.get(node_id)
            if init:
                for p_id in init["parents"]:
                    if p_id in self.all_nodes:
                        node.add_parent(self.all_nodes[p_id])
                for c_id in init["children"]:
                    if c_id in self.all_nodes:
                        node.add_child(self.all_nodes[c_id])

    def apply_merge(self, source_id: str, target_id: str):
        if source_id == target_id:
            return
        
        source = self.get_node(source_id)
        target = self.get_node(target_id)
        if not source or not target:
            return
        
        if source.output_item_name != target.output_item_name:
            raise ValueError(f"Cannot merge {source_id} and {target_id}: different output items")

        # Record merge
        self.merges[source_id] = target_id
        source.absorbed_by = target_id

        # Transfer External Demand
        source_ext = source.parent_demands.get("External Demand", 0)
        if source_ext > 0:
            target.parent_demands["External Demand"] = target.parent_demands.get("External Demand", 0) + source_ext
            source.parent_demands["External Demand"] = 0
        
        # Execute link transfer
        self._execute_merge_links(source, target)

    def _execute_merge_links(self, source: ProductionNode, target: ProductionNode):
        # Parents of source now point to target
        for parent in list(source.parents):
            if source in parent.children:
                parent.children.remove(source)
            parent.add_child(target)
            target.add_parent(parent)
            source.parents.discard(parent) # Clear link from source

        # Children of source now receive from target
        for child in list(source.children):
            if source in child.parents:
                child.parents.remove(source)
            child.add_parent(target)
            target.add_child(child)
            source.children.discard(child) # Clear link from source

    def remove_merge(self, source_id: str):
        """Removes a specific merge and rebuilds the structure from other merges."""
        if source_id not in self.merges:
            # Maybe it's a target? Remove all merges into this target
            to_remove = [s for s, t in self.merges.items() if t == source_id]
            for s in to_remove:
                del self.merges[s]
        else:
            del self.merges[source_id]

        # Rebuild structure
        self._rebuild_structure()

    def _rebuild_structure(self):
        """Full reset and re-application of all recorded merges."""
        self._reset_structure()
        for s_id, t_id in self.merges.items():
            source = self.get_node(s_id)
            target = self.get_node(t_id)
            if source and target:
                source.absorbed_by = t_id
                self._execute_merge_links(source, target)

    def set_subtree_dormancy(self, node_id: str, dormant: bool):
        """
        Recursively sets the dormancy state for a node and all its descendants.
        """
        node = self.get_node(node_id)
        if not node:
            return
            
        node.is_dormant = dormant
        for child in node.children:
            self.set_subtree_dormancy(child.id, dormant)

    def recalculate(self, overrides: Dict[str, float] = None, round_up: bool = False):
        """
        Propagates scales through the graph.
        Handles merges by treating the absorption target as the primary node.
        """
        # 1. Apply overrides
        for node_id, node in self.all_nodes.items():
            if overrides and node_id in overrides:
                node.user_scale = overrides[node_id]
            else:
                node.user_scale = None

        # 2. Topological Sort
        nodes_map = self.all_nodes
        in_degree = {node_id: 0 for node_id, n in nodes_map.items() if not n.is_dormant}
        for node_id, node in nodes_map.items():
            if node.is_dormant:
                continue
            for child in node.children:
                if child.id in in_degree:
                    in_degree[child.id] += 1
        
        # Initialize queue with nodes that have no active parents
        queue = []
        for node_id, degree in in_degree.items():
            if degree == 0:
                node = nodes_map[node_id]
                queue.append(node)
                
                # Update root scale based on External Demand
                external = node.parent_demands.get("External Demand", 0)
                if node.base_output_rate > 0:
                    base_scale = external / node.base_output_rate
                    if round_up:
                        node.original_building_scale = math.ceil(base_scale - 0.00001)
                        if node.original_building_scale == 0 and base_scale > 0:
                            node.original_building_scale = 1
                    else:
                        node.original_building_scale = base_scale
                    
                    node.ideal_building_scale = base_scale
                else:
                    # e.g. nodes with 0 output rate (sinks) or raw items without recipes
                    # If they are just roots without parents now, their scale should be 0 
                    # unless they are the actual designated root demands.
                    node.original_building_scale = 0
                    node.ideal_building_scale = 0

        while queue:
            current = queue.pop(0)
            
            # Current node's scale is final. Update its children's needs.
            for child in current.children:
                if child.id not in nodes_map or child.is_dormant:
                    continue
                
                # Re-sum required rates for child from all its parents
                sum_required_rate = 0.0
                
                # External Demand preservation
                external = child.parent_demands.get("External Demand", 0)
                child.parent_demands = {} 
                if external > 0:
                    child.parent_demands["External Demand"] = external
                    sum_required_rate += external

                for parent in child.parents:
                    if parent.id not in nodes_map or parent.is_dormant:
                        continue
                    # Use parent's effective scale
                    # If parent is absorbed, it shouldn't have children in our manipulated graph?
                    # Wait, apply_merge MOVES the children to the target.
                    # So 'current' in this loop will be the target node.
                    
                    for inp in parent.scaled_inputs:
                        if inp["item"] == child.output_item_name:
                            rate = inp["rate"]
                            sum_required_rate += rate
                            child.parent_demands[parent.id] = child.parent_demands.get(parent.id, 0) + rate
                
                if child.base_output_rate > 0:
                    base_scale = sum_required_rate / child.base_output_rate
                    if round_up:
                        child.original_building_scale = math.ceil(base_scale - 0.00001)
                        if child.original_building_scale == 0 and base_scale > 0:
                            child.original_building_scale = 1
                    else:
                        child.original_building_scale = base_scale
                    
                    child.ideal_building_scale = base_scale
                
                in_degree[child.id] -= 1
                if in_degree[child.id] == 0:
                    queue.append(child)

    def get_ui_data(self) -> List[Dict]:
        """
        Returns serialized nodes for the UI.
        Absorbed nodes are omitted from the flat list, 
        but their values are aggregated into their targets?
        Actually, the user said "overrides ... for merged nodes, should 'bubble up'".
        If A is absorbed by B, we only send B' to UI.
        B'.building_scale = B.scale + A.scale (if they were separate)
        Wait, if they are merged, they share the SAME scale if the override is applied to B.
        If B' has override 10, then A and B are both operating?
        No, usually a merge means they are combined into one physical factory.
        If A and B both had 1.0 scale originally, the merged node has 2.0.
        If the user overrides the merged node to 5.0, what happens?
        
        Let's treat the merged node as ONE entity in the UI.
        Backend: B is the representative. B's properties (throughput, power) = sum(B, A).
        """
        ui_nodes = []
        target_to_constituents: Dict[str, List[ProductionNode]] = {}
        
        for node in self.all_nodes.values():
            if node.absorbed_by:
                target_id = node.absorbed_by
                if target_id not in target_to_constituents:
                    target_to_constituents[target_id] = []
                target_to_constituents[target_id].append(node)
        
        for node in self.all_nodes.values():
            if node.absorbed_by or node.is_dormant:
                continue # Skip absorbed or dormant nodes from top level
                
            constituents = [c for c in target_to_constituents.get(node.id, []) if not c.is_dormant]
            
            # Serialize representative
            data = self._serialize_node(node)
            
            # Map parents and children to their merge targets for UI consistency
            data["parents"] = sorted(list(set(
                self.get_node(p_id).absorbed_by or p_id 
                for p_id in data["parents"] 
                if p_id in self.all_nodes
            )))
            data["children"] = sorted(list(set(
                self.get_node(c_id).absorbed_by or c_id 
                for c_id in data["children"] 
                if c_id in self.all_nodes
            )))

            # Mark if it's a merged node and track constituents
            data["is_merged"] = len(constituents) > 0
            data["constituent_ids"] = [c.id for c in constituents]
            
            # NOTE: Aggregation of scales/throughput is no longer needed 
            # as the representative node's parents/children set correctly 
            # accounts for the whole group demand.
            
            ui_nodes.append(data)
            
        return ui_nodes

    def _serialize_node(self, node: ProductionNode) -> Dict:
        return {
            "id": node.id,
            "name": node.name,
            "recipe_name": node.name.split('__')[-1] if '__' in node.name else node.name,
            "building": node.building.name,
            "building_scale": node.building_scale,
            "original_building_scale": node.original_building_scale,
            "user_scale": node.user_scale,
            "ideal_building_scale": node.ideal_building_scale,
            "throughput": node.scaled_output,
            "power": node.scaled_power,
            "output_item": node.output_item_name,
            "parents": [p.id for p in node.parents],
            "children": [c.id for c in node.children],
            "scaled_inputs": [inp.copy() for inp in node.scaled_inputs],
            "parent_demands": node.parent_demands.copy(),
            "base_output_rate": node.base_output_rate,
            "base_inputs": node.base_inputs,
            "base_power": node.base_power,
            "is_dormant": node.is_dormant
        }
