from __future__ import with_statement

import os
import json
import logging
import datetime

# state_* functions provide simple means for saving information
# about node states that has to survive over executions.
# For example logfile source node might want to record timestamp of the last
# log line it has seen so that it wouldn't parse it again if the program is
# restarted.

STATE_FILE = "/tmp/punnsilm_state.json"

def ts_serializer(obj):
    """custom JSON serializer for datetime objects since JSON doesn't have
    any std. dt. format
    """
    if isinstance(obj, datetime.datetime):
        return obj.isoformat().rsplit(".")[0]
    raise TypeError(repr(obj) + " is not JSON serializable")

def state_writer(nodemap):
    """write node states out to stable storage
    """
    logging.info("writing out state information")
    # ensure that the state file exists and truncate it if so
    with open(STATE_FILE, "w+") as fd:
        pass

    state_dict = {}
    for key, node in nodemap.items():
        state_dict[key] = node.get_state()

    with open(STATE_FILE, 'w+') as fd:
        serialized_contents = json.dumps(state_dict, default=ts_serializer, indent=2)
        fd.write(serialized_contents)

    logging.info("state writter")

def _state_convert(input_dict):
    """recursively cast some contents of the input_dict into correct types
    """
    for key, value in input_dict.items():
        try:
            # python 2 & 3 compatibility
            is_string_value = isinstance(value, basestring)
        except NameError:
            is_string_value = isinstance(value, str)

        if isinstance(value, dict):
            input_dict[key] = _state_convert(value)
        elif is_string_value and key.endswith("_ts"):
            input_dict[key] = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")

    return input_dict

def state_read(node_name=None):
    """read the state file and return all of the contained data structs or just
    the struct for the node specified in the argument
    """
    state_map = {}
    if not os.path.exists(STATE_FILE):
        return state_map

    with open(STATE_FILE, 'r') as fd:
        state_file = fd.read()
        if state_file == '':
            return state_map
        state_map = json.loads(state_file)
        state_map = _state_convert(state_map)

    if node_name is None:
        return state_map

    return state_map.get(node_name, {})
