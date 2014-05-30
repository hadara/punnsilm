import logging

import requests

from punnsilm import core

METHODMAP = {
    'GET': requests.get,
    'POST': requests.post,
}

class HTTPOutput(core.Output):
    """sends message out over HTTP
    """
    name = 'http_output'

    def __init__(self, **kwargs):
        core.Output.__init__(self, name=kwargs['name'])

        if 'uri' not in kwargs:
            raise Exception("mandatory option uri not specified for node %s" % (self.name,))
        self._uri = kwargs['uri']

        self._method = kwargs.get('method', 'POST')
        if self._method not in METHODMAP:
            raise Exception("unknown method %s configured for node %s" % (
                    str(self._method), self.name))

        self._basicauth = kwargs.get('basicauth', None)

        self._format = kwargs.get('format', 'formencode')
        if self._format not in ('formencode', 'json'):
            raise Exception("unknown format %s configured for node %s" % (
                    str(self._format), self.name))
        
    def append(self, msg):
        if self._format == 'formencode':
            data = msg.dictify()
        elif self._format == 'json':
            data = msg.__json__()

        response = METHODMAP[self._method](self._uri, data=data, auth=self._basicauth)
        logging.debug(response.text)
