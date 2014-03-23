from __future__ import unicode_literals

import time
import logging
import threading

import smtplib

from email.mime.text import MIMEText

from punnsilm import core

try:
    unicode
except NameError:
    # XXX: hack to get python3 + 2 support
    unicode = lambda x: str(x)

MAX_MESSAGES_TO_SEND = 200

DEFAULT_SMTP_SERVER = 'localhost'
# do not send out notifications more often than every X seconds
DEFAULT_SEND_INTERVAL = 60

DEFAULT_MAX_QUEUE_SIZE = MAX_MESSAGES_TO_SEND
SENDOUT_WORKER_INTERVAL_SEC = 30

class EmailOutput(core.Output):
    """class that sends out all the incoming messages by e-mail
    """
    name = 'smtp_output'

    def __init__(self, **kwargs):
        core.Output.__init__(self, name=kwargs['name'])
        for parameter in ('from_address', 'addresses'):
            if parameter not in kwargs:
                logging.error('missing mandatory parameter %s' % (parameter,))
                raise Exception

        self._from_address = kwargs.get('from_address', None)
        self._addresses = kwargs['addresses']
        self._send_interval = kwargs.get('send_interval', DEFAULT_SEND_INTERVAL)
        self._smtp_server = kwargs.get('smtp_server', DEFAULT_SMTP_SERVER)
        self._last_send_time_uts = None

        self._reset_mqueue()

    def run(self):
        core.Output.run(self)
        self._start_worker()

    def _start_worker(self):
        self._send_thr = threading.Thread(target=self._sendout_worker)
        self._send_thr.daemon = True
        self._send_thr.start()

    def _allowed_to_send_next_mail(self):
        if self._last_send_time_uts is None:
            return True

        if (self._last_send_time_uts + self._send_interval) < time.time():
            return True

        logging.info("[%s] sending e-mail isn't allowed yet" % (self.name,))

        return False

    def _sendout_worker(self):
        logging.info("mail worker thread for %s started!" % (self.name,))

        while 1:
            logging.info("[%s] email sender tick. queue len=%d interval=%d" % ( 
                self.name, len(self._mqueue), self._send_interval)
            )

            if len(self._mqueue) > 0 and self._allowed_to_send_next_mail():
                try:
                    self._send_mail()
                except:
                    logging.exception('%s failed to send mail' % (self.name,))

            time.sleep(SENDOUT_WORKER_INTERVAL_SEC)

    def _reset_mqueue(self):
        self._mqueue = []

    def _send_mail(self):
        self._last_send_time_uts = time.time()
        body = self._create_message_body()
        # FIXME: if we dropped messages because there were to many then we should log it
        # or the e-mail should say so at the very first line
        self._reset_mqueue()
        toaddrs = self._addresses

        # Create a text/plain message
        msg = MIMEText(body, 'plain', 'UTF-8')

        me = self._from_address
        you = ','.join(toaddrs)
        
        msg['Subject'] = '[punnsilm:%s] alert' % (self.name,)
        msg['From'] = me
        msg['To'] = you
        
        s = smtplib.SMTP(self._smtp_server)
        s.sendmail(me, toaddrs, msg.as_string())
        s.quit()

        logging.info("mail sent from %s to %s" % (self.name, you))

    def _create_message_body(self):
        msg = 'Following interesting log entries were seen (limit:%d qsize:%d):\n' % (
            MAX_MESSAGES_TO_SEND, len(self._mqueue)
        )
        return msg + '\n'.join(unicode(x) for x in self._mqueue[:MAX_MESSAGES_TO_SEND])

    def append(self, msg):
        if len(self._mqueue) > DEFAULT_MAX_QUEUE_SIZE:
            # XXX: in some cases it might be a good idea to log queue overflows
            # but we certainly shouldn't do that for every incoming message.
            return None
        self._mqueue.append(msg)
