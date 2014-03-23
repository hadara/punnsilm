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
                    'outputs': ['output_named', 'output_anon'],
                },
            },
        },
    },
    {
        'name': 'output_named',
        'type': 'pipe_output',
        'params': {
            'append_newline': True,
            'bufsize': 1,
            'path': '/tmp/punnsilm.pipe',
        },
        'outputs': [],
    },
    {
        'name': 'output_anon',
        'type': 'pipe_output',
        'params': {
            'append_newline': True,
            'bufsize': 0,
            'command': 'tee /tmp/punnsilm.test',
        },
        'outputs': [],
    },
]

