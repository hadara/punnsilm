import sys
import logging

from punnsilm.core import Output

import logging
import logging.config
import logging.handlers

if sys.platform.startswith('linux'):
    SYSLOG_SOCKET = '/dev/log'
elif sys.platform.startswith('freebsd'):
    SYSLOG_SOCKET = "/var/run/log"

class LogOutput(Output):
    name = 'log'

    def __init__(self, **kwargs):
        Output.__init__(self, name=kwargs['name'])
        self._msg_format = kwargs.get('msg_format', '%(message)s')

        my_logger = logging.getLogger('output_'+kwargs['name'])
        my_logger.propagate = False
        my_logger.setLevel(logging.DEBUG)

        handler = logging.handlers.SysLogHandler(address = SYSLOG_SOCKET)
        formatter = logging.Formatter(self._msg_format)
        handler.setFormatter(formatter)

        my_logger.addHandler(handler)
        self._logger = my_logger

    def append(self, msg):
        self._logger.info(msg)
