import sys

from punnsilm import read_config

node_type_color_map = {
    'rx_grouper': 'blue',
    'syslog_input': 'green',
    'syslog_monitor': 'green',
    'console': 'red',
    'output_smtp': 'red',
}

"""
digraph G {
    graph [fontsize=10 fontname="Verdana" compound=true];
    node [shape=record fontsize=10 fontname="Verdana"];

    subgraph cluster_syslog_source {
        color=green;
        node [style=filled, shape=box];
        label = "";
        syslog_source [shape=plaintext];
    }

    subgraph cluster_auth_filter {
        color=blue;
        node [style=filled, shape=box];
        label = "";
        auth_filter [shape=plaintext, style=solid];
        imap_login [shape=box];
    }

    subgraph cluster_sql_writer {
        color=red;
        node [style=filled, shape=box];
        label = "";
        sql_writer [shape=plaintext];
    }

    syslog_source -> auth_filter;
    imap_login -> sql_writer;
}
"""

rx_count = 0

# we will gather all the node connections into this
# list and append these to the end of the graph definition
outputs = []

def normalize_name(name):
    if name.startswith('"'):
        return name
    return '"%s"' % (name,)

def walk_graph(nodelist, cb):
    for element in nodelist:
        cb(element)

def handle_RXGrouper(node):
    global rx_count
    # FIXME:
    #  - color should depend on the cluster type
    #  - 
    subgraph_string = """
    subgraph cluster_%(name)s {
        color=%(color)s;
        node [style=filled];
        label = "";
        %(normalized_name)s [shape=plaintext, style=solid];
        %(node_string)s
    }
    """
    node_string = ''
    connections = []

    color = node_type_color_map.get(node['type'], 'green')

    argd = {
        'name': node['name'].replace("-", "_"),
        'normalized_name': normalize_name(node['name']),
        'node_string': '',
        'color': color,
    }

    subgroup_names = []

    if node['type'] == 'rx_grouper':
        for subgroup, subgroup_node in node['params']['groups'].items():
            subgroup_name = normalize_name(subgroup)
            subgroup_node['name'] = subgroup_name
            handle_node(subgroup_node)
            subgroup_names.append(subgroup_name)
            if 'rx_list' in subgroup_node:
                rx_count += len(subgroup_node['rx_list'])
    else:
        handle_node(node)
    
    if len(subgroup_names) > 0:
        argd['node_string'] = ' '.join(subgroup_names)+";"

    return subgraph_string % argd

def handle_node(node):
    if 'outputs' not in node:
        # probably an output node
        return

    for output in node['outputs']:
        outputs.append((normalize_name(node['name']), output))

def printer(node):
    if node['type'] == 'rx_grouper':
        print(handle_RXGrouper(node))
    else:
        print(handle_RXGrouper(node))

nodelist = read_config(sys.argv[1])
graph_desc = """
digraph G {
    graph [fontsize=10 fontname="Verdana" compound=true];
    node [shape=record fontsize=10 fontname="Verdana"];

"""
print(graph_desc)
walk_graph(nodelist, printer)
for from_node, to_node in outputs:
    print("\t%s -> %s;" % (from_node, to_node))

print("""}""")

# print(rx_count)
