# About
Punnsilm is a tool for analyzing, monitoring, transforming and sending logs.

# Install
Punnsilm is developed on Python 3.3. In general I try to keep it Python 2.7 compatible
but I only bring py2 support up-to-date every once in a while.

    sudo apt-get install python-regex
    cd /srv/data
    virtualenv --system-site-packages punnsilm-venv
    hg clone http://bitbucket.org/hadara/punnsilm
    source punnsilm-venv/bin/activate
    cd punnsilm
    python setup.py install

# Configuration
By default punnsilm expects to find a configuration in the file called conf.py 
which should be located in the same directory as the application itself.
You can specify other configuration files with the --config option

Main configuration file can in turn include other configuration files.

There are several configuration examples available under the test directory

NB. when configuring statsd host use IP instead of the name or place the 
name into /etc/hosts file.
Otherwise the OS will use your nameserver to resolve the hostname
for each and every packet which can easily generate thousands
of unnecessary DNS lookups per second. 
Another workaround method is to run a local caching DNS proxy (i.e. Unbound).

# Running
You can run it with:
    /srv/data/punnsilm-venv/bin/python /srv/data/punnsilm/punnsilm.py

to run it on startup add the following to the crontab of the user that should run it:
    @reboot cd /srv/data/punnsilm/ && /srv/data/punnsilm-venv/bin/python /srv/data/punnsilm/punnsilm.py 1> /dev/null 2> /dev/null &

There is actually a --daemon option that should do it in a much more Unixy way but it doesn't yet
quite work as expected.

# Available nodes
All the nodes have following mandatory attributes:
 - *name*: name used in configuration to reference this node
 - *type*: type of the node

All the nodes can have attribute outputs which is a list containing node names where the output from this node should be sent.
For output nodes this attribute doesn't have any meaning since their output is a sideffect (printing to console, sending e-mail, 
writing to socket etc.)

## Input
Input nodes read input from some external source and forward it to one or more output nodes. Usually a bit of normalization
is already performed inside the input node so that the basic message structure is already present for the downstream nodes.

Currently the following input nodes are available:

### file_monitor
Basic node that reads input from a file (or file like object like a pipe).
Doesn't assume any structure from the input. This node is mainly useful as a baseclass for defining your own file monitors that
implement normalization that is specific to your file format.

It takes care of the following things for you:
 - *rotation*: if the file size decreases then it's assumed that it was rotated and we will reopen it
 - *dynamic filenames*: it can handle filenames like log_2014.01.02.log

Following configuration options are available for this node:
 - *stop_on_EOF*: instead of looping at the end of the input and waiting for additional content just stop the chain.
 - *filename*: filename to open. It can contain any of the time formating directives supported by strftime() [1]

1 - http://docs.python.org/3/library/time.html#time.strftime

### syslog_file_monitor
Extends basic file monitor with syslog specific parser.

Currently only RFC3164 is supported.

### syslog_input 
This input node binds to TCP/UDP port and is able to handle Syslog protocol. 

Currently only RFC3164 is supported.

Following configuration options are available for this node:
 - *network_protocol*: tcp | udp
 - *syslog_protocol*: rfc3164
 - *address*: (hostname|ip, port) for example (127.0.0.1, 5104)

## Intermediate
### rx_grouper
This is the most common node in any configuration that matches input against regular expressions, parses message components
and forwards result to different output nodes.

Following configuration options are available for this node:
 - *groups*: a dictionary containing regular expression groups. Key is the name of the group and the group itself is defined with a
 dictionary that contains keys rx_list which holds a list of regular expressions and outputs node that contains name of the
 output nodes to forward this message to should any of the regular expressions match.
 regular expressions in the rx_list can either be plain string in which case it's assumed that we should match this expression
 against the message.content field or a tuple where the first element denotes message field that we should match the regular
 expression against.

Example:
The following defines a node called filter that is of type rx_grouper and contains a single match group which has 2 match rules.
The first one matches if message.content field contains the word hint and the second rule matches if message.host field contains
"publicapi1"
If either of these rules match the output is sent to the node called writer.

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


## Output
### console_output
This output just prints out everything that is sent to it.

### log_output
This node will log all the input with syslog logger. Be careful not to introduce log parsing cycles with it!

### smtp_output
Following configuration options are available for this node:
 - *addresses*: list of e-mail addresses where to send the output
 - *send_interval*: do not send e-mail more often than this many seconds. Messages that are seen in between are gathered in batches.

### pipe_output
Writes out to a named pipe output.

The following configuration options are available for this node:
 - *path*: path to the named pipe. Mutually exclusive with the *command* option.
 - *command*: execute a Unix pipeline with the given command and send output to it. Mutually exlusive with the *path* option.
 
 - *bufsize*: how large should the buffer be. By default system default is used. 0 disabled buffering, 1 sets line based buffering and larger positive numbers set buffer size in bytes.
 - *append_newline*: append newline to the messages before writing

### statsd_output
Sends messages to the Statsd server. If you have nothing in the extradata dictionary of the message this module
will construct a Graphite key from the configured key_prefix value + name of the matched rx_grouper.
By naming extradata groups in specific ways you can force this module to send out several messages for each
incoming message.
The parts of the message under the message.extradata hierarchy that start with _ are considered special.
The values of the variables under extradata whose name ends with _value are used as a final component of the statsd key
and are sent as counters.
The keys that end with _time are considered to be of a timer type and are sent to the statsd with a name where the final component
of the key is the name of the group that matched this message. If the name of the key starts with _ref then the value of the extradata element
whose name follows is used as the final component of the statsd key.

The following configuration options are available for this node:
 - *host*: IP or name of the statsd server (default 127.0.0.1)
 - *port*: port of the statsd server (default 8125)
 - *key_prefix*: prefix all the metric names with this string

### mariadb_output
Following configuration options are available for this node:
 - *query*: query string
 - *arguments*: list of parameters for the query
 - *connection_parameters*: dictionary containing SQL connection parameters

# License
MIT

# Acknowledgements
Work on this project has been supported by Elion Ettevõtted AS
