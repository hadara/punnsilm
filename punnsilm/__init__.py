import os
import sys
import glob
import inspect
import logging
import importlib
import threading
import multiprocessing

import os.path

from .core import PunnsilmNode, Output

DEFAULT_CONFIG_FILE = "conf.py"
DEFAULT_MODULEDIR = "modules"

DEFAULT_CONCURRENCY_METHOD = "threads"

# holds name to node class mapping, filled dynamically on startup
typemap = {}

class PunnsilmGraph(object):
    def __init__(self, nodemap):
        self.nodemap = nodemap
        self.connect()

    def connect(self):
        for node_name, node in self.nodemap.items():
            node.connect_outputs(self.nodemap)

    def start(self):
        """start the activity of the graph.
        returns list of runnable objects
        """
        runnables = []
        for node_name, node in self.nodemap.items():
            runnable = node.run()
            if runnable:
                runnables.append(runnable)
        return runnables

    def stop(self):
        for node_name, node in self.nodemap.items():
            node.stop()

def create_node(node_conf):
    """node factory
    """
    node_name = node_conf.get('name', None)
    if node_name is None:
        logging.error("node name not specified for %s" % (node_conf,))
        return None

    node_type = node_conf.get('type', None)
    if node_type is None:
        logging.error("node type not specified for %s" % (node_name,))
        return None

    node_class = typemap.get(node_type, None)
    if node_class is None:
        logging.error("specified node type %s is unknown for node %s" % (node_type, node_name,))
        return None

    args = {}
    # copy relevant keys from the configuration to keyword args that will be fed to the
    # constructor
    for key in ('name', 'outputs'):
        if key in node_conf:
            args[key] = node_conf[key]
        if 'params' in node_conf:
            args.update(node_conf['params'])

    logging.info("create node with params: %s" % (str(args),))
    node = node_class(**args)

    return node

def create_nodes(nodelist, node_whitelist=None, test_mode=False, keep_state=True, concurrency='threads'):
    """creates all the nodes specified in the configuration given in the argument
    returns result as a dictionary containing node.name -> node mappings
    """
    nodemap = {}

    for node_conf in nodelist:
        node = create_node(node_conf)

        if node is None:
            logging.error("failed to initialize node %s" % (node_conf,))
            # FIXME: should this be fatal?
            #   document it
            continue

        if node_whitelist and node.name not in node_whitelist:
            logging.warn("ignoring node %s because it's not in the whitelist" % (node.name,))
            continue

        if test_mode and isinstance(node, core.Output):
            logging.info("replacing %s with ConsoleOutput because test mode is enabled" % (str(node.name),))
            real_node_name = node.name
            node = typemap['console_output'](name=real_node_name)

        if not keep_state and hasattr(node, "continue_from_last_known_position"):
            logging.info("overriding continue_from_last_known_position flag")
            node.continue_from_last_known_position = False

        if concurrency == 'threads':
            node.concurrency_cls = threading.Thread
        elif concurrency == 'processes':
            node.concurrency_cls = multiprocessing.Process

        nodemap[node.name] = node
            
    return nodemap

def _execfile(filename, _globals, _locals):
    """execfile wrapper that abstracts away differenced between python 2 & 3
    """
    try:
        execfile(filename, _globals, _locals)
    except NameError:
        # python3
        with open(filename, "rb") as fd:
            exec(compile(fd.read(), filename, 'exec'), _globals, _locals)

def load_module(module):
    logging.info('loading module %s' % (module,))

    try:
        mod = importlib.import_module(module)
    except:
        logging.exception('failed to load module %s' % (str(module),))

    for name, obj in inspect.getmembers(mod):
        if inspect.isclass(obj) and issubclass(obj, core.PunnsilmNode):
            if not hasattr(obj, "name"):
                logging.debug('name attribute of %s is not available. Not attempting to load' % (
                    str(obj),
                ))
                continue
            typemap[obj.name] = obj
            logging.info('registered %s as %s' % (str(obj), obj.name))
    
    return mod

def load_modules(moduledir):
    # FIXME: currently the argument is completely ignored.
    # We should allow to use it in order to override the module directory
    moduledir = DEFAULT_MODULEDIR
    absolute_moduledir = os.path.join(os.path.dirname(__file__), moduledir)
    files = os.listdir(absolute_moduledir)

    for filename in files:
        if not os.path.isfile(os.path.join(absolute_moduledir, filename)):
            continue
        if not filename.endswith(".py"):
            continue
        if filename == '__init__.py':
            continue

        load_module('.'.join(('punnsilm', moduledir, filename[:-3])))

    logging.info('module loading finished. Following modules are available: %s' % (
        str(','.join(typemap.keys()))
    ))

def read_config(filename=None):
    """reads in configuration file
    DEFAULT_CONFIG_FILE is assumed if filename is None
    """
    retd = {}

    if filename == None:
        filename = DEFAULT_CONFIG_FILE

    if not os.path.exists(filename):
        logging.error("configuration file %s does not exist!" % (filename,))
        sys.exit(-1)

    # we create a special import_nodes function that can be used
    # from the main configuration file to read in additional configuration
    # files (which can't use this function anymore)
    def import_nodes(relative_path):
        """helper function that can be used inside the config file to read node
        configs
        """
        include_files = glob.glob(relative_path)
        if len(include_files) == 0:
            logging.warn('no node definitions found for pattern %s' % (relative_path,))

        # child config will see parent config NS and will be able to add new
        # nodes to the NODE_LIST so it purely works on sidefects and doesn't really
        # return anything.

        for dir_element in include_files:
            _execfile(dir_element, retd, {})

    globalsd = {
        'import_nodes': import_nodes,
    }

    _execfile(filename, globalsd, retd)

    return retd['NODE_LIST']
    
def init_graph(node_whitelist=None, test_mode=False, keep_state=True, config=None, concurrency=DEFAULT_CONCURRENCY_METHOD):
    """reads in configuration and initializes data structures
    """
    load_modules(DEFAULT_MODULEDIR)

    nodelist = read_config(config)
    nodemap = create_nodes(nodelist, node_whitelist=node_whitelist, test_mode=test_mode, keep_state=keep_state, concurrency=concurrency)
    return PunnsilmGraph(nodemap)
