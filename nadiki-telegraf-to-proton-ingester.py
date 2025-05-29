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
import requests
import os
from proton_driver import client

PROTON_INGEST_URL = "http://localhost:3218/proton/v1/ingest/streams/influxdb_metrics"

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
        #print(json.dumps({ "columns": columns, "data": data }), file=sys.stderr)
        headers = {"Content-Type": "application/json"}
        payload = { "columns": columns, "data": data }
        response = requests.post(PROTON_INGEST_URL, headers=headers, json=payload)
        data = []
    signal.alarm(1)

if __name__ == "__main__":
    # we should fork one process per query
    if os.fork() > 0:
        # child process queries proton and outputs metrics
        c = client.Client(host='127.0.0.1', port=8463)
        rows = c.execute_iter(
            "SELECT * FROM influxdb_metrics"
            #"SELECT server, map_cast(['power_consumption'], [fields['current_power_consumption_watts']*3600/(timestamp-lag(timestamp))]) FROM influxdb_metrics WHERE fields['current_power_consumption_watts'] != ''"
        )
        for row in rows:
            (measurement, tags, fields, timestamp, ts) = row
            tag_strings = [f"{tagname}={tags[tagname]}" for tagname in tags.keys()]
            field_strings = [f"{fieldname}={fields[fieldname]}" for fieldname in fields.keys()]
            print(f"{measurement},{','.join(tag_strings)} {'.'.join(field_strings)} {timestamp}")
            #print(row, file=sys.stderr)
    else:
        # parent process does the ingestion into proton
        signal.signal(signal.SIGALRM, dump_metrics)
        signal.alarm(1)
        for line in fileinput.input():
            data.append(parse_line(line))
