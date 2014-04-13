import sys
import pprint

from punnsilm import read_config

nodelist = read_config(sys.argv[1])
pprint.pprint(nodelist)
