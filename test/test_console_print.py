NODE_LIST = [
    {
        'name': 'syslog_source',
        'type': 'syslog_file_monitor',
        'outputs': [
            'filter',
        ],
        'params': {
            'filename': 'testlog1.log',
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
        },
        'outputs': [],
    },
]

