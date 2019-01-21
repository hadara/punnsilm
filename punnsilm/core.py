import os
import sys
import json
import time
import logging
import datetime
import threading
import setproctitle
import multiprocessing

import os.path

from . import state_manager

import cProfile

class ImplementMe(Exception):
    pass

class StopMonitor(Exception):
    pass

class MsgJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.date):
            return obj.isoformat()

def broadcast_test_decorator(broadcast_func):
    """wrap broadcast function with some debug functionality 
    """
    def _broadcast_test_decorator(msg):
        if not hasattr(msg, 'depth'):
            setattr(msg, 'depth', 0)
        msg.depth += 1
        broadcast_func(msg)
        msg.depth -=1

    return _broadcast_test_decorator

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

    def dictify(self):
        retd = {}

        for key in ('timestamp', 'host', 'content'):
            retd[key] = getattr(self, key)
        if self.extradata is not None:
            retd['extradata'] = self.extradata

        return retd

    def __json__(self):
        return json.dumps(self.dictify(), cls=MsgJSONEncoder)

class PunnsilmNode(object):
    """baseclass for all the input, output and intermediate nodes
    """
    def __init__(self, name=None, outputs=None, test_mode=False):
        # this will hold just the names of the outputs
        self._configured_outputs = outputs
        # this will at some point hold actual output objects
        # once they are initialized
        self.outputs = []

        # are we running in the test mode
        self.test_mode = test_mode
        # this module is test mode aware and has necessary hooks in place
        # to avoid having undesired side effects while testing
        self.have_test_hooks = False

        self.name = name

        if test_mode:
            self.broadcast = broadcast_test_decorator(self.broadcast)

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
        """broadcast msg to output nodes
        """
        for o in self.outputs:
            o.append(msg)

class Monitor(PunnsilmNode):
    """baseclass for all the message monitors
    """
    def __init__(self, *args, **kwargs):
        PunnsilmNode.__init__(self, *args, **kwargs)
        self.msg_cls = None
        self.continue_from_last_known_position = True

        # what concurrency method to use, might be
        # overriden externally
        self.concurrency_cls = threading.Thread

        self._want_exit = False

    def stop(self):
        self._want_exit = True

    def run(self):
        self._worker = self.concurrency_cls(target=self._run)
        self._worker.daemon = True
        self._worker.start()
        return self._worker

    def _run(self):
        # pr = cProfile.Profile()
        # pr.enable()

        if self.concurrency_cls != threading.Thread:
            setproctitle.setproctitle('punnsilm: '+self.name)

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
                            #last_seen_msg_ts = self.get_state('last_msg_ts')

                            # FIXME: temporary hack until we get saving state working again
                            # when processes are used for concurrency
                            last_seen_msg_ts = datetime.datetime.now() - datetime.timedelta(seconds=60)

                            # we only have a 1s precision so it's rather probable that there might be
                            # several loglines from the same second than our last_seen_msg_ts of which
                            # we haven't seen some. By using > instead of >= we ensure that we at least see
                            # all the messages once, but some might be seen more than once. 
                            # Adding some seen_line_checksum is one way around this if it ever becomes a problem
                            if last_seen_msg_ts is not None and last_seen_msg_ts > msg.timestamp:
                                # initialize timestamp exists and we are currently seeing records
                                # that are older than this
                                initialized_ignored_lines += 1
                                continue
                            initialize_mode = False
                            logging.info("%s: initialize finished. Ignored %d lines" % (str(self), initialized_ignored_lines,))

                        self.broadcast(msg)
                        self.set_state('last_msg_ts', msg.timestamp)
                    if self._want_exit:
                        break
            except StopMonitor:
                logging.info('stop monitor exception seen in %s' % (str(self),))
                break
            except:
                logging.exception('unexpected failure in %s' % (str(self),))
        # pr.disable()
        # pr.dump_stats('rx.profile')

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

        stat_struct = os.fstat(self._fd.fileno())
        inode_nr = stat_struct.st_ino
        last_inode_nr = self.get_state('inode_nr')
        file_size = stat_struct.st_size
        last_saved_pos = self.get_state('file_pos')
        if last_inode_nr == inode_nr and last_saved_pos < file_size:
            self._fd.seek(last_saved_pos)
        self.set_state('inode_nr', inode_nr)
        self._save_file_state()

        return True

    def _save_file_state(self):
        fpos = self._fd.tell()
        self.set_state('file_pos', fpos)

    def read(self):
        self._maybe_reopen()

        WRITE_POSITION_EVERY_N_LINES = 100

        state_lines = 0
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

            state_lines += 1
            if state_lines >= WRITE_POSITION_EVERY_N_LINES:
                self._save_file_state()
                state_lines = 0

            if not isinstance(l, str):
                try:
                    l = l.decode('utf-8')
                except:
                    continue

            yield l

class Output(PunnsilmNode):
    pass
