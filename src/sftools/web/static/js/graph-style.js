// The main graph's Cytoscape stylesheet: node colors, status badges, merge and selection marks.
export const GRAPH_STYLE = [
    {
        selector: 'node',
        style: {
            'background-color': 'data(backgroundColor)',
            'border-width': 2,
            'border-color': '#f59e0b',
            'label': 'data(label)',
            'color': 'data(textColor)',
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'width': 150,
            'height': 80,
            'shape': 'round-rectangle',
            'font-size': '12px'
        }
    },
    {
        // Status dot, only on nodes that have one
        selector: 'node[backgroundImage]',
        style: {
            'background-image': 'data(backgroundImage)',
            'background-clip': 'node',
            'background-position-x': '0px',
            'background-position-y': '0px'
        }
    },
    {
        selector: 'edge',
        style: {
            'width': 2,
            'line-color': '#475569',
            'target-arrow-color': '#475569',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'color': '#94a3b8',
            'font-size': '10px',
            'text-background-opacity': 1,
            'text-background-color': '#0f172a',
            'text-background-padding': '2px'
        }
    },
    {
        selector: '.clocked',
        style: {
            'border-color': '#22d3ee',
            'border-style': 'dashed'
        }
    },
    {
        // A demand target (a demand row), fed by the node that makes it
        selector: '.demand',
        style: {
            'shape': 'ellipse',
            'width': 110,
            'height': 110,
            'border-width': 3,
            'border-color': '#a855f7'
        }
    },
    {
        // Inbound production: supplied from outside the plan
        selector: '.supplied',
        style: {
            'border-width': 3,
            'border-color': '#38bdf8'
        }
    },
    {
        // Where by-products go (ticket 024)
        selector: '.sink',
        style: {
            'shape': 'ellipse',
            'width': 120,
            'height': 120,
            'border-width': 3,
            'border-color': '#94a3b8'
        }
    },
    {
        // Fluids can't be sunk: the Sink only holds them as a placeholder
        selector: '.sink.invalid',
        style: {
            'border-width': 8,
            'border-color': '#ef4444'
        }
    },
    {
        selector: 'edge.byproduct',
        style: {
            'line-style': 'dotted',
            'line-color': '#64748b',
            'target-arrow-color': '#64748b'
        }
    },
    {
        // A by-product used as supply (ticket 031)
        selector: 'edge.byproduct.used',
        style: {
            'line-style': 'dashed',
            'line-color': '#38bdf8',
            'target-arrow-color': '#38bdf8',
            'color': '#7dd3fc'
        }
    },
    {
        // Using it would close a loop, so it goes to the Sink
        selector: 'edge.byproduct.loop',
        style: {
            'line-color': '#f4511e',
            'target-arrow-color': '#f4511e',
            'color': '#fdba74'
        }
    },
    {
        selector: 'edge.byproduct.invalid',
        style: {
            'line-color': '#ef4444',
            'target-arrow-color': '#ef4444',
            'color': '#fca5a5'
        }
    },
    {
        // All its buildings are built (ticket 037): faded, so what's left to build stands out
        selector: '.done',
        style: { 'opacity': 0.45 }
    },
    {
        // Logistics mode: a node's input (left) and output (right) logistics, with its number of
        // splitters and mergers (ticket 033)
        selector: '.lnode',
        style: {
            'shape': 'rectangle',
            'width': 22,
            'height': 50,
            'background-color': '#1e293b',
            'border-width': 2,
            'border-color': '#94a3b8',
            'color': '#e2e8f0',
            'font-size': '11px'
        }
    },
    {
        // An edge that needs more than one belt (or pipe) of the highest tier unlocked
        selector: 'edge.multi',
        style: { 'line-color': '#f59e0b', 'target-arrow-color': '#f59e0b', 'width': 4 }
    },
    {
        selector: '.lnode.edited',
        style: { 'border-style': 'dashed', 'border-color': '#38bdf8' }
    },
    {
        selector: '.lnode.warn',
        style: { 'border-width': 3, 'border-color': '#ef4444' }
    },
    {
        // Last, so it shows on overridden nodes too; the node keeps its item color
        selector: ':selected',
        style: {
            'border-width': 4,
            'border-color': '#f43f5e'
        }
    }
];
