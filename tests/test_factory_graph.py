import pytest
from unittest.mock import MagicMock
from sftools.domain.models.production_node import ProductionNode
from sftools.domain.models.building import Building
from sftools.domain.models.factory_graph import FactoryGraph

@pytest.fixture
def empty_graph():
    return FactoryGraph()

@pytest.fixture
def mock_building():
    b = MagicMock(spec=Building)
    b.name = "TestBuilding"
    return b

def test_apply_and_remove_merge(empty_graph, mock_building):
    # Setup 3 nodes: A -> C and B -> D 
    # (Simplified for testing links)
    a = ProductionNode("A", "NodeA", mock_building, 1.0, "Item1", 10.0, 5.0)
    b = ProductionNode("B", "NodeB", mock_building, 1.0, "Item1", 10.0, 5.0)
    c = ProductionNode("C", "NodeC", mock_building, 1.0, "Item2", 10.0, 5.0)
    d = ProductionNode("D", "NodeD", mock_building, 1.0, "Item2", 10.0, 5.0)
    
    a.add_child(c)
    c.add_parent(a)
    
    b.add_child(d)
    d.add_parent(b)
    
    empty_graph.add_node(a)
    empty_graph.add_node(b)
    empty_graph.add_node(c)
    empty_graph.add_node(d)
    
    empty_graph.capture_initial_structure()
    
    # Verify initial
    assert c in a.children
    assert d in b.children
    
    # 1. Merge A into B
    empty_graph.apply_merge("A", "B")
    
    assert a.absorbed_by == "B"
    assert "A" in empty_graph.merges
    
    # Link check: B should now have C as a child (transferred from A)
    assert c in b.children
    assert b in c.parents
    assert a not in c.parents
    
    # 2. Unmerge A
    empty_graph.remove_merge("A")
    
    assert a.absorbed_by is None
    assert "A" not in empty_graph.merges
    
    # Link check: restored to A -> C and B -> D
    assert c in a.children
    assert a in c.parents
    assert c not in b.children
    assert b not in c.parents
    assert d in b.children # B still has its own child

def test_recursive_merge_cleanup(empty_graph, mock_building):
    a = ProductionNode("A", "NodeA", mock_building, 1.0, "Item1", 10.0, 5.0)
    b = ProductionNode("B", "NodeB", mock_building, 1.0, "Item1", 10.0, 5.0)
    c = ProductionNode("C", "NodeC", mock_building, 1.0, "Item1", 10.0, 5.0)
    
    empty_graph.add_node(a)
    empty_graph.add_node(b)
    empty_graph.add_node(c)
    empty_graph.capture_initial_structure()
    
    # A -> B, then B -> C
    empty_graph.apply_merge("A", "B")
    empty_graph.apply_merge("B", "C")
    
    assert empty_graph.merges["A"] == "B"
    assert empty_graph.merges["B"] == "C"
    
    # Removing C (the target) should clear all merges into it?
    # Actually, my implementation of remove_merge(target_id) clears all source nodes targeting it.
    empty_graph.remove_merge("C")
    
    assert len(empty_graph.merges) == 1
    assert "B" not in empty_graph.merges
    assert "A" in empty_graph.merges
    assert empty_graph.get_node("B").absorbed_by is None
    assert empty_graph.get_node("A").absorbed_by == "B"

def test_ui_data_mapping(empty_graph, mock_building):
    # A -> B
    a = ProductionNode("A", "NodeA", mock_building, 1.0, "Item1", 10.0, 5.0)
    b = ProductionNode("B", "NodeB", mock_building, 1.0, "Item2", 10.0, 5.0)
    a.add_child(b)
    b.add_parent(a)
    
    # C -> D
    c = ProductionNode("C", "NodeC", mock_building, 1.0, "Item1", 10.0, 5.0)
    d = ProductionNode("D", "NodeD", mock_building, 1.0, "Item2", 10.0, 5.0)
    c.add_child(d)
    d.add_parent(c)

    empty_graph.add_node(a)
    empty_graph.add_node(b)
    empty_graph.add_node(c)
    empty_graph.add_node(d)
    empty_graph.capture_initial_structure()

    # Merge producers A and C into TargetA
    empty_graph.apply_merge("C", "A")
    # Merge consumers B and D into TargetB
    empty_graph.apply_merge("D", "B")

    ui_data = empty_graph.get_ui_data()
    assert len(ui_data) == 2 # Only A and B are active

    node_a_data = next(n for n in ui_data if n["id"] == "A")
    node_b_data = next(n for n in ui_data if n["id"] == "B")

    # A's child should be B (D was absorbed by B)
    assert "B" in node_a_data["children"]
    # B's parent should be A (C was absorbed by A)
    assert "A" in node_b_data["parents"]

def test_merge_scale_calculation(empty_graph, mock_building):
    # Node A needs 4, Node B needs 2. Both Stators.
    # Parent 1 needs 4 from A. Parent 2 needs 2 from B.
    p1 = ProductionNode("P1", "Parent1", mock_building, 1.0, "Root", 10.0, 5.0)
    p2 = ProductionNode("P2", "Parent2", mock_building, 1.0, "Root", 10.0, 5.0)
    
    # st_a and st_b output 1/min at 1.0 scale (for simplicity)
    st_a = ProductionNode("ST_A", "Stator", mock_building, 4.0, "Stator", 1.0, 5.0)
    st_b = ProductionNode("ST_B", "Stator", mock_building, 2.0, "Stator", 1.0, 5.0)
    
    # Simulate parent demands
    p1.add_child(st_a)
    st_a.add_parent(p1)
    # Mocking scaled_inputs since it's a derived property but we are testing graph logic
    # In real logic, Parent.scaled_inputs is derived from ITS scale.
    # Let's just mock the base_inputs of parents
    p1._base_inputs = [{"item": "Stator", "rate": 4.0}]
    p2._base_inputs = [{"item": "Stator", "rate": 2.0}]
    
    p2.add_child(st_b)
    st_b.add_parent(p2)
    
    # Root demands must have External Demand or they become 0 on recalculate
    p1.parent_demands["External Demand"] = 10.0 # 10/min of Root item
    p2.parent_demands["External Demand"] = 10.0
    
    empty_graph.add_node(p1)
    empty_graph.add_node(p2)
    empty_graph.add_node(st_a)
    empty_graph.add_node(st_b)
    empty_graph.capture_initial_structure()
    
    # Initial recalculate (A=4, B=2)
    empty_graph.recalculate()
    assert st_a.building_scale == 4.0
    assert st_b.building_scale == 2.0
    
    # Merge B into A
    empty_graph.apply_merge("ST_B", "ST_A")
    
    # Recalculate
    empty_graph.recalculate()
    
    # A should now be 6 (has both parents)
    assert st_a.building_scale == 6.0
    # B should be 0 (has no parents)
    # CURRENT BUG: st_b.building_scale might still be 2.0 because it's a root now
    assert st_b.building_scale == 0.0
    
    # UI Data check
    ui_nodes = empty_graph.get_ui_data()
    st_node_data = next(n for n in ui_nodes if n["id"] == "ST_A")
    # Should be 6 + 0 = 6
    assert st_node_data["building_scale"] == 6.0

def test_reported_bug_copper_ingots(empty_graph, mock_building):
    # Setup Structure: Root M/W -> Stator M/W -> Wire M/W -> CI M/W
    def create_chain(suffix, st_scale):
        root = ProductionNode(f"Root_{suffix}", "Motor", mock_building, 1.0, f"Root_{suffix}", 1.0, 5.0)
        stator = ProductionNode(f"ST_{suffix}", "Stator", mock_building, st_scale, "Stator", 1.0, 5.0)
        wire = ProductionNode(f"W_{suffix}", "Wire", mock_building, st_scale * 3, "Wire", 1.0, 5.0)
        ci = ProductionNode(f"CI_{suffix}", "Copper Ingot", mock_building, st_scale * 3 * 1.5, "Copper Ingot", 1.0, 5.0)
        
        # Connect
        root.add_child(stator); stator.add_parent(root)
        stator.add_child(wire); wire.add_parent(stator)
        wire.add_child(ci); ci.add_parent(wire)
        
        root.parent_demands["External Demand"] = 1.0 
        root._base_inputs = [{"item": "Stator", "rate": st_scale}] # Motor needs N stators
        stator._base_inputs = [{"item": "Wire", "rate": 3.0}] # 1 stator used 3 wires
        wire._base_inputs = [{"item": "Copper Ingot", "rate": 1.5}] # 1 wire used 1.5 ingots
        
        return root, stator, wire, ci

    rM, stM, wM, ciM = create_chain("M", 4.0)
    rW, stW, wW, ciW = create_chain("W", 1.5) # User says 1.5 rounded to 2

    for n in [rM, stM, wM, ciM, rW, stW, wW, ciW]: empty_graph.add_node(n)
    empty_graph.capture_initial_structure()
    
    # User Step 1: Merge Stators
    empty_graph.apply_merge("ST_W", "ST_M")
    empty_graph.recalculate(round_up=True)
    
    # stM should be ceil(4 + 1.5) = 6
    assert stM.building_scale == 6.0
    
    # User Step 2: Override Stator M to 7
    # Note: 7 Stators * 3 Wire/Stator = 21 Wire
    # BUT, Wire is NOT merged yet. wM and wW each see parent ST_M.
    # W_M will see ST_M outputting 21.0. W_W will see ST_M outputting 21.0.
    # THIS IS THE N:M INFLATION.
    empty_graph.recalculate(overrides={"ST_M": 7.0}, round_up=True)
    assert stM.building_scale == 7.0
    assert wM.building_scale == 21.0
    assert wW.building_scale == 21.0
    
    # User Step: Merge Wires
    empty_graph.apply_merge("W_W", "W_M")
    # Add a third wire node to match the "three nodes" in user report
    wC = ProductionNode("W_C", "Wire", mock_building, 0, "Wire", 1.0, 5.0)
    empty_graph.add_node(wC)
    empty_graph.apply_merge("W_C", "W_M")
    
    # User Step 3: Override Wire node scaler to 19.3334
    empty_graph.recalculate(overrides={"ST_M": 7.0, "W_M": 19.3334}, round_up=True)
    
    # CI needed = 19.3334 * 1.5 = 29.0001 -> Rounds to 30
    assert wM.building_scale == 19.3334
    assert ciM.original_building_scale == 30.0
    
    # User Step 4: Override CI node to 29
    # Merge CI nodes first
    empty_graph.apply_merge("CI_W", "CI_M")
    empty_graph.recalculate(overrides={"ST_M": 7.0, "W_M": 19.3334, "CI_M": 29.0}, round_up=True)
    
    assert ciM.user_scale == 29.0
    assert ciM.building_scale == 29.0
    
    ui_data = empty_graph.get_ui_data()
    ci_ui = next(n for n in ui_data if n["id"] == "CI_M")
    
    # THE BUG: This should be 29.0. If it's 49.0, we reproduced it!
    # (29.0 override + 20.0 from an incorrectly calculated constituent?)
    assert ci_ui["building_scale"] == 29.0
