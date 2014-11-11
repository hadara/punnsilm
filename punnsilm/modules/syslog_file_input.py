import time
import logging
import datetime

import iso8601

try:
    import regex as re
except ImportError:
    logging.warn("regex module not available. Performance will suffer.")
    import re

from punnsilm.core import Monitor, FileMonitor, Message

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

def timestamp_parser_rfc3164(raw_ts):
    # XXX: strptime() is too slow
    month_abbrev, date, ts_part = raw_ts.split()
    hour, minute, second = ts_part.split(":")
    year = time.localtime().tm_year
    return datetime.datetime(year, _MONTHMAP[month_abbrev], int(date), int(hour), int(minute), int(second))

def timestamp_parser_iso8601(raw_ts):
    return iso8601.parse_date(raw_ts)

def timestamp_parser_rfc3339(raw_ts):
    # XXX: rfc3339 is a subset of iso8601
    # and rfc5424 defines couple of further restrictions

    # FIXME: removing tz info until I can think of an efficient
    # method of using either tz aware objects or UTC throughout the system
    return iso8601.parse_date(raw_ts).replace(tzinfo=None)

def parse_priority(priority):
    priority = int(priority)
    # see http://www.ietf.org/rfc/rfc3164.txt 4.1.1 for the spec
    facility = priority // 8
    severity = priority - (facility * 8)
    return facility, severity

class RsyslogParser:
    MSG_CLS = Message

    @classmethod
    def parse(cls, raw_msg):
        syslog_msg = cls.rx_syslog_message.match(raw_msg)

        if syslog_msg:
            md = syslog_msg.groupdict()
            try:
                ts = cls.time_parser(md['timestamp'])
            except AttributeError:
                logging.warn('http://bugs.python.org/issue7980 encountered')
                return None

            return cls.MSG_CLS(ts, md['host'], md['content'], md)

class RsyslogTraditionalFileFormatParser(RsyslogParser):
    RE_SYSLOG_MESSAGE = """^(?P<timestamp>[A-Z][a-z]{2}\s+[0-9]+\s[0-9]{2}:[0-9]{2}:[0-9]{2})\s([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\s)?(?P<host>[a-zA-Z0-9\-\_\.]+)\s(?P<content>.*)$"""
    rx_syslog_message = re.compile(RE_SYSLOG_MESSAGE)
    time_parser = timestamp_parser_rfc3164

class RsyslogFileFormatParser(RsyslogParser):
    RE_SYSLOG_MESSAGE = """^(?P<timestamp>[^\s]+)\s(?P<host>[a-zA-Z0-9\-\_\.]+)\s(?P<content>.*)$"""
    rx_syslog_message = re.compile(RE_SYSLOG_MESSAGE)
    time_parser = timestamp_parser_iso8601

class RFC5424Message(Message):
    """adds some rfc5424 specific structure to the message
    """
    def __init__(self, *kwargs):
        Message.__init__(self, *kwargs)
        self.parse_priority(self.priority)
        self.parse_SD()

    def parse_SD(self):
        # XXX: implement me
        return
        
    def parse_priority(self, priority):
        self.facility, self.severity = parse_priority(self.priority)

class RsyslogProtocol23FormatParser(RsyslogParser):
    MSG_CLS = RFC5424Message
    # XXX: SD-ELEMENT parser isn't rfc5424 conformant
    RE_SYSLOG_MESSAGE = """^\<(?P<priority>\d{1,3})\>1 (?P<timestamp>[^\s]+)\s(?P<host>[^\s]+)\s(?P<appname>[^\s]+)\s(?P<procid>[^\s]+)\s(?P<msgid>[^\s]+)\s(?P<SD>\[[a-zA-Z0-9@]+( [a-zA-Z0-9]+\="[^"]+")*\])\s(?P<content>.*)$"""
    rx_syslog_message = re.compile(RE_SYSLOG_MESSAGE)
    time_parser = timestamp_parser_rfc3339

SYSLOG_FILE_PARSERS = {
    'rsyslog_traditional_file_format': RsyslogTraditionalFileFormatParser,
    'rsyslog_file_format': RsyslogFileFormatParser,
    'rsyslog_protocol23_format': RsyslogProtocol23FormatParser,
}

class SyslogFileMonitor(FileMonitor):
    DEFAULT_FILE_FORMAT = 'rsyslog_traditional_file_format'
    KNOWN_ARGS = set((
        'syslog_format',
    ))

    name = 'syslog_file_monitor'

    def __init__(self, **kwargs):
        local_args, parent_args = {}, {}
        for k,v in kwargs.items():
            if k in self.KNOWN_ARGS:
                local_args[k] = v
            else:
                parent_args[k] = v

        FileMonitor.__init__(self, **parent_args)
        file_format = local_args.get('syslog_format', self.DEFAULT_FILE_FORMAT)
        parser = SYSLOG_FILE_PARSERS.get(file_format, None)

        if parser == None:
            logging.error('syslog file parser %s is unknown' % (file_format,))
            raise Exception

        self._parser = parser

    def parse_message(self, l):
        return self._parser.parse(l)
