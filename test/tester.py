import os
import sys
import time
import datetime

try:
    # py2
    import Queue as queue
except:
    # py3
    import queue

sys.path.append("..")

import unittest

from punnsilm import init_graph

# The following are mainly system tests.
# General strategy is to monkey patch the output nodes
# so that we can read the output as it is right before it's
# sent out from the program

EXPECTED_MSGS_TESTLOG1 = [
    {
        'host': 'publicapi2',
        'timestamp': datetime.datetime(2014, 12, 20, 13, 21, 9),
        'content': """nginx: 127.26.108.212 - 10.149.105.119 - - 20/Dec/2013:13:21:09 +0200 "GET /api/index/et/hint/active?type=useful,funny&include_related_data=none HTTP/1.1" 200 214 0.052 0.052 "http://static.example.com/html5/" "Mozilla/5.0 (Linux) AppleWebKit/534.51 (KHTML, like Gecko) Safari/534.51" .""",
    },
    {
        'host': 'publicapi1',
        'timestamp': datetime.datetime(2014, 12, 20, 13, 21, 9),
        'content': """nginx: 127.26.108.212 - 10.219.102.129 - - 20/Dec/2013:13:21:09 +0200 "GET /api/index/et/help HTTP/1.1" 200 787 0.022 0.022 "http://static.example.com/html5/" "Mozilla/5.0 (Linux) AppleWebKit/534.51 (KHTML, like Gecko) Safari/534.51" .""",
    },
    {
        'host': 'publicapi1',
        'timestamp': datetime.datetime(2014, 12, 20, 13, 21, 10),
        'content': """nginx: 127.26.108.212 - 10.219.102.129 - - 20/Dec/2013:13:21:09 +0200 "GET /api/index/et/help HTTP/1.1" 200 787 0.024 0.023 "http://static.example.com/html5/äöõüs" "Mozilla/5.0 (Linux) AppleWebKit/534.51 (KHTML, like Gecko) Safari/534.51" .""",
    },
]

class PunnsilmSystemTests(unittest.TestCase):
    def test_print(self):
        CONF = "test_console_print.py"
        self.maxDiff = 1000

        graph = init_graph(config=CONF, keep_state=False)
        writer_node = graph.nodemap['writer']
        q = queue.Queue()
        def my_reader(msg):
            q.put(msg)
        writer_node._printer = my_reader
        graph.start()

        for exp in EXPECTED_MSGS_TESTLOG1:
            msg = q.get(timeout=2)
            self.assertEqual(msg.host, exp['host'])
            self.assertEqual(msg.timestamp, exp['timestamp'])
            self.assertEqual(msg.content, exp['content'])

        graph.stop()

    def test_pipe(self):
        CONF = "test_pipe.py"
        NAMED_PIPE_FILE = "/tmp/punnsilm.pipe"
        PIPED_WRITE_FILE = "/tmp/punnsilm.test"

        EXPECTED_MSG = """h:publicapi2 ts:2014-12-20 13:21:09 content:nginx: 127.26.108.212 - 10.149.105.119 - - 20/Dec/2013:13:21:09 +0200 "GET /api/index/et/hint/active?type=useful,funny&include_related_data=none HTTP/1.1" 200 214 0.052 0.052 "http://static.example.com/html5/" "Mozilla/5.0 (Linux) AppleWebKit/534.51 (KHTML, like Gecko) Safari/534.51" .\nh:publicapi1 ts:2014-12-20 13:21:09 content:nginx: 127.26.108.212 - 10.219.102.129 - - 20/Dec/2013:13:21:09 +0200 "GET /api/index/et/help HTTP/1.1" 200 787 0.022 0.022 "http://static.example.com/html5/" "Mozilla/5.0 (Linux) AppleWebKit/534.51 (KHTML, like Gecko) Safari/534.51" .\nh:publicapi1 ts:2014-12-20 13:21:10 content:nginx: 127.26.108.212 - 10.219.102.129 - - 20/Dec/2013:13:21:09 +0200 "GET /api/index/et/help HTTP/1.1" 200 787 0.024 0.023 "http://static.example.com/html5/äöõüs" "Mozilla/5.0 (Linux) AppleWebKit/534.51 (KHTML, like Gecko) Safari/534.51" .\n"""

        self.maxDiff = None

        try:
            os.unlink(NAMED_PIPE_FILE)
        except (OSError, IOError) as e:
            pass

        try:
            os.unlink(PIPED_WRITE_FILE)
        except (OSError, IOError) as e:
            pass

        os.mkfifo(NAMED_PIPE_FILE)
        fd = os.open(NAMED_PIPE_FILE, os.O_RDONLY|os.O_NONBLOCK)
        graph = init_graph(config=CONF, keep_state=False)
        graph.start()
        time.sleep(2)
        val = os.read(fd, 1024).decode('utf-8')
        self.assertEqual(EXPECTED_MSG, val)
        graph.stop()

        with open(PIPED_WRITE_FILE, "r", encoding='utf-8') as fd:
            val = fd.read()
            self.assertEqual(EXPECTED_MSG, val)

        os.unlink(PIPED_WRITE_FILE)

    def test_statsd(self):
        CONF = "test_statsd.py"
        EXPECTED_COUNTERS = [
            'test.publicapi2.http.code.200',
            'test.publicapi1.http.code.200',
            'test.publicapi8.http.code.200',
            'test.publicapi1.http.code.200',
        ]

        EXPECTED_TIMERS = [
            (('test.publicapi2.group1', '200', 0.052), ('test.publicapi2.group1', '', 0.052),),
            (('test.publicapi1.group1', '200', 0.022), ('test.publicapi1.group1', '', 0.022),),
            (('test.publicapi8.group1', '200', 0.023), ('test.publicapi8.group1', '', 0.021),),
            (('test.publicapi1.group1', '200', 0.024), ('test.publicapi1.group1', '', 0.023),),
        ]

        graph = init_graph(config=CONF, keep_state=False)
        writer_node = graph.nodemap['statsd']

        counter_q = queue.Queue()
        def _counter(key):
            counter_q.put(key)

        timer_q = queue.Queue()
        def _timer(key, extrakey, value):
            timer_q.put((key, extrakey, value))

        writer_node.send_timer = _timer
        writer_node.send_counter = _counter

        graph.start()

        for exp in EXPECTED_COUNTERS:
            msg = counter_q.get()
            self.assertEqual(msg, exp)

        for exp in EXPECTED_TIMERS:
            msg1 = timer_q.get()
            msg2 = timer_q.get()
            self.assertIn(msg1, exp)
            self.assertIn(msg2, exp)

        graph.stop()

if __name__ == '__main__':
    unittest.main()
