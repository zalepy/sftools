# 033 — Logistics mode (separate, advanced)

**Type:** feature · **Priority:** P3 · **Status:** Open · **Related:** [028](028-belts-and-pipes.md), 027

## Goal
An advanced mode that plans how items get from buildings to buildings: belt and pipe capacity ([028](028-belts-and-pipes.md)), splitting a node's output over the edges it feeds, and merging and splitting at the consumer to balance its buildings' inputs. The user chooses between the simple mode, which is the planner as it is today and doesn't consider belts at all, and this one.

## Decisions (2026-10-13)

### Modes
- **Isolated modes.** Logistics mode is a **separate page** (e.g. `/logistics`), sharing the engine and graph code, with a header link between the two. It has its own saved plan and export files (marked `mode: logistics`); each page refuses the other's files. Converting a plan from one mode to the other isn't supported: see how it turns out first, only then consider it.
- **Everything about belts is in this mode**, 028 included. The simple mode stays as it is today: no belts, pipes, splitters or mergers.
- **No Splits in logistics mode.** Splits stood for one node built in several places for reasons outside the demand chain (e.g. available space). Here that is done inside a logistics node, by keeping separate sets of buildings, each with its own splitters and belts, isolated from one another.

### Logistics nodes
- A **logistics node** isn't a graph node: it attaches to a production node, **one per side**: input on the left, output on the right, drawn as a small extra rectangle next to the node. Several input items (e.g. Steel Beam and Concrete) are independent sub-networks inside the one input-side node.
- **On the main graph it's symbolic**: one number for its inner complexity (splitters + mergers), and a mark when something is wrong (over capacity, unbalanced).
- **Selecting it** shows a summary and a **Zoom in** button. Zooming in gives the whole viewport to that logistics node; zooming out returns to the production planner.
- **Zoomed in**, the individual buildings, the splitters/mergers and the **exit belts** (for the output side; entry belts for the input side) are graph nodes. An exit belt stands for one outgoing edge of the production graph, e.g. the 36/min of Steel Beam for Encased Industrial Beam. Tools: add and delete splitters/mergers, drag a belt from one node to another (as belts are dragged in the game). Edge labels show the computed rates.
- **Both ends of an edge** meet at the main graph's edge: the producer's exit belt is the consumer's entry belt. That edge is where 028's capacity check sits (belt tier, number of belts).
- **Layout** (where things stand, belt routes, floors) is out of scope; a page of common layouts, or links to the wiki, at most.

### Defaults and changes
- **The tool computes a default**, which the user can adjust in the zoomed-in view:
  - output side: buildings grouped by destination (whole buildings per exit first, the remainder through one splitter, what's left overflowing to a buffer or the Sink), as in the Steel Beam example below;
  - input side: a manifold (a chain of splitters, n-1 for n buildings), not a balancer.
- **A change that affects a logistics node resets it to the default** (e.g. a demand change that changes its building count or edges), with a brief, unintrusive notice for a few seconds. Undo brings the user's version back if that wasn't intended.

### Rules modelled
- Flows: splitters divide evenly among outputs that aren't backed up, mergers share their inputs, overflow only spills when the main output is full. **Trees only** at first (manifolds, groups by destination); a loop-back (balancers such as the classic 5- or 7-way) is rejected or flagged until a later step.
- A **settings section** in the side panel: highest belt tier and pipe tier unlocked (dropdowns; belts Mk.1-6: 60/120/270/480/780/1200 per min, pipes Mk.1-2: 300/600 m³/min), a checkbox for smart/programmable splitters, and similar unlocks.
- Building ports (the data has input/output counts) rule out impossible layouts, e.g. one port needing more than its belt carries.
- Pipes: capacity only (no headlift or pumps).

## What it plans
- **Producer side, split to the edges.** A node's buildings are grouped by where their output goes, rather than every split being balanced at the consumer. Example: 5 Steel Beam Constructors make 75/min; 30/min go to Versatile Framework and 36/min to Encased Industrial Beam, and the other 9/min are buffered for Mk.3 belts and other building. Two Constructors (30) feed Versatile Framework exactly; two more plus 6/min of the fifth feed Encased Beam; the fifth's other 9/min overflow to storage.
- **Consumer side, merge and balance.** A consumer's buildings get their input balanced, from one or several producers.
- **Considered together, not in isolation.** How the producer side is merged changes which consumer-side splits are needed, so both ends of an edge are planned as one setup.
- **Remainders** that don't divide evenly (the 6 + 9 above) are handled with overflow (to a buffer, storage or the Sink) rather than exact ratios.

## Steps
1. The `/logistics` page: separate plan and files, settings section, no Splits, logistics-node symbols on the main graph.
2. Zoomed-in view, read-only: default layouts and the flow calculation (trees); 028's capacity checks on edges.
3. Editing in the zoomed-in view: add/delete splitters and mergers, drag belts; reset-to-default on changes, with the notice.
4. Later: balancers with loop-backs, smart/programmable splitters.

## Discussion
The answers above came from inline replies in this ticket (2026-10-13). On how to show it: "On one hand I want to keep representation small. [...] On the other hand the information we need to represent is significant, and the controls we need to provide are sophisticated. The most intuitive way I think about this is sort of 'zoom in' on the logistic node, and take the full viewport for the purpose of showing and manipulating the node."
