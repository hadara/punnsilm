# obviously misses some legal IPs and matches some non-legal but is good enough for our specific case
IPV4 = """[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+"""
NGINX_TIMESTAMP = """(?P<nginx_timestamp>[0-9]+/[A-Z][a-z]{2}/[0-9]+:[0-9]+:[0-9]+:[0-9]+ \+[0-9]+)"""
REQ = """(?P<http_method>[A-Z]+) (?P<request_uri>[^ ]+) (?P<protocol>[A-Z]+)/(?P<http_version>1.[0-9]+)"""
STATUS_CODE = "(?P<_http_code_value>[0-9]+)"
BYTES_RETURNED = "(?P<bytes_returned>[0-9]+)"
TOTAL_TIME = "(?P<_ref_http_code_value_time>[0-9]\.[0-9]+)"
BACKEND_TIME = "(?P<_backend_time>[0-9]\.[0-9]+)"
REFERER = "(?P<referer>[^ ]+)"
USER_AGENT = '(?P<user_agent>[^"]+)'
NGINX_RX = 'nginx: '+IPV4+' - '+IPV4+' - - '+NGINX_TIMESTAMP+' "'+REQ+'" '+STATUS_CODE+' '+BYTES_RETURNED+' '+TOTAL_TIME+' '+BACKEND_TIME+' "'+REFERER+'" "'+USER_AGENT+'" .'

NODE_LIST = [
    {
        'name': 'syslog_source',
        'type': 'syslog_file_monitor',
        'outputs': [
            'nginx_parser',
        ],
        'params': {
            'filename': 'testlog1.log',
        }
    },
    {
        'name': 'nginx_parser',
        'type': 'rx_grouper',
        'params': {
            'groups': {
                'group1': {
                    'rx_list': [
                        NGINX_RX,
                    ],
                    'outputs': ['http',],
                },
            },
        },
    },
    {
        'name': 'http',
        'type': 'http_output',
        'params': {
            'uri': 'http://httpbin.org/post',
            'basicauth': ('someuser', 'somepassword'),
            'format': 'json',
        },
    },
]

