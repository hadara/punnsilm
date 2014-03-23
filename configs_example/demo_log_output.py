NODE_LIST.append(
{
    'name': 'log',
    'type': 'log',
    'params': {
        # see 15.7.6 @ 
        # http://docs.python.org/2/library/logging.html#formatter-objects
        # for supported syntax in the msg_format string
        'msg_format': 'punnsilm: %(message)s',
    }
},
)

