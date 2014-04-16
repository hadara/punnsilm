import datetime
import unittest

from punnsilm.modules.syslog_file_input import RsyslogTraditionalFileFormatParser, RsyslogFileFormatParser, RsyslogProtocol23FormatParser

class FixedOffset(datetime.tzinfo):
    """Fixed offset in minutes east from UTC."""

    def __init__(self, delta, name):
        self.__offset = delta
        self.__name = name

    def utcoffset(self, dt):
        return self.__offset

    def tzname(self, dt):
        return self.__name

    def dst(self, dt):
        return ZERO

class ParserTests(unittest.TestCase):
    def _compare_results(self, parsed, expected):
        for key, value in expected.items():
            self.assertEqual(getattr(parsed, key), value)

    def _test_parser(self, cls, filename, expected_results):
        with open(filename, 'r') as fd:
            for line, expected in zip(fd.readlines(), expected_results):
                parsed = cls.parse(line)
                self._compare_results(parsed, expected)

    def test_traditional(self):
        FILENAME = 'logsamples/rsyslog_traditional_fileformat.log'
        EXPECTED_RESULTS = (
            {
                'host': 'hadara-laptop2', 
                'timestamp': datetime.datetime(2014, 4, 11, 13, 35, 1), 
                'content': 'CRON[14695]: pam_unix(cron:session): session opened for user root by (uid=0)'
            },
            {
                'host': 'hadara-laptop2', 
                'timestamp': datetime.datetime(2014, 4, 11, 13, 36, 29), 
                'content': 'dhclient: DHCPDISCOVER on eth0 to 255.255.255.255 port 67 interval 13 (xid=0x3d55da5e)',
            },
            {
                'host': 'hadara-laptop2',
                'timestamp': datetime.datetime(2014, 4, 11, 13, 36, 40),
                'content': 'whoopsie[1474]: online',
            },
        )
        self._test_parser(RsyslogTraditionalFileFormatParser, FILENAME, EXPECTED_RESULTS)

    def test_fileformat(self):
        FILENAME = 'logsamples/rsyslog_fileformat.log'
        tz = FixedOffset(datetime.timedelta(hours=3), 'Fixed offset')
        EXPECTED_RESULTS = (
            {
                'host': 'debian7-tpl',
                'timestamp': datetime.datetime(2014, 4, 11, 13, 35, 35, 447571, tz),
                'content': 'kernel: imklog 5.8.11, log source = /proc/kmsg started.',
            },
            {
                'host': 'debian7-tpl',
                'timestamp': datetime.datetime(2014, 4, 11, 13, 35, 35, 447645, tz),
                'content': 'rsyslogd: [origin software="rsyslogd" swVersion="5.8.11" x-pid="3247" x-info="http://www.rsyslog.com"] start',
            },
            {
                'host': 'debian7-tpl',
                'timestamp': datetime.datetime(2014, 4, 11, 13, 43, 1, 929431, tz),
                'content': 'sshd[3289]: Accepted password for hadara from 192.168.57.1 port 51539 ssh2',
            },
            {
                'host': 'debian7-tpl',
                'timestamp': datetime.datetime(2014, 4, 11, 13, 43, 1, 929938, tz),
                'content': 'sshd[3289]: pam_unix(sshd:session): session opened for user hadara by (uid=0)',
            },
        )
        self._test_parser(RsyslogFileFormatParser, FILENAME, EXPECTED_RESULTS)

    def test_protocol23(self):
        FILENAME = 'logsamples/rsyslog_protocol23_format.log'
        tz = FixedOffset(datetime.timedelta(hours=3), 'Fixed offset')
        EXPECTED_RESULTS = (
            {
                'host': 'XYZ-devel',
                'timestamp': datetime.datetime(2014, 4, 16, 15, 35, 16, 784000), #, tz),
                'content': '/static/js/app.js in (8ms)',
                'msgid': 'perf',
                'SD': '[mdc@18060 customer="31504044442" ip="127.0.0.1" requestId="XYZ-devel-363" selectedRepresentee="31504044442" sessionId="rgepixbouem6clvwl7g8lzur" xyzContextId="1a2b3c"]',
            },
        )
        self._test_parser(RsyslogProtocol23FormatParser, FILENAME, EXPECTED_RESULTS)

if __name__ == '__main__':
    unittest.main()
