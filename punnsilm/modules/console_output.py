from __future__ import print_function

import sys

from termcolor import cprint

from punnsilm import core

class ConsoleOutput(core.Output):
    """prints messages out to the console
    """
    name = 'console_output'

    _STREAMS = {
        'stdin': sys.stdin,
        'stdout': sys.stdout,
        'stderr': sys.stderr,
    }

    def __init__(self, **kwargs):
        core.Output.__init__(self, name=kwargs['name'])
        if 'stream' in kwargs:
            stream = self._STREAMS.get(kwargs['stream'], None)
            if stream == None:
                raise Exception("unknown stream %s requested. Pick one of %s" % (
                    ','.join(self._STREAMS.keys()))
                )
        else:
            stream = sys.stdout

        self._color = kwargs.get('color', None)
        self._highlight = kwargs.get('highlight', None)

        if self._color == None and self._highlight == None:
            self._printer = lambda x: print(x, file=stream)
        else:
            self._printer = lambda x: cprint(x, self._color, self._highlight, \
                file=stream)

    def append(self, msg):
        if msg.comment:
            self._printer("comment: %s" % (msg.comment,))
        if msg.extradata:
            self._printer("extradata: %s" % (msg.extradata,))

        self._printer(msg)
