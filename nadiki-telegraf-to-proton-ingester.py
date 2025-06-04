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
import datetime

PROTON_INGEST_URL = "http://localhost:3218/proton/v1/ingest/streams/"

# this should go to a config file
STREAM_CONFIG = {
    "ipmi_dcmi_power_consumption_watts": ["instance"]
}

QUERIES = [
    "SELECT * FROM ipmi_dcmi_power_consumption_watts"
]

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

data = {} # will contain one key per metric with an array of parsed lines as value

def dump_metrics(a,b):
    global data
    print("alarm!", file=sys.stderr)
    for k in data.keys():
        print(f"{k} has {len(data[k])} entries", file=sys.stderr)
        if len(data[k]) > 0:
            #print(json.dumps({ "columns": columns, "data": data }), file=sys.stderr)
            headers = {"Content-Type": "application/json"}
            columns = STREAM_CONFIG[k] + ["tags", "fields", "timestamp", "_tp_time"]
            payload = { "columns": columns, "data": data[k] }
            #print(json.dumps(payload), file=sys.stderr)
            response = requests.post(f"{PROTON_INGEST_URL}{k}", headers=headers, json=payload)
            response.raise_for_status()
            data[k] = []
    signal.alarm(1)

if __name__ == "__main__":
    # create the streams
    c = client.Client(host='127.0.0.1', port=8463)
    for s in STREAM_CONFIG:
        c.execute(f"DROP STREAM IF EXISTS {s}")
        create_stmt = f"CREATE STREAM {s} (" \
            + ", ".join([f"{field} string" for field in STREAM_CONFIG[s]]) \
            + ", tags map(string, string), fields map(string, string), timestamp BIGINT)" \
            + f" PRIMARY KEY ({','.join(STREAM_CONFIG[s])}) SETTINGS mode='versioned_kv' "
        #print(create_stmt, file=sys.stderr)
        c.execute(create_stmt)

    # fork one child per query
    for q in QUERIES:
        if os.fork() > 0:
            # child process queries proton and outputs metrics
            c = client.Client(host='127.0.0.1', port=8463)
            rows = c.execute_iter(q)
            for row in rows:
                (measurement, tags, fields, timestamp, ts) = row
                tag_strings = [f"{tagname}={tags[tagname]}" for tagname in tags.keys()]
                field_strings = [f"{fieldname}={fields[fieldname]}" for fieldname in fields.keys()]
                print(f"{measurement},{','.join(tag_strings)} {'.'.join(field_strings)} {timestamp}")
                #print(row, file=sys.stderr)
                ## this never terminates

    # parent process does the ingestion into proton
    signal.signal(signal.SIGALRM, dump_metrics)
    signal.alarm(1)
    for line in fileinput.input():
        #print(line, file=sys.stderr)
        (measurement, tags, fields, ts) = parse_line(line)
        data.setdefault(measurement, [])
        #print(f"tags={tags}, k={STREAM_CONFIG[measurement]}", file=sys.stderr)
        pkey_values = [tags[k] for k in STREAM_CONFIG[measurement]]
        data[measurement].append([pkey_values, tags, fields, ts, datetime.datetime.fromtimestamp(int(ts)/10**9).strftime("%F %T.%f")])
