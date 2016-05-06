import logging
import datetime

import statsd

from punnsilm import core

class StatsdOutput(core.Output):
    """sends output to the Statsd daemon
    """
    name = 'statsd_output'

    def __init__(self, **kwargs):
        core.Output.__init__(self, name=kwargs['name'])
        self.host = kwargs.get('host', '127.0.0.1')
        self.port = kwargs.get('port', 8125)
        self.key_prefix = kwargs.get('key_prefix', '')
        # specifies what multiplier to use for timers to get
        # seconds. If incoming timer value already is in seconds then
        # None can be used.
        self.time_factor = kwargs.get('time_factor', None)
        if self.time_factor is not None:
            self.time_factor = float(self.time_factor)
        statsd.Connection.set_defaults(host=self.host, port=self.port)

    def append(self, msg):
        self.send_to_statsd(msg)

    def msg_too_old(self, msg):
        """check if the message is fresh enough to make sense for statsd
        Since we don't have timestamp in the statsd message then sending messages
        abount past events would falsify statistics.
        """
        if msg.timestamp < (datetime.datetime.now() - datetime.timedelta(minutes=1)):
            return True
        return False

    def send_counter(self, key):
        statsd_counter = statsd.Counter(key)
        statsd_counter += 1

    def send_timer(self, key, extraname, value):
        timer = statsd.Timer(key)
        if self.time_factor is not None:
            value *= self.time_factor
        timer.send(extraname, value)

    def send_to_statsd(self, msg):
        if self.msg_too_old(msg) == True:
            if __debug__:
                logging.debug("msg too old: %s" % (str(msg),))
            return None

        base_key = ''
        if self.key_prefix != '':
            base_key = self.key_prefix+'.'
        base_key += "%s" % (msg.host,)

        have_seen_name_group = False

        # extradata element names that start with _ have a special meaning for us.
        # Elements with the name in the form
        #  _some_key_name_time will be sent to statsd as a TIMER value
        #    with the name some.key.<value_of_file_field>
        #  _some_key_value will be sent to stats as a COUNTER with the name
        #    some.key.<value_of_the_corresponding_extradata_item>

        if msg.extradata is not None:
            del_keys = []

            for k,v in msg.extradata.items():
                if k[0] != '_':
                    continue

                try:
                    head, tail = k[1:].rsplit("_", 1)
                except ValueError:
                    continue

                key_prefix = head.replace("_", ".")

                if tail == "time":
                    key = base_key + ".%s" % (msg.group,)
                    key = key.lower()
                    extraname = ''
                    if head.startswith("ref"):
                        # we should use value of another regexp group as part
                        # of the key name
                        # for example _ref_request_count_value_time means that we should
                        # use value of the field _count_value as our key
                        lookup_key = head[len("ref"):]
                        if lookup_key in msg.extradata:
                            extraname = msg.extradata[lookup_key]
                        else:
                            logging.warning('group %s referenced from timer %s was not found' % (
                                lookup_key, k,))
                    self.send_timer(key, extraname, float(v))
                elif tail == "value":
                    key = '.'.join((base_key, key_prefix, v))
                    key = key.lower()
                    self.send_counter(key)
                    have_seen_name_group = True
                del_keys.append(k)

            for key in del_keys:
                # XXX: if message isn't copied between nodes multiple statsd outputs might see
                # the same message. To avoid double send under such a scenario we will delete
                # keys that we have "consumed"
                del msg.extradata[key]

        if not have_seen_name_group:
            key = base_key + ".%s" % (msg.group,)
            if __debug__:
                logging.debug("group send:",key)

            self.send_counter(key)
