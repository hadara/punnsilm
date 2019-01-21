import os
import imp
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

# module name -> object mappings for all the loaded modules
modulemap = {}

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
    for key in ('name', 'outputs', 'test_mode'):
        if key in node_conf:
            args[key] = node_conf[key]
        if 'params' in node_conf:
            args.update(node_conf['params'])

    logging.info("create node with params: %s" % (str(args),))
    node = node_class(**args)

    return node

def test_appender(node, real_appender):
    """basically a decorator for node.append() that prints out incoming messages for each node
    when in test mode.
    Attached to append() only in test mode so we won't pay performance penalty in the normal case
    """
    def _test_appender(msg):
        print(msg.depth*2*" "+'%s received: %s' % (node.name, str(msg)))
        if msg.extradata:
            print((msg.depth*2+1)*" "+"  extradata: %s" % (msg.extradata,))
        return real_appender(msg)
    return _test_appender

def create_nodes(nodelist, node_whitelist=None, test_mode=False, keep_state=True, concurrency='threads', connect_test_input=None):
    """creates all the nodes specified in the configuration given in the argument
    returns result as a dictionary containing node.name -> node mappings
    """
    nodemap = {}

    for node_conf in nodelist:
        if test_mode:
            node_conf['test_mode'] = True
        node = create_node(node_conf)

        if node is None:
            logging.error("failed to initialize node %s" % (node_conf,))
            # FIXME: should this be fatal?
            #   document it
            continue

        if connect_test_input and isinstance(node, core.Monitor):
            if node.name in connect_test_input:
                node.filename = '-'
                logging.info("reconnecting source node %s to stdin" % (node.name,))
            else:
                logging.warn("ignoring input node %s since it's not allowed by connect_test_input parameter" % (node.name,))
                continue

        if node_whitelist and node.name not in node_whitelist:
            logging.warn("ignoring node %s because it's not in the whitelist" % (node.name,))
            continue

        if test_mode:
            if isinstance(node, core.Output):
                if node.have_test_hooks:
                    logging.info("not replacing %s with ConsoleOutput since it's test mode aware" % (str(node.name),))
                else:
                    logging.info("replacing %s with ConsoleOutput because test mode is enabled" % (str(node.name),))
                    real_node_name = node.name
                    node = typemap['console_output'](name=real_node_name)

            node.test_mode = True
            if hasattr(node, 'append'):
                orig_append = node.append
                node.append = test_appender(node, orig_append)

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
            # XXX: optimize doesn't really have intended results at least under py 3.5
            # since our main interpreter is not called in the optimized mode.
            # See https://bugs.python.org/issue27169
            exec(compile(fd.read(), filename, 'exec', optimize=1), _globals, _locals)

def load_module(module, is_absolute=False):
    logging.info('loading module %s' % (module,))

    try:
        if is_absolute:
            mod = imp.load_source('module.name', module)
        else:
            mod = importlib.import_module(module)
    except:
        logging.exception('failed to load module %s' % (str(module),))
        return

    # register all the Punnsilm nodes found in the module in the global typemap
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
    global modulemap

    if moduledir[0] != "/":
        absolute_moduledir = os.path.join(os.path.dirname(__file__), moduledir)
    else:
        absolute_moduledir = moduledir

    files = os.listdir(absolute_moduledir)

    for filename in files:
        absolute_modulepath = os.path.join(absolute_moduledir, filename)
        if not os.path.isfile(absolute_modulepath):
            continue
        if not filename.endswith(".py"):
            continue
        if filename == '__init__.py':
            continue

        mod = None
        if moduledir[0] == '/':
            mod = load_module(os.path.join(moduledir, filename), is_absolute=True)
        else:
            mod = load_module('.'.join(('punnsilm', moduledir, filename[:-3])))
        modulemap[mod.__name__] = mod

    logging.info('module loading finished. Following modules are available: %s' % (
        str(','.join(typemap.keys()))
    ))

def construct_config_namespaces():
    """returns local namespace dictionary that should be made available to configuration
    nodes. This will contain functions that are explicitly imported by punnsilm modules
    """
    namespace = {}
    for module_name, module in modulemap.items():
        # FIXME: check for duplicates
        if hasattr(module, 'EXPORTABLE_CONFIG_FUNCS'):
            namespace.update(getattr(module, 'EXPORTABLE_CONFIG_FUNCS'))
    return namespace

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

    config_namespace = construct_config_namespaces()
    retd.update(config_namespace)

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
        # nodes to the NODE_LIST so it purely works on side effects and doesn't really
        # return anything.

        for dir_element in include_files:
            _execfile(dir_element, retd, config_namespace)

    globalsd = {
        'import_nodes': import_nodes,
    }

    _execfile(filename, globalsd, retd)

    return retd['NODE_LIST']
    
def init_graph(node_whitelist=None, test_mode=False, keep_state=True, config=None, concurrency=DEFAULT_CONCURRENCY_METHOD, extra_module_dirs=None, connect_test_input=None):
    """reads in configuration and initializes data structures
    """
    load_modules(DEFAULT_MODULEDIR)
    if extra_module_dirs is not None:
        for module_dir in extra_module_dirs:
            logging.info("loading extra module dir: %s" % (module_dir,))
            load_modules(module_dir)

    nodelist = read_config(config)
    nodemap = create_nodes(nodelist, node_whitelist=node_whitelist, test_mode=test_mode, keep_state=keep_state, concurrency=concurrency, connect_test_input=connect_test_input)
    return PunnsilmGraph(nodemap)
