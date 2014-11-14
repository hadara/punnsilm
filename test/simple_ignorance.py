SSHD_TAG = "^sshd\[\d+\]: "

NODE_LIST = [
    {
        'name': 'syslog_source2',
        'type': 'syslog_file_monitor',
        'outputs': ['filter',],
        'params': {
            'filename': 'auth.log',
            'stop_on_EOF': True,
        }
    },
    {
        'name': 'syslog_source',
        'type': 'syslog_file_monitor',
        'outputs': ['filter',],
        'params': {
            'filename': 'auth2.log',
            'stop_on_EOF': True,
        }
    },
    {
        # ignore known good sshd messages
        'name': 'filter',
        'type': 'rx_grouper',
        'params': {
            'groups': {
                'ignore': {
                    'rx_list': [
                        SSHD_TAG + "Accepted password for",
                        SSHD_TAG + "pam_unix\(sshd:session\): session opened for",
                        SSHD_TAG + "Received disconnect from ",
                        SSHD_TAG + "pam_unix\(sshd:session\): session closed for user",
                        SSHD_TAG + "Connection closed by",
                    ],
                    'outputs': [],
                },
                '_fallthrough': {
                    'outputs': ['console'],
                },
            },
        },
    },
    {
        'name': 'console',
        'type': 'console_output',
        'outputs': [],
    },
]

