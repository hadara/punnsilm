# Dec 20 13:21:09 publicapi2 nginx: 127.26.108.212 - 10.149.105.119 - - 20/Dec/2013:13:21:09 +0200 "GET /api/index/et/hint/active?type=useful,funny&include_related_data=none HTTP/1.1" 200 214 0.052 0.052 "http://static.example.com/html5/" "Mozilla/5.0 (Linux) AppleWebKit/534.51 (KHTML, like Gecko) Safari/534.51" .

NODE_LIST = [
    {
        'name': 'syslog_source',
        'type': 'syslog_file_monitor',
        'outputs': [
            'filter', 'email',
        ],
        'params': {
            'filename': 'test/testlog1.log',
        }
    },
    {
        'name': 'filter',
        'type': 'rx_grouper',
        'params': {
            'groups': {
                'imap_auth': {
                    'rx_list': [
                        ".*hint.*",
                        ("host", "publicapi1"),
                    ],
                    'outputs': ['writer',],
                },
            },
        },
    },
    {
        'name': 'writer',
        'type': 'console_output',
        'params': {
            'color': 'red',
            'highlight': 'on_blue',
        },
        'outputs': [],
    },
    {
        'name': 'email',
        'type': 'smtp_output',
        'params': {
            'smtp_server': 'localhost',
            'from_address': 'hadara@bsd.ee',
            'send_interval': 30,
            'addresses': [
                'hadara@bsd.ee',
            ],
        },
        'outputs': [],
    },
]

