import sys

from punnsilm import read_config

LAYOUT_HORIZONTAL, LAYOUT_VERTICAL = range(2)

# show names of subgroups and therir connections in the rx_grouper
DETAILED_SUBGROUPS = True
UNIQUE_EDGES_ONLY = True
LAYOUT = LAYOUT_HORIZONTAL

node_type_color_map = {
    'rx_grouper': 'blue',
    'syslog_input': 'green',
    'syslog_monitor': 'green',
    'console_output': 'red',
    'output_smtp': 'red',
    'log': 'red',
    'statsd': 'red',
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

seen_edges = set()

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
        label = "%(label)s";
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
        'label': "",
    }

    subgroup_names = []

    if node['type'] == 'rx_grouper':
        sub_regexps = 0
        for subgroup, subgroup_node in node['params']['groups'].items():
            subgroup_name = normalize_name(subgroup)
            subgroup_node['name'] = subgroup_name

            if DETAILED_SUBGROUPS:
                from_node = None
            else:
                from_node = node

            handle_node(subgroup_node, from_node)
            subgroup_names.append(subgroup_name)
            if 'rx_list' in subgroup_node:
                rx_list_len = len(subgroup_node['rx_list'])
                sub_regexps += rx_list_len
                rx_count += sub_regexps
        argd['label'] += '%d' % (sub_regexps,)
    else:
        handle_node(node)
    
    if len(subgroup_names) > 0:
        if DETAILED_SUBGROUPS:
            argd['node_string'] = ' '.join(subgroup_names)+";"
        else:
            # probably should append subgroup count somewhere
            pass

    return subgraph_string % argd

def handle_node(node, parent_node=None):
    """if parent node is specified then draw arrow from the parent instead of myself
    """
    if 'outputs' not in node:
        # probably an output node
        return

    if parent_node == None:
        from_node = node
    else:
        from_node = parent_node

    for output in node['outputs']:
        edge = (normalize_name(from_node['name']), output)
        if DETAILED_SUBGROUPS == False and edge in seen_edges:
            continue
        seen_edges.add(edge)
        outputs.append(edge)

def printer(node):
    if node['type'] == 'rx_grouper':
        print(handle_RXGrouper(node))
    else:
        print(handle_RXGrouper(node))

if len(sys.argv) < 2:
    print("give me name of the configuration file as an argument")
    sys.exit(-1)

nodelist = read_config(sys.argv[1])

if LAYOUT == LAYOUT_HORIZONTAL:
    layout_str = ' rankdir=LR '
else:
    layout_str = ''

graph_desc = """
digraph G {
    graph [fontsize=10 fontname="Verdana" compound=true %s];
    node [shape=record fontsize=10 fontname="Verdana"];

""" % (layout_str,)
print(graph_desc)
walk_graph(nodelist, printer)
for from_node, to_node in outputs:
    print("\t%s -> %s;" % (from_node, to_node))

print("""}""")

# print(rx_count)
