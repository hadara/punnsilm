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

class GraphiteDashboardMonitor(core.Monitor):
    """monitors a Graphite dashboard
    Expects all the graphs to have timeseries called:
      value
      upper
      lower
    """
    name = 'graphite_input'

    def __init__(self, **kwargs):
        MY_ARGS = ['dashboard_uri', 'auth']
        for arg in MY_ARGS:
            setattr(self, arg, kwargs[arg])
            del kwargs[arg]

        self.monitored_graphs = []

        parse_res = urlparse(self.dashboard_uri)
        self.host = '%s://%s' % (parse_res.scheme, parse_res.netloc)

        super().__init__(**kwargs)
        self._parse_dashboard()

    def _parse_dashboard(self):
        res = requests.get(self.dashboard_uri, auth=self.auth)
        res = json.loads(res.text)
        graphs = res['state']['graphs']

        for graph in graphs:
            target_uri, parameter_dict, graph_uri = graph
            try:
                self._parse_dashboard_graph_def(target_uri, parameter_dict, graph_uri)
            except:
                logging.exception('failed to parse graph:'+str(graph_uri))

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
        print("URI IS:", uri)
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

        pprint.pprint(data)
        datad = {}
        for timeserie in data:
            print("timeseries:", timeserie)
            name = timeserie['target']
            name_prefix = name.split(" ", 1)[0]

            if name_prefix not in ('upper', 'lower', 'current'):
                logging.debug('ignoring timeserie %s on %s' % (name, graph['graph_uri']))
                continue

            last_datapoint = timeserie['datapoints'][-1]
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

        if current_value is None:
            logging.debug('current value is None. Ignoring it.')
            return None

        if 'upper' in datad:
            upper = datad['upper']
            upper_value, upper_value_ts = upper['datapoint']
            if current_value >= upper_value:
                self.send_alarm(current, upper, graph)
        elif 'lower' in datad:
            lower = datad['lower']
            lower_value, lower_value_ts = lower['datapoint']
            if current_value <= lower_value:
                self.send_alarm(current, lower, graph)

    def send_alarm(self, current, threshold, graph):
        msg = 'current_value: %s threshold: %s graph: %s' % (str(current), str(threshold), str(graph['graph_uri']))
        content = msg
        logging.debug(msg)
        # XXX: the assumption here is that the the timestamp of the current value is in local timezone
        # instead of the UTC. 
        timestamp = datetime.datetime.fromtimestamp(current['datapoint'][1])
        # XXX: what host should we use?
        host = 'graphite'
        print(graph['parameter_dict'])

        self.broadcast(core.Message(timestamp, host, content))

    def analyze_graphs(self):
        for graph in self.monitored_graphs:
            self.analyze_graph(graph)

    def read(self):
        self.analyze_graphs()
        time.sleep(1)
        return []
