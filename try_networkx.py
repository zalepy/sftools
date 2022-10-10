# https://github.com/boothby/networkx/blob/master/networkx/drawing/nx_pylab.py

import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

G = nx.Graph()

G.add_node(1)
G.add_nodes_from([2, 3])
G.add_nodes_from([
    (4, {"color": "red"}),
    (5, {"color": "green"}),
])

G.add_edges_from([(1, 2), (1, 3)])

# ------------------------------------
DG = nx.DiGraph()
DG.add_edge(2, 1)   # adds the nodes in order 2, 1
DG.add_edge(1, 3)
DG.add_edge(2, 4)
DG.add_edge(1, 2)

DG.add_weighted_edges_from([(1, 2, 0.5), (3, 1, 0.75)])
DG.out_degree(1, weight='weight')
DG.degree(1, weight='weight')
list(DG.successors(1))
list(DG.neighbors(1))

# ------------------------------------

G.add_edge(1, 2, weight=4.7)
G.add_edges_from([(3, 4), (4, 5)], color='red')
G.add_edges_from([(1, 2, {'color': 'blue'}), (2, 3, {'weight': 8})])
G[1][2]['weight'] = 4.7
G.edges[3, 4]['weight'] = 4.2

nx.draw_shell(G, with_labels=True, font_weight='bold')

f2 = plt.figure()
gg = nx.petersen_graph()
nx.draw_shell(G, nlist=[range(5, 10), range(5)], with_labels=True, font_weight='bold', width=3, node_size=500, node_shape='s')
# https://matplotlib.org/stable/gallery/lines_bars_and_markers/marker_reference.html

f3 = plt.figure()
gp = nx.petersen_graph()
positions = {}
labels = {}
arc = 2 * np.pi / len(gp.nodes)
radius = 0.8
for i, node in enumerate(gp.nodes):
    positions[node] = (radius * np.cos(i * arc), radius * np.sin(i * arc),)
    labels[node] = '({:6.2f}'.format(np.cos(i * arc)) + ', {:6.2f}'.format(np.sin(i * arc)) + ')'

edge_labels = {}
for i, edge in enumerate(gp.edges):
    # print(i, edge) # edge.data())
    edge_labels[edge] = str(edge)

# ax = plt.gca()
nx.draw(gp, pos=positions, with_labels=True, font_weight='bold', width=2, node_size=500)
label_pos = {n: (p[0], p[1] + 0.1) for n, p in positions.items()}
nx.draw_networkx_labels(gp, pos=label_pos, labels=labels)
nx.draw_networkx_edge_labels(gp, positions, edge_labels=edge_labels, font_color='r')

plt.savefig("path.png")
plt.show()
