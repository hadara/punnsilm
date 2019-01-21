#Jan 21 19:06:28 <mail.info> xyz dovecot: imap-login: Login: user=<user3>, method=PLAIN, rip=10.1.2.3, lip=10.2.3.3, mpid=51689, TLS, session=<tyio4fp/vgBVHf60>
DOVECOT_IMAP_AUTH = '^dovecot(\[[0-9]+\])?: imap-login: Login: user=<(?P<username>\w+)>, method=(?P<authmethod>[^,]+), rip=(?P<remote_ip>[^,]+), lip=(?P<local_ip>[^,]+),.*'

NODE_LIST = [
    {
        'name': 'dovecot_source',
        'type': 'syslog_file_monitor',
        'outputs': [
            'imap_parser',
        ],
        'params': {
            'filename': 'logsamples/freebsd_dovecot_imap.log',
            'syslog_format': 'freebsd_syslog_format',
        }
    },
    {
        'name': 'imap_parser',
        'type': 'rx_grouper',
        'params': {
            'groups': {
                'parse': {
                    'rx_list': [
                        DOVECOT_IMAP_AUTH,
                    ],
                    'outputs': ['auth_writer',],
                },
            },
        },
    },
    {
        'name': 'auth_writer',
        'type': 'mariadb_output',
        'params': {
            'connection_parameters': {
                'db': 'testdb',
                'user': 'punnsilm',
                'passwd': 'notarealpassword',
                'host': 'sqlmaster.lan',
            },
            'query': """
                UPDATE user 
                SET last_auth=NOW() 
                WHERE username=%s
            """,
            'arguments': (
                '.username',
            ),
        }
    },
]
