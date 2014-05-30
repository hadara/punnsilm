try:
    import regex as re
except ImportError:
    logging.warn("regex module not available. Performance will suffer.")
    import re

from punnsilm import core

DEFAULT_OPTIONS = {
    'type':  'replace',
}

def regexp_replacer(pattern, replacement, value):
    return re.sub(pattern, replacement, value)

def replace_replacer(pattern, replacement, value):
    return value.replace(pattern, replacement)

class Rewriter(core.PunnsilmNode):
    """replaces occurences of one string in the message attributes with another
    """
    name = 'rewriter'

    def __init__(self, **kwargs):
        core.PunnsilmNode.__init__(self, name=kwargs['name'], outputs=kwargs['outputs'])
        self._rules = self._parse_rules(kwargs['rules'])

    def _parse_rules(self, rules):
        """validates ruleset configuration and build up internal representation of it
        """
        retl = []

        for rule in rules:
            if len(rule) == 3:
                key, pattern, replacement = rule
                options = DEFAULT_OPTIONS
            elif len(rule) == 4:
                key, pattern, replacement, options = rule
            else:
                raise Exception("rule has too many elements:"+str(rule))

            if not 'type' in options:
                raise Exception("rule type not specified in options for rewrite rule %s" % (str(rule),))

            if options['type'] not in ('replace', 'regexp'):
                raise Exception("unknown rewrite rule type %s seen in configuration" % (str(options['type']),))

            if options['type'] == 'regexp':
                pattern = re.compile(pattern)
                func = regexp_replacer
            elif options['type'] == 'replace':
                func = replace_replacer

            retl.append((key, pattern, replacement, options, func))

        return retl
            
    def append(self, msg):
        for rule in self._rules:
            key, pattern, replacement, options, func = rule
            if key.startswith("."):
                key = key[1:]
                if msg.extradata is not None and key in msg.extradata:
                    msg.extradata[key] = func(pattern, replacement, msg.extradata[key])
            elif hasattr(msg, key):
                setattr(msg, key, func(pattern, replacement, getattr(msg, key)))

        self.broadcast(msg)
