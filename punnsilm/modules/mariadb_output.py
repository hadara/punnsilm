import time
import logging

import pymysql

from punnsilm import core

# run PING on the SQL connection before executing the query
# if more than this many seconds have passed from the last query
TRY_PING_AFTER_INACTIVITY_SECONDS = 60

class MariadbOutput(core.Output):
    """Allows you to execute MySQL/MariaDB queries with parameters from the log message.
    Useful for example for writing authentication events to SQL
    """
    name = 'mariadb_output'

    def __init__(self, **kwargs):
        core.Output.__init__(self, name=kwargs['name'])

        self._query = kwargs['query']
        self._arguments = kwargs['arguments']
        self._connection_params = kwargs['connection_parameters']

        self._sql_connection = None
        self._last_query_time = None

        # try to connect on startup so problems with config would be apparent sooner
        self._get_connection()

    def _get_connection(self):
        if self._sql_connection:
            if TRY_PING_AFTER_INACTIVITY_SECONDS and \
                (self._last_query_time + TRY_PING_AFTER_INACTIVITY_SECONDS) < time.time():
                self._sql_connection.ping()
            self._last_query_time = time.time()
            return self._sql_connection

        logging.info("creating new connection to the MariaDB")
        self._sql_connection = pymysql.connect(**self._connection_params)
        self._sql_connection.autocommit(True)
        self._last_query_time = time.time()

        return self._sql_connection
    
    def _execute_query(self, msg):
        con = self._get_connection()
        cur = con.cursor()

        parameters = []
        for arg in self._arguments:
            # XXX: there aren't any sanity checks here on purpose
            if arg[0] == '.':
                # references extradata
                value = msg.extradata[arg[1:]]
            else:
                value = getattr(msg, arg)

            parameters.append(value)

        logging.debug("%s %s" % (self._query, str(parameters)))

        try:
            cur.execute(self._query, parameters)
        except:
            # reset the connection just in case. It will be automatically
            # reconnected. We actually should only do it when the connection
            # is problematic but I don't know which exception types cover that
            # besides BrokenPipeError
            self._sql_connection = None
            logging.exception('query failed: %s %s' % (self._query, str(parameters)))

    def append(self, msg):
        self._execute_query(msg)
