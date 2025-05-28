#!env python3
#
# This script acts as a processor to Telegraf
# and ingests metrics into the Timeplus Proton streaming database.
#

import fileinput
import pprint
import shlex
import signal
import json
import sys

def parse_line(line):
    # parse the input line (Influx line protocol)
    (tmp, fields_str, ts) = shlex.split(line) # shlex.split respects backslashed spaces
    pairs = tmp.split(",")
    measurement = pairs[0]
    tags = {}
    for x in pairs[1:]:
        (k,v) = x.split("=")
        tags[k] = v
    fields = {}
    for x in fields_str.split(","):
        (k,v) = x.split("=")
        fields[k] = v
    return measurement, tags, fields, ts

columns = ["measurement", "tags", "fields", "timestamp"]
data = []

def dump_metrics(a,b):
    global columns
    global data
    print("alarm!", file=sys.stderr)
    if len(data) > 0:
        print(json.dumps({ "columns": columns, "data": data }), file=sys.stderr)
        data = []
    signal.alarm(1)

signal.signal(signal.SIGALRM, dump_metrics)
signal.alarm(1)

if __name__ == "__main__":
    for line in fileinput.input():
        data.append(parse_line(line))
