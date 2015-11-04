import time
import json
import pprint
import logging
import datetime

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

import requests

from punnsilm import core

DEFAULT_POLLING_INTERVAL_SEC = 60

class GraphiteDashboardMonitor(core.Monitor):
    """monitors a Graphite dashboard
    Expects all the graphs to have timeseries called:
      value
      upper
      lower
    """
    name = 'graphite_input'

    def __init__(self, **kwargs):
        MY_MANDATORY_ARGS = ['dashboard_uri',]
        for arg in MY_MANDATORY_ARGS:
            setattr(self, arg, kwargs[arg])
            del kwargs[arg]


        MY_OPTIONAL_ARGS = ['auth', 'polling_interval_sec']
        for arg in MY_OPTIONAL_ARGS:
            if arg in kwargs:
                setattr(self, arg, kwargs[arg])
                del kwargs[arg]
            else:
                setattr(self, arg, None)

        if self.polling_interval_sec is not None:
            self.polling_interval_sec = int(self.polling_interval_sec)
        else:
            self.polling_interval_sec = DEFAULT_POLLING_INTERVAL_SEC

        self.monitored_graphs = []

        parse_res = urlparse(self.dashboard_uri)
        self.host = '%s://%s' % (parse_res.scheme, parse_res.netloc)

        super().__init__(**kwargs)
        self._parse_dashboard()

    def _parse_dashboard(self):
        res = requests.get(self.dashboard_uri, auth=self.auth).json()
        graphs = res['state']['graphs']

        for graph in graphs:
            target_uri, parameter_dict, graph_uri = graph
            try:
                self._parse_dashboard_graph_def(target_uri, parameter_dict, graph_uri)
            except:
                logging.exception('failed to parse graph:'+str(graph_uri))
                continue

            graphd = {
                'target_uri': target_uri,
                'parameter_dict': parameter_dict,
                'graph_uri': graph_uri,
            }
            self.monitored_graphs.append(graphd)

            self._get_graph_data(graph_uri)

    def _parse_dashboard_graph_def(self, target_uri, parameter_dict, graph_uri):
        for target in parameter_dict['target']:
            # XXX: actual parser would be nice
            timeserie_name = target.split('"')[-2].strip()

    def _get_graph_data(self, uri):
        logging.debug("graph data URI is:", uri)
        uri = self.host + uri + '&format=json'
        res = requests.get(uri, auth=self.auth)
        if res.status_code != 200:
            logging.warn('got %s from %s content: %s' % (res.status_code, uri, res.text))
            return None

        res = json.loads(res.text)
        return res

    def analyze_graph(self, graph):
        data = self._get_graph_data(graph['graph_uri'])
        if data is None:
            return None

        datad = {}
        for timeserie in data:
            name = timeserie['target']
            name_prefix = name.split(" ", 1)[0]

            if name_prefix not in ('upper', 'lower', 'current'):
                logging.debug('ignoring timeserie %s on %s' % (name, graph['graph_uri']))
                continue

            # XXX: looking at second last instead of the last one because the last one
            # is often not yet complete and has value None
            if len(timeserie['datapoints']) > 1:
                idx = -2
            else:
                idx = -1
            last_datapoint = timeserie['datapoints'][idx]
            tmpd = {
                'name': name,
                'datapoint': last_datapoint,
            }
            datad[name_prefix] = tmpd

        if not 'current' in datad:
            logging.warn('current timeserie not found on %s' % (graph['graph_uri'],))
            return None

        current = datad['current']
        current_value, current_value_ts = current['datapoint']
        logging.debug("current value is:", current_value, current_value_ts)

        if current_value is None:
            logging.debug('current value is None. Ignoring it.')
            return None

        if 'upper' in datad:
            upper = datad['upper']
            upper_value, upper_value_ts = upper['datapoint']
            logging.debug("upper value:", upper_value, upper_value_ts)
            if current_value >= upper_value:
                logging.debug("UPPER IN ALARM")
                self.send_alarm("above", current, upper, graph)
        elif 'lower' in datad:
            lower = datad['lower']
            lower_value, lower_value_ts = lower['datapoint']
            logging.debug("lower value:", lower_value, lower_value_ts)
            if current_value <= lower_value:
                logging.debug("LOWER IN ALARM")
                self.send_alarm("below", current, lower, graph)

    def send_alarm(self, direction, current, threshold, graph):
        graph_title = graph['parameter_dict']['title']
        current_value = current['datapoint'][0]
        threshold_value = threshold['datapoint'][0]
        short_desc = '%s: value is %s threshold' % (
            graph_title, str(direction),
        )
        long_desc = '%s: value is %s threshold.\ncurrent_value: %s threshold: %s\n graph URI: %s' % (
            graph_title, str(direction), str(current_value), str(threshold_value), str(graph['graph_uri'])
        )
        content = short_desc

        logging.debug(long_desc)
        # XXX: the assumption here is that the the timestamp of the current value is in local timezone
        # instead of UTC
        timestamp = datetime.datetime.fromtimestamp(current['datapoint'][1])
        # XXX: what host should we use?
        host = 'graphite'
        logging.debug("PARAMS:", graph['parameter_dict'])

        msg_obj = core.Message(timestamp, host, content)
        msg_obj.extradata = {
            'full_uri': self.host+graph['graph_uri'],
            'long_desc': long_desc,
        }
        msg_obj.extradata.update(graph['parameter_dict'])
        self.broadcast(msg_obj)

    def analyze_graphs(self):
        for graph in self.monitored_graphs:
            self.analyze_graph(graph)

    def read(self):
        self.analyze_graphs()
        time.sleep(self.polling_interval_sec)
        return []
