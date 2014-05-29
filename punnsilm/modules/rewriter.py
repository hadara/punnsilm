try:
    import regex as re
except ImportError:
    logging.warn("regex module not available. Performance will suffer.")
    import re

from punnsilm import core

class Rewriter(core.PunnsilmNode):
    """replaces occurences of one string in the message attributes with another
    """
    name = 'rewriter'

    def __init__(self, **kwargs):
        core.PunnsilmNode.__init__(self, name=kwargs['name'], outputs=kwargs['outputs'])
        self._patterns = kwargs['patterns']

    def append(self, msg):
        for rule in self._patterns:
            key, pattern, replacement = rule
            if key.startswith("."):
                key = key[1:]
                if msg.extradata is not None and key in msg.extradata:
                    msg.extradata[key] = re.sub(pattern, replacement, msg.extradata[key])
            elif hasattr(msg, key):
                setattr(msg, key, re.sub(pattern, replacement, getattr(msg, key)))

        self.broadcast(msg)
