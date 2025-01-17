import os
import copy
import json
import time
import logging

try:
    import regex as re
except ImportError:
    logging.warn("regex module not available. Performance will suffer.")
    import re
#import re

from punnsilm import core

STATS_ROOT = "/tmp/"
STATS_WRITE_EVERY_X_MSGS = 50000

# stop on first succesful match
MATCH_FIRST = 0
# attempt to match all the defined groups
MATCH_ALL = 1
KNOWN_MATCH_TYPES = {
    'first': MATCH_FIRST,
    'all': MATCH_ALL,
}
DEFAULT_MATCH_TYPE = 'all'
MEASURE_RX_PERF = False

if hasattr(time, "perf_counter"):
    pcounter = time.perf_counter
else:
    pcounter = time.clock

# regexp string id (memptr.) -> compiled rx. mappings
rx_cachemap = {}

# XXX: functions usable in the configuration
def match_field(msg, fieldname, rx):
    rx_c = rx_cachemap.get(rx)
    if rx_c is None:
        rx_c = re.compile(rx, re.UNICODE)
        rx_cachemap[rx] = rx_c

    if msg.extradata is None:
        return False
    # XXX: have to think about it a bit... is returning '' for missing
    # msg. attributes safe or should we communicate error back to upper
    # layers. We are obviously loosing information here
    match_obj = rx_c.match(msg.extradata.get(fieldname, ''))
    if match_obj is None:
        return False
    for k,v in match_obj.groupdict().items():
        msg.extradata[k] = v
    return True

def AND(_, *args):
    return all((x() if callable(x) else x for x in args))

def OR(_, *args):
    return any((x() if callable(x) else x for x in args))
# /XXX

def subgroup_broadcast_test_decorator(broadcast_func):
    """wrap broadcast function with some debug functionality 
    """
    def _broadcast_test_decorator(group, msg):
        if not hasattr(msg, 'depth'):
            setattr(msg, 'depth', 0)
        msg.depth += 1
        broadcast_func(group, msg)
        msg.depth -=1

    return _broadcast_test_decorator

class Group(object):
    def __init__(self, name, outputs):
        self.name = name
        self.outputs = outputs
        self.matches = 0

    def __str__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.name)

class RXGroup(Group):
    """handles single regexp group
    """
    # default field to match regexps against
    DEFAULT_FIELD = 'content'

    def __init__(self, name, outputs, rx_list=None, match_rule=None, disables_fallthrough=False, name_transform=None, test_mode=False):
        """
        @arg disables_fallthrough: if True then matching this group doesn't disable matching of the fallthrough
            group. This is useful when you just want to send some of the log lines to stats engine but this doesn't
            necessarily mean these arent anomalous. An example might be matching all the HTTP status codes in
            different groups while still wanting to see anomalous lines in the fallthrough group.
        """
        Group.__init__(self, name, outputs)
        self.disables_fallthrough = disables_fallthrough
        self.name_transform = name_transform
        self._perfd = {}

        if rx_list:
            self._init_rx_list(rx_list)
            self.match = self.match_rx_list
        elif match_rule:
            self._init_match_rule(match_rule)
            self._match_rule = match_rule
            self.match = self.match_rule
        else:
            self.match = None

        if test_mode and self.match:
            self.match = self.test_match_printer(self.match)

    def test_match_printer(self, matchfunc):
        def _test_match_printer(msg):
            res = matchfunc(msg)
            res_bool = bool(res)
            match_str = ''
            if res_bool:
                match_str = 'OK'
            else:
                match_str = 'NOK'
            print(msg.depth*2*" "+"rx_group '%s' -> %s" % (self.name, match_str))
            return res
        return _test_match_printer

    def get_performance_counters(self):
        return self._perfd

    def get_formated_name(self, group):
        """if name_transform is specified for this group then return name formated with matched RX groupdict
        otherwise just return the name
        """
        if self.name_transform is not None:
            return self.name_transform % group.groupdict()
        return self.name

    def _init_match_rule(self, match_rule):
        # FIXME: cache RX entries
        self._match_rule = match_rule

    def _init_rx_list(self, rx_list):
        self._rx_list = []

        if rx_list is None:
            # probably the _fallback node 
            return True

        # rx elements are either regexp strings, in which case we match it against the content field,
        # or tuple where the first element is fieldname and the second one holds regexp
        for rx in rx_list:
            if isinstance(rx, type('')):
                entry = (self.DEFAULT_FIELD, rx, re.compile(rx, re.UNICODE))
            else:
                fieldname, rx = rx
                entry = (fieldname, rx, re.compile(rx, re.UNICODE))

            self._rx_list.append(entry)
            self._perfd[rx] = {'evaluations': 0, 'matches': 0, 'total_time': 0}

    def match_rule(self, msg):
        def _rec_match_rule(msg, rule):
            if type(rule) != tuple:
                return rule
            return lambda: rule[0](msg, *(_rec_match_rule(msg, x) for x in (rule[1:])))

        return _rec_match_rule(msg, self._match_rule)()

    def match_rx_list(self, msg):
        """returns re match object if msg matches this group
        None otherwise
        """
        for fieldname, rx, rx_c in self._rx_list:
            if fieldname[0] == '.':
                # references extradata
                try:
                    fieldval = msg.extradata[fieldname[1:]]
                except KeyError:
                    logging.warn('grouper %s: key %s not found in %s' % 
                        (self.name, str(fieldname), str(msg.extradata)))
                    continue
                except TypeError:
                    if __debug__:
                        logging.debug("grouper %s: unable to match field %s against a message %s that doesn't have any parsed attributes" % (
                            self.name, str(fieldname), str(msg)))
                    continue
            else:
                fieldval = getattr(msg, fieldname)

            if MEASURE_RX_PERF is True:
                start_time = pcounter()
            match_obj = rx_c.match(fieldval)
            if MEASURE_RX_PERF is True:
                time_spent = pcounter() - start_time
                if time_spent > 1.0:
                    logging.warn('pathologically slow rx. %s in %s field:%s against %s took %.4fs' % (rx, self.name, str(fieldname), fieldval, time_spent))
                perf_rec = self._perfd[rx]
                perf_rec['evaluations'] += 1
                perf_rec['total_time'] += time_spent
            if match_obj:
                if MEASURE_RX_PERF is True:
                    perf_rec['matches'] += 1
                #if __debug__:
                #    logging.debug('%s matched rx %s with %s' % (
                #        str(self), str(rx), fieldval)
                #    )
                self.matches += 1
                return match_obj
            else:
                #if __debug__:
                #    logging.debug('%s no match: rx %s msg: %s' % (
                #        str(self), str(rx), fieldval)
                #    )
                pass

        return False

class RXGrouper(core.PunnsilmNode):
    name = 'rx_grouper'

    def __init__(self, *args, **kwargs):
        # XXX: remove attributes that the downstream doesn't expect
        groups = kwargs['groups']
        del kwargs['groups']

        match_type_name = kwargs.get('match', DEFAULT_MATCH_TYPE)
        self.match_strategy = KNOWN_MATCH_TYPES.get(match_type_name)
        if self.match_strategy is None:
            msg = 'match type %d is unknown' % (match_type_name,)
            logging.warn(msg)
            raise Exception(msg)
        if 'match' in kwargs:
            del kwargs['match']

        # is it OK to modify messages that go through us or should
        # make a copy that we modify and send downstream.
        # This might be useful in the cases when one wants to ensure
        # that upstream/parallel nodes that also get this message
        # won't see our modifications
        want_copy = kwargs.get('want_copy', False)

        # add list of all the unique outputs used by our subgroups so the
        # parent class would be able to initialize all the outputs correctly
        kwargs['outputs'] = self._gather_output_list_from_subgroups(groups)

        core.PunnsilmNode.__init__(self, *args, **kwargs)

        self.output_map = {}
        self._rx_list = []
        self._subgroups = {}
        self._matchable_subgroups = []
        self._init_subgroups(groups)

        # We want to show warning about missing output only once
        # and use this set to keep track of known misses.
        # Another possibility might be to use custome logging.Filter
        # that keeps track of what messages have been shown but it would
        # be slower
        self._missing_outputs = set()

        if want_copy:
            self._copier = copy.copy
        else:
            self._copier = lambda x: x

        self._stats_write_counter = 0

        if self.test_mode:
            self._subgroup_broadcast = subgroup_broadcast_test_decorator(self._subgroup_broadcast)

    def _gather_output_list_from_subgroups(self, groups):
        """create a list of unique output node names that are used in subgroups of this grouper
        """
        output_set = set()
        for subgroup in groups.values():
            if 'outputs' not in subgroup:
                logging.warn("""subgroup %s doesn't have any outputs""" % (str(subgroup),))
                continue

            output_set.update(subgroup['outputs'])

        return list(output_set)

    def _init_subgroups(self, groups):
        for group_name, group_config in groups.items():
            group = self._init_subgroup(group_name, group_config)
            if group.match is not None:
                self._matchable_subgroups.append(group)

    def _init_subgroup(self, group_name, group_config):
        # FIXME: maybe all the RX stuff should be implemented inside
        # the group
        try:
            if self.test_mode:
                group_config['test_mode'] = True
            group = RXGroup(group_name, **group_config)
        except:
            logging.error('error encountered while initializing subgroup "%s" conf: %s' % (group_name, str(group_config)))
            raise

        self._subgroups[group_name] = group
        return group

    def add_output(self, output):
        core.PunnsilmNode.add_output(self, output)
        self.output_map[output.name] = output
        if output.name in self._missing_outputs:
            self._missing_outputs.discard(output.name)

    def write_stats(self):
        stats = {}
        stats_file = os.path.join(STATS_ROOT, "punnsilm_stats_%s.json" % (self.name,))

        for name, group in self._subgroups.items():
            perf_counters = group.get_performance_counters()
            stats[name] = perf_counters

        with open(stats_file, "w+") as fd:
            fd.write(json.dumps(stats, sort_keys=True, indent=4))

    def append(self, msg):
        have_match = False

        for group in self._matchable_subgroups:
            match_group = group.match(msg)
            if match_group is not False:
                # Multiple groups might match the message and if we add some
                # extra attributes to it we might have to make a copy so downstream nodes
                # would see a consistent view even if the message is passed between the
                # threads and modified afterwards
                # It's usually not required though and is just NOOP
                msg_copy = self._copier(msg)
                msg_copy.group = group.get_formated_name(group)
                # XXX: if it's rx_list matcher the return value is match object itself
                if match_group is not True:
                    groupdict = match_group.groupdict()
                    if groupdict:
                        if msg_copy.extradata is None:
                            msg_copy.extradata = {}
                        msg_copy.extradata.update(groupdict)
                self._subgroup_broadcast(group, msg_copy)
                        
                have_match = True
                if self.match_strategy == MATCH_FIRST:
                    break

        if not have_match:
            fallthrough = self._subgroups.get('_fallthrough', None)
            if fallthrough:
                # FIXME: think about message copying and consistency
                # if we copy msg. for normal groups we probably should
                # do the same for fallthrough
                msg.group = fallthrough.name
                self._subgroup_broadcast(fallthrough, msg)

        self._stats_write_counter += 1
        if self._stats_write_counter > STATS_WRITE_EVERY_X_MSGS:
            self.write_stats()
            self._stats_write_counter = 0

    def _subgroup_broadcast(self, group, msg):
        for group_output in group.outputs:
            output_node = self.output_map.get(group_output, None)
            if output_node is None:
                if group_output not in self._missing_outputs:
                    logging.warn('unknown output %s specified for group %s' % (group_output, group.name))
                    self._missing_outputs.add(group_output)
                continue

            output_node.append(msg)


# HOOKS
EXPORTABLE_CONFIG_FUNCS = {
    'AND': AND,
    'OR': OR,
    'match_field': match_field,
}
