from __future__ import unicode_literals
import os
import time
import shlex
import logging
import subprocess

from punnsilm import core

try:
    unicode
except NameError:
    # XXX: hack to get python3 + 2 support
    unicode = lambda x: str(x)

class NamedPipe:
    DEFAULT_BUFSIZE = -1

    def __init__(self, path, bufsize=None):
        if bufsize == None:
            self._bufsize = self.DEFAULT_BUFSIZE
        else:
            self._bufsize = bufsize

        self._path = path
        self._ensure_named_pipe_exists()

        self._pipe = None

    def _open_named_pipe(self):
        try:
            self._pipe = os.open(self._path, os.O_WRONLY|os.O_NONBLOCK)
        except OSError:
            logging.warn('nobody is listening on pipe %s' % (self._path,))
            return False
            
    def _ensure_named_pipe_exists(self):
        if not os.path.exists(self._path):
            os.mkfifo(self._path)

    def write(self, val):
        if not self._pipe:
            self._open_named_pipe()
        if not self._pipe:
            return False
        os.write(self._pipe, bytes(val, 'utf-8'))
        return True

class Pipeline:
    DEFAULT_BUFSIZE = -1

    def __init__(self, command, bufsize=None):
        if bufsize == None:
            self._bufsize = self.DEFAULT_BUFSIZE
        else:
            self._bufsize = bufsize

        self._cmd = command
        self._bufsize = bufsize
        self._create_subprocess()

    def _create_subprocess(self):
        args = shlex.split(self._cmd)
        self._process = subprocess.Popen(args, stdin=subprocess.PIPE, bufsize=self._bufsize)
        self._pipe = self._process.stdin

    def write(self, val):
        self._pipe.write(bytes(val, 'utf-8'))

class PipeOutput(core.Output):
    """writes messages to the Unix pipe
    """
    name = 'pipe_output'

    def __init__(self, **kwargs):
        core.Output.__init__(self, name=kwargs['name'])
        self._path = kwargs.get('path', None)
        self._cmd = kwargs.get('command', None)
        if self._path is None and self._cmd is None:
            msg = "you have to specify either path or command parameter to the pipe_output module"
            logging.error(msg)
            raise Exception(msg)

        self._bufsize = kwargs.get('bufsize', None)

        self._append_newline = kwargs.get('append_newline', False)

        if self._path:
            self._pipe = NamedPipe(self._path, self._bufsize)
        else:
            self._pipe = Pipeline(self._cmd, self._bufsize)

    def append(self, msg):
        val = unicode(msg)
        if self._append_newline:
            val += "\n"
        self._pipe.write(val)
