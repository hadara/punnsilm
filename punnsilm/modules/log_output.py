import sys
import string

import logging
import logging.config
import logging.handlers

import collections

from punnsilm.core import Output

if sys.platform.startswith('linux'):
    SYSLOG_SOCKET = '/dev/log'
elif sys.platform.startswith('freebsd'):
    SYSLOG_SOCKET = "/var/run/log"

class ExtradataWrapper:
    """string formatter friendly wrapper around 
    the extradata object
    """
    DEFAULT_VALUE = ''

    def __init__(self, obj):
        self._obj = obj

    def __getitem__(self, key):
        if self._obj is None:
            return self.DEFAULT_VALUE
        return self._obj.get(key, self.DEFAULT_VALUE)

class MessageWrapper:
    """string formatter friendly wrapper around 
    the message object that returns empty string
    for non existent values instead of giving
    dying with an exception
    """
    _MAPPED_ATTRIBUTES = set(('timestamp', 'host', 'content'))

    def __init__(self, obj):
        self._obj = obj

    def _resolve_mapped_name(self, name):
        if name == 'extradata':
            return ExtradataWrapper(self._obj.extradata)
        if name in self._MAPPED_ATTRIBUTES:
            return getattr(self._obj, name)
        raise KeyError

    def __getitem__(self, name):
        return self._resolve_mapped_name(name)

    def __getattr__(self, name):
        try:
            return self._resolve_mapped_name(name)
        except KeyError:
            raise AttributeError

def default_formatter(msg):
    """do no formating, whatever the __str__ provides will do
    """
    return msg

def msg_formatter(fmt):
    """custom formatter
    """
    formatter = string.Formatter()
    def _msg_formatter(msg):
        return formatter.vformat(fmt, [], MessageWrapper(msg))
    return _msg_formatter

class LogOutput(Output):
    """logs message to syslog
    """
    name = 'log'

    def __init__(self, **kwargs):
        Output.__init__(self, name=kwargs['name'])
        self._msg_format = kwargs.get('msg_format', None)
        self._logger_format = kwargs.get('logger_format', '%(message)s')

        if self._msg_format is None:
            self._msg_formatter = default_formatter
        else:
            self._msg_formatter = msg_formatter(self._msg_format)

        my_logger = logging.getLogger('output_'+kwargs['name'])
        my_logger.propagate = False
        my_logger.setLevel(logging.DEBUG)

        handler = logging.handlers.SysLogHandler(address = SYSLOG_SOCKET)
        formatter = logging.Formatter(self._logger_format)
        handler.setFormatter(formatter)

        my_logger.addHandler(handler)
        self._logger = my_logger

    def append(self, msg):
        self._logger.info(self._msg_formatter(msg))
