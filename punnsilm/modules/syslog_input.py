import copy
import time
import logging
import datetime

try:
    import socketserver
except ImportError:
    import SocketServer as socketserver

try:
    import regex as re
except ImportError:
    logging.warn("regex module not available. Performance will suffer.")
    import re

from punnsilm.core import Monitor, Message

SP = "\s"

RFC_3164_PRIORITY = '<(?P<priority>[0-9]{1,3})>'
RFC_3164_TIMESTAMP = '(?P<timestamp>[A-Z][a-z]{2}\s+[0-9]+\s[0-9]{2}:[0-9]{2}:[0-9]{2})'
RFC_3164_HOSTNAME = '(?P<hostname>[^\s]+)'
# XXX: hostname matching is far too wide, see http://www.ietf.org/rfc/rfc3164.txt
# for what is actually allowed. Implementing it 100% correctly would require a lot
# of work.

RFC_3164_TAG = '(?P<tag>[a-zA-Z0-9\-]{1,32})[^a-zA-Z0-9]'
RFC_3164_CONTENT = '\s+(?P<content>.*)'

RFC_3164_HEADER = RFC_3164_PRIORITY + RFC_3164_TIMESTAMP + SP + RFC_3164_HOSTNAME + SP
RFC_3164_MESSAGE = RFC_3164_TAG + RFC_3164_CONTENT

RFC_3164_MESSAGE = RFC_3164_HEADER + RFC_3164_MESSAGE
rfc_3164_message_rx = re.compile(RFC_3164_MESSAGE)

class RFC3164Parser(object):
    _MONTHMAP = {
        'Jan': 1,
        'Feb': 2,
        'Mar': 3,
        'Apr': 4,
        'May': 5,
        'Jun': 6,
        'Jul': 7,
        'Aug': 8,
        'Sep': 9,
        'Oct': 10,
        'Nov': 11,
        'Dec': 12,
    }

    @classmethod
    def parse_priority(cls, priority):
        # see http://www.ietf.org/rfc/rfc3164.txt 4.1.1 for the spec
        facility = priority // 8
        severity = priority - (facility * 8)
        return facility, severity

    @classmethod
    def date_parser(cls, raw_ts):
        # XXX: strptime() would be prettier but is too slow
        # besides the RFC explictly states that the month names will be english
        # abbreviations so there's no need for locale stuff anyway (which is what makes strptime() slow)
        month_abbrev, date, ts_part = raw_ts.split()
        hour, minute, second = ts_part.split(":")
        year = time.localtime().tm_year
        return datetime.datetime(year, cls._MONTHMAP[month_abbrev], int(date), int(hour), int(minute), int(second))

    @classmethod
    def parse(cls, line):
        match = re.match(rfc_3164_message_rx, line)
        if match:
            gd = match.groupdict()
            gd['timestamp'] = cls.date_parser(gd['timestamp'])
            facility, severity = cls.parse_priority(int(gd['priority']))
            gd['facility'] = facility
            gd['severity'] = severity
            return gd

        return None

class SyslogHandler(socketserver.StreamRequestHandler):
    def handle(self):
        while 1:
            msg = self.rfile.readline().strip()

            # XXX: do not compare against '' here
            # in py3 the msg is b''
            # Just using not here should work in both py2 and py3
            if not msg:
                return False

            try:
                self.monitor._on_new_message(msg)
            except Exception:
                logging.exception('failed to handle message!')

class SyslogMonitor(Monitor):
    _PARSERMAP = {
        'rfc3164': RFC3164Parser,
    }
    _MY_ARGS = (
        'network_protocol',
        'syslog_protocol',
        'address',
    )

    name = 'syslog_input'

    def __init__(self, *args, **kwargs):
        """
        known parameters:
          network_protocol: (tcp|udp)
          syslog_protocol: rfc3164
          address: (hostname|ip, port)
        """
        argd = copy.copy(kwargs)
        for arg in self._MY_ARGS:
            if arg in argd:
                del argd[arg]

        Monitor.__init__(self, *args, **argd)

        self._address = kwargs['address']
        syslog_protocol = kwargs['syslog_protocol']
        parser = self._PARSERMAP.get(syslog_protocol, None)
        if parser == None:
            raise Exception("syslog_protocol %s is unknown. Use one of %s" % (
                syslog_protocol, self._PARSERMAP.keys()))

        self._syslog_protocol = syslog_protocol
        self._parser = parser
        self._network_protocol = kwargs['network_protocol'].lower()

        if self._network_protocol not in ('tcp', 'udp'):
            raise Exception("unknown network protocol requested %s" % (
                self._network_protocol,))

        self._server = self._get_server(self._network_protocol)

    def _get_server(self, type):
        # XXX: setting class attribute to my object definitelly isn't nice
        # but alternatives that come to mind are all a bit too extravagant
        SyslogHandler.monitor = self

        if type == 'tcp':
            return socketserver.TCPServer(self._address, SyslogHandler)
        elif type == 'udp':
            return socketserver.UDPServer(self._address, SyslogHandler)
        return None

    def _run(self):
        self._server.serve_forever()

    def _on_new_message(self, message):
        """called when new syslog message is read from the network
        """
        message = message.decode('utf-8')
        msg_dict = self._parser.parse(message)
        if msg_dict is None:
            logging.debug('failed to parse:'+str(message))
            return

        msg_obj = Message(msg_dict['timestamp'], msg_dict['hostname'], msg_dict['content'])
        # FIXME: make tag & other stuff available too
        self.broadcast(msg_obj)

if __name__ == '__main__':
    TEST_MESSAGES = [
        """<22>Jan 23 13:38:33 mh-front01 dovecot: lmtp(55131): Disconnect from 127.0.0.1: Connection closed (in banner)""",
        """<22>Jan 23 13:38:33 mh-front01 dovecot] lmtp(55131): Disconnect from 127.0.0.1: Connection closed (in banner)""",
        """<34>Oct 11 22:14:15 mymachine su: 'su root' failed for lonvick on /dev/pts/8""",
        """<45>Jan 26 18:46:01 mh-front01 syslog-ng[1262]: Syslog connection broken; fd='24', server='AF_INET(127.0.0.1:5140)', time_reopen='60'""",
        """<38>Feb  1 23:13:51 mh-front01 sshd[52288]: Accepted keyboard-interactive/pam for hadara from 127.0.0.1 port 45795 ssh2""",
    ]
    for msg in TEST_MESSAGES:
        print(RFC3164Parser.parse(msg))

