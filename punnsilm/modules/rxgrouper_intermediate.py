import copy
import logging

try:
    import regex as re
except ImportError:
    logging.warn("regex module not available. Performance will suffer.")
    import re

from punnsilm import core

class Group(object):
    def __init__(self, name, outputs):
        self.name = name
        self.outputs = outputs
        self.matches = 0

    def mark_matched(self, msg):
        self.matches += 1
        if __debug__:
            logging.debug("group match: %s total %d" % (self.name, self.matches))

    def __str__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.name)

class RXGroup(Group):
    """handles single regexp group
    """
    # default field to match regexps against
    DEFAULT_FIELD = 'content'

    def __init__(self, name, outputs, rx_list=None, disables_fallthrough=False, name_transform=None):
        """
        @arg disables_fallthrough: if True then matching this group doesn't disable matching of the fallthrough
            group. This is useful when you just want to send some of the log lines to stats engine but this doesn't
            necessarily mean these arent anomalous. An example might be matching all the HTTP status codes in
            different groups while still wanting to see anomalous lines in the fallthrough group.
        """
        Group.__init__(self, name, outputs)
        self.disables_fallthrough = disables_fallthrough
        self.name_transform = name_transform
        self._init_rx_list(rx_list)

    def get_formated_name(self, group):
        """if name_transform is specified for this group then return name formated with matched RX groupdict
        otherwise just return the name
        """
        if self.name_transform is not None:
            return self.name_transform % group.groupdict()
        return self.name

    def _init_rx_list(self, rx_list):
        self._rx_list = []

        if rx_list is None:
            # probably the _fallback node 
            return True

        # rx elements are either regexp strings in which case we match it against the content field
        # or tuple where the first element is fieldname and the second one holds regexp
        for rx in rx_list:
            if isinstance(rx, type('')):
                self._rx_list.append((self.DEFAULT_FIELD, rx, re.compile(rx)))
            else:
                fieldname, rx = rx
                self._rx_list.append((fieldname, rx, re.compile(rx)))

    def match(self, msg):
        """returns re match object if msg matches this group
        None otherwise
        """
        for fieldname, rx, rx_c in self._rx_list:
            fieldval = getattr(msg, fieldname)
            match_obj = rx_c.match(fieldval)
            if match_obj:
                if __debug__:
                    logging.debug('%s matched rx %s with %s' % (
                        str(self), str(rx), fieldval)
                    )
                self.mark_matched(msg)
                return match_obj
            else:
                if __debug__:
                    logging.debug('%s no match: rx %s msg: %s' % (
                        str(self), str(rx), fieldval)
                    )

        return None

class RXGrouper(core.PunnsilmNode):
    name = 'rx_grouper'

    def __init__(self, *args, **kwargs):
        # XXX: remove attributes that the downstream doesn't expect
        groups = kwargs['groups']
        del kwargs['groups']

        # add list of all the unique outputs used by our subgroups so the
        # parent class would be able to initialize all the outputs correctly
        kwargs['outputs'] = self._gather_output_list_from_subgroups(groups)

        core.PunnsilmNode.__init__(self, *args, **kwargs)

        self.output_map = {}
        self._rx_list = []
        self._subgroups = {}
        self._init_subgroups(groups)

        # We want to show warning about missing output only once
        # and use this set to keep track of known misses.
        # Another possibility might be to use custome logging.Filter
        # that keeps track of what messages have been shown but it would
        # be slower
        self._missing_outputs = set()

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
            self._init_subgroup(group_name, group_config)

    def _init_subgroup(self, group_name, group_config):
        # FIXME: maybe all the RX stuff should be implemented inside
        # the group
        try:
            group = RXGroup(group_name, **group_config)
        except:
            logging.error('error encountered while initializing subgroup "%s" conf: %s' % (group_name, str(group_config)))
            raise
        self._subgroups[group_name] = group

    def add_output(self, output):
        core.PunnsilmNode.add_output(self, output)
        self.output_map[output.name] = output
        if output.name in self._missing_outputs:
            self._missing_outputs.discard(output.name)

    def append(self, msg):
        have_match = False

        for group in self._subgroups.values():
            match_group = group.match(msg)
            if match_group is not None:
                # since multiple groups might match the message and if we add some
                # extra attributes to it we have to make a copy so downstream nodes
                # would see a consistent view even if the message is passed between the
                # threads and modified afterwards
                msg_copy = copy.copy(msg)
                msg_copy.group = group.get_formated_name(group)
                groupdict = match_group.groupdict()
                if groupdict:
                    if msg_copy.extradata is None:
                        msg_copy.extradata = {}
                    msg_copy.extradata.update(groupdict)
                self._subgroup_broadcast(group, msg_copy)
                        
                have_match = True
                if __debug__:
                    #print "match:",group,msg.content
                    pass
                # XXX: break or continue?

        if not have_match:
            # FIXME: maybe we should cache the falltrhough obj as attribute
            fallthrough = self._subgroups.get('_fallthrough', None)
            if fallthrough:
                # FIXME: think about message copying and consistency
                # if we copy msg. for normal groups we probably should
                # do the same for fallthrough
                msg.group = fallthrough.name
                self._subgroup_broadcast(fallthrough, msg)

    def _subgroup_broadcast(self, group, msg):
        for group_output in group.outputs:
            output_node = self.output_map.get(group_output, None)
            if output_node is None:
                if group_output not in self._missing_outputs:
                    logging.warn('unknown output %s specified for group %s' % (group_output, group.name))
                    self._missing_outputs.add(group_output)
                continue

            output_node.append(msg)
