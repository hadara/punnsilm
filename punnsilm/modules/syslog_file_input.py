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

class RsyslogTraditionalFileFormatParser:
    RE_SYSLOG_MESSAGE = """^(?P<timestamp>[A-Z][a-z]{2}\s+[0-9]+\s[0-9]{2}:[0-9]{2}:[0-9]{2})\s([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\s)?(?P<host>[a-zA-Z0-9\-\_\.]+)\s(?P<content>.*)$"""
    rx_syslog_message = re.compile(RE_SYSLOG_MESSAGE)

    @classmethod
    def parse(cls, raw_msg):
        syslog_msg = cls.rx_syslog_message.match(raw_msg)

        if syslog_msg:
            md = syslog_msg.groupdict()
            try:
                ts = timestamp_parser_rfc3164(md['timestamp'])
            except AttributeError:
                logging.warn('http://bugs.python.org/issue7980 encountered')
                return None

            return Message(ts, md['host'], md['content'])

SYSLOG_FILE_PARSERS = {
    'rsyslog_traditional_file_format': RsyslogTraditionalFileFormatParser,
}

class SyslogFileMonitor(FileMonitor):
    DEFAULT_FILE_FORMAT = 'rsyslog_traditional_file_format'
    KNOWN_ARGS = set((
        'syslog_format',
    ))

    name = 'syslog_file_monitor'

    def __init__(self, **kwargs):
        local_args = {}
        for k,v in kwargs.items():
            if k in self.KNOWN_ARGS:
                local_args[k] = v
                del kwargs[k]

        FileMonitor.__init__(self, **kwargs)
        file_format = local_args.get('syslog_format', self.DEFAULT_FILE_FORMAT)
        parser = SYSLOG_FILE_PARSERS.get(file_format, None)

        if parser == None:
            logging.error('syslog file parser %s is unknown' % (file_format,))
            raise Exception

        self._parser = parser

    def parse_message(self, l):
        return self._parser.parse(l)
