from punnsilm.core import Monitor, FileMonitor, Message, SyslogMessage

class SyslogFileMonitor(FileMonitor):
    name = 'syslog_file_monitor'

    def parse_message(self, l):
        return SyslogMessage.from_raw_message(l)
