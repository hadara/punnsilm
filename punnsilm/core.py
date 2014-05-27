import os
import sys
import time
import logging
import threading

import os.path

from . import state_manager

class ImplementMe(Exception):
    pass

class StopMonitor(Exception):
    pass

class Message(object):
    def __init__(self, timestamp, host, content, extra_params=None):
        self.timestamp = timestamp
        self.host = host
        self.content = content

        self.extradata = None
        self.comment = None

        if extra_params is not None:
            for k, v in extra_params.items():
                if not hasattr(self, k):
                    setattr(self, k, v)

    def __str__(self):
        retstr = "h:%s ts:%s content:%s" % (str(self.host), str(self.timestamp), self.content)
        if self.comment:
            retstr += '\n' + self.comment

        return retstr

class PunnsilmNode(object):
    """baseclass for all the input, output and intermediate nodes
    """
    def __init__(self, name=None, outputs=None):
        # this will hold just the names of the outputs
        self._configured_outputs = outputs
        # this will at some point hold actual output objects
        # once they are initialized
        self.outputs = []

        self.name = name
        self._read_state()

    def __str__(self):
        return "<%s - %s>" % (self.__class__.__name__, str(self.name))

    def _read_state(self):
        self._state = state_manager.state_read(self.name)
        logging.debug("%s state set to %s" % (str(self.name), str(self._state)))

    def set_state(self, key, state):
        self._state[key] = state

    def get_state(self, key=None):
        """returns either state for specific key or the whole current state
        """
        if key is not None:
            return self._state.get(key, None)

        return self._state

    def run(self):
        pass

    def stop(self):
        pass

    def connect_outputs(self, nodemap):
        if not self._configured_outputs:
            return None

        for output_name in self._configured_outputs:
            output = nodemap.get(output_name, None)
            if output is None:
                logging.error("failed to find output %s for node %s" % (output_name, self.name))
                # FIXME: should this be fatal?
                continue

            self.add_output(output)

    def add_output(self, output):
        self.outputs.append(output)

    def broadcast(self, msg):
        for o in self.outputs:
            o.append(msg)

class Monitor(PunnsilmNode):
    """baseclass for all the message monitors
    """
    def __init__(self, *args, **kwargs):
        PunnsilmNode.__init__(self, *args, **kwargs)
        self.msg_cls = None
        self.continue_from_last_known_position = True

        self._worker_thr = threading.Thread(target=self._run)
        self._worker_thr.daemon = True

        self._want_exit = False

    def stop(self):
        self._want_exit = True

    def run(self):
        self._worker_thr.start()

    def _run(self):
        initialize_mode = True

        if self.continue_from_last_known_position != True:
            initialize_mode = False

        initialized_ignored_lines = 0

        while 1:
            try:
                for l in self.read():
                    msg = self.parse_message(l)
                    # if parse_message() returns None then this 
                    # message was filtered out
                    if msg:
                        if initialize_mode is True:
                            # XXX: having the initialize conditional in the main
                            # loop isn't really optimal 
                            last_seen_msg_ts = self.get_state('last_msg_ts')
                            # we only have a 1s precision so it's rather probable that there might be
                            # several loglines from the same second than our last_seen_msg_ts of which
                            # we haven't seen some. By using > instead of >= we ensure that we at least see
                            # all the messages once, but some might be seen twise. Adding some seen_line_checksum
                            # is one way around this if it ever becomes a problem
                            if last_seen_msg_ts is not None and last_seen_msg_ts > msg.timestamp:
                                # initialize timestamp exists and we are currently seeing records
                                # that are older than this
                                initialized_ignored_lines += 1
                                continue
                            initialize_mode = False
                            logging.info("%s: initialize finished. Ignored %d lines" % (str(self), initialized_ignored_lines,))
                            #raise Exception(last_seen_msg_ts)

                        self.broadcast(msg)
                        self.set_state('last_msg_ts', msg.timestamp)
                    if self._want_exit:
                        break
            except StopMonitor:
                logging.info('stop monitor exception seen in %s' % (str(self),))
                break
            except:
                logging.exception('unexpected failure in %s' % (str(self),))

    def parse_message(self, l):
        if self.msg_cls != None:
            return self.msg_cls.from_raw_message(l)

        raise ImplementMe

class FileMonitor(Monitor):
    """monitors single logfile for changes"""

    def __init__(self, filename=None, stop_on_EOF=False, msg_cls=None, **kwargs):
        Monitor.__init__(self, **kwargs)

        if filename is None:
            raise Exception('filename has to be specified for FileMonitor')

        self.filename = filename
        self._stop_on_EOF = stop_on_EOF

        self._fd = None
        self._last_file_size = None

        if msg_cls != None:
            self.msg_cls = msg_cls

    def _list_holding_directory(self):
        dirname = os.path.dirname(self.filename)
        return os.listdir(dirname)

    def _maybe_reopen(self):
        """check if our monitored file needs to be reopened and do it if so
        Reopen is required usually because the file was rotated.
        """
        if self.filename == '-':
            # currently I don't know of any cases where reopening stdin would be needed
            self._fd = sys.stdin
            return 

        # this might actualy change the filename if there are format strings inside it
        filename = time.strftime(self.filename)

        try:
            cur_size = os.path.getsize(filename)

            if self._last_file_size != None and cur_size >= self._last_file_size:
                self._last_file_size = cur_size
                return False
        except OSError:
            # file was probably rotated from under us
            cur_size = None
        except IOError:
            # XXX: we seem to hit a rare NFS issue sometimes where get back no such file
            # or directory error when the file is rotated and the problem persists until
            # the next rotation. Getting directory listing from the parent folder seems
            # to fix it though... Probably the vnode goes out of sync in some way
            self._list_holding_directory()
            # just so that we wouldn't hammer the system if things still don't work out
            time.sleep(1)
            # fail now, caller will retry
            raise

        self._last_file_size = cur_size

        # probably file was rotated
        logging.info('reopening file %s' % (filename,))
        if self._fd:
            self._fd.close()

        try:
            self._fd = open(filename, "rb")
        except (OSError, IOError) as e:
            # throttle a bit
            time.sleep(1)
            raise

        return True

    def read(self):
        self._maybe_reopen()

        while 1:
            try:
                l = self._fd.readline()
            except IOError:
                logging.exception('closing file %s' % (str(self.filename),))
                self._fd.close()

            if not l:
                if self._stop_on_EOF:
                    logging.info('monitor %s stopped' % (self.name,))
                    raise StopMonitor("EOF seen on input")

                if not self._maybe_reopen():
                    # there was no need to reopen the file so there's nothing to do
                    # just sleep a bit to pass the time
                    logging.debug("no new data in %s last_size=%s" % (str(self), str(self._last_file_size)))
                    time.sleep(2)
                continue

            l = l.decode('utf-8')
            yield l

class Output(PunnsilmNode):
    pass
