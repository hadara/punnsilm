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
        self.assertEqual(parsed.host, expected['host'])
        self.assertEqual(parsed.timestamp, expected['ts'])
        self.assertEqual(parsed.content, expected['content'])

    def test_traditional(self):
        FILENAME = 'logsamples/rsyslog_traditional_fileformat.log'
        EXPECTED_RESULTS = (
            {
                'host': 'hadara-laptop2', 
                'ts': datetime.datetime(2014, 4, 11, 13, 35, 1), 
                'content': 'CRON[14695]: pam_unix(cron:session): session opened for user root by (uid=0)'
            },
            {
                'host': 'hadara-laptop2', 
                'ts': datetime.datetime(2014, 4, 11, 13, 36, 29), 
                'content': 'dhclient: DHCPDISCOVER on eth0 to 255.255.255.255 port 67 interval 13 (xid=0x3d55da5e)',
            },
            {
                'host': 'hadara-laptop2',
                'ts': datetime.datetime(2014, 4, 11, 13, 36, 40),
                'content': 'whoopsie[1474]: online',
            },
        )
        with open(FILENAME, 'r') as fd:
            for line, expected in zip(fd.readlines(), EXPECTED_RESULTS):
                parsed = RsyslogTraditionalFileFormatParser.parse(line)
                self._compare_results(parsed, expected)

    def test_fileformat(self):
        FILENAME = 'logsamples/rsyslog_fileformat.log'
        tz = FixedOffset(datetime.timedelta(hours=3), 'Fixed offset')
        EXPECTED_RESULTS = (
            {
                'host': 'debian7-tpl',
                'ts': datetime.datetime(2014, 4, 11, 13, 35, 35, 447571, tz),
                'content': 'kernel: imklog 5.8.11, log source = /proc/kmsg started.',
            },
            {
                'host': 'debian7-tpl',
                'ts': datetime.datetime(2014, 4, 11, 13, 35, 35, 447645, tz),
                'content': 'rsyslogd: [origin software="rsyslogd" swVersion="5.8.11" x-pid="3247" x-info="http://www.rsyslog.com"] start',
            },
            {
                'host': 'debian7-tpl',
                'ts': datetime.datetime(2014, 4, 11, 13, 43, 1, 929431, tz),
                'content': 'sshd[3289]: Accepted password for hadara from 192.168.57.1 port 51539 ssh2',
            },
            {
                'host': 'debian7-tpl',
                'ts': datetime.datetime(2014, 4, 11, 13, 43, 1, 929938, tz),
                'content': 'sshd[3289]: pam_unix(sshd:session): session opened for user hadara by (uid=0)',
            }
        )
        with open(FILENAME, 'r') as fd:
            for line, expected in zip(fd.readlines(), EXPECTED_RESULTS):
                parsed = RsyslogFileFormatParser.parse(line)
                self._compare_results(parsed, expected)

if __name__ == '__main__':
    unittest.main()
