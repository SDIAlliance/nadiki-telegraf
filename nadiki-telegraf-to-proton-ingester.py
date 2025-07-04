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
import itertools
import setproctitle

from multiprocessing import Process, Lock

PROTON_INGEST_URL = f"http://{os.environ.get('PROTON_HOST')}:3218/proton/v1/ingest/streams/"

# primary keys of our streams
# this should go to a config file
STREAM_CONFIG = {
    "ipmi_dcmi_power_consumption_watts":    ["instance"],
    "node_cpu_seconds_total":               ["instance", "cpu", "mode"],
    "node_network_transmit_bytes_total":    ["instance", "device"],
    "node_network_receive_bytes_total":     ["instance", "device"],
    "node_network_transmit_packets_total":  ["instance", "device"],
    "node_network_receive_packets_total":   ["instance", "device"],
    "node_disk_read_bytes_total":           ["instance", "device"],
    "node_disk_written_bytes_total":        ["instance", "device"],
    "node_disk_reads_completed_total":      ["instance", "device"],
    "node_disk_writes_completed_total":     ["instance", "device"]
}

QUERIES = [
    # Calculate server_energy_consumption_kwh by multiplying Watts with the fraction of an hour which lies between two data points (and then dividing though 1000 to get the kilos)
    """
        SELECT
        'server', tags, map_cast(['server_energy_consumption_kwh'], [((date_diff('s', t2, t1) / 3600) * watts) / 1000]) AS fields, to_unix_timestamp64_nano(t1)
        FROM
        (
            SELECT
            instance, tags, to_float(fields['value']) AS watts, _tp_time AS t1, lag(_tp_time) OVER (PARTITION BY instance) AS t2
            FROM
            ipmi_dcmi_power_consumption_watts
        )
        WHERE
        (t1 != t2) AND (date_diff('s', t2, t1) < 86400)
    """,
#    # Calculate fraction of time (between 0 and 1) in which CPU cores were non-idle
#    """
#        SELECT
#        'server', tags, map_cast(['cpu_not_idle_fraction'], [sum(seconds-last_seconds)/date_diff('s', t2, t1)]) as fields, to_unix_timestamp64_nano(t1)
#        FROM
#        (
#            SELECT
#            tags, to_float(fields['value']) as seconds, lag(to_float(fields['value'])) over (partition by instance, cpu, mode) as last_seconds, _tp_time as t1, lag(_tp_time) over (partition by instance, cpu, mode) as t2
#            FROM
#            node_cpu_seconds_total
#            WHERE
#            mode != 'idle'
#        )
#        WHERE
#        (t1 != t2) AND (date_diff('s', t2, t1) < 86400) GROUP BY tags, t2, t1
#    """
]

# generate queries which are very similar (network and disk)
QUERIES.extend([
    ##
    f"""
        SELECT
        'server', tags, map_cast(['network_{transmit_receive}_{bytes_packets}'], [sum(units-last_units)]) as fields, to_unix_timestamp64_nano(t1)
        FROM
        (
            SELECT
            tags, to_float(fields['value']) as units, lag(to_float(fields['value'])) over (partition by instance, device) as last_units, _tp_time as t1, lag(_tp_time) over (partition by instance, device) as t2
            FROM
            node_network_{transmit_receive}_{bytes_packets}_total
        )
        WHERE
        (t1 != t2) AND (date_diff('s', t2, t1) < 86400) GROUP BY tags, t2, t1
    """
    for (transmit_receive, bytes_packets) in itertools.product(["transmit", "receive"], ["bytes", "packets"])])

QUERIES.extend([
    ## number of bytes read and written
    f"""
        SELECT
        'server', tags, map_cast(['io_bytes_{read_written}'], [sum(units-last_units)]) as fields, to_unix_timestamp64_nano(t1)
        FROM
        (
            SELECT
            tags, to_float(fields['value']) as units, lag(to_float(fields['value'])) over (partition by instance, device) as last_units, _tp_time as t1, lag(_tp_time) over (partition by instance, device) as t2
            FROM
            node_disk_{read_written}_bytes_total
        )
        WHERE
        (t1 != t2) AND (date_diff('s', t2, t1) < 86400) GROUP BY tags, t2, t1
    """
    for (read_written) in ["read", "written"]])

QUERIES.extend([
    ## number of reads and writes completed
    f"""
        SELECT
        'server', tags, map_cast(['io_{reads_writes}'], [sum(units-last_units)]) as fields, to_unix_timestamp64_nano(t1)
        FROM
        (
            SELECT
            tags, to_float(fields['value']) as units, lag(to_float(fields['value'])) over (partition by instance, device) as last_units, _tp_time as t1, lag(_tp_time) over (partition by instance, device) as t2
            FROM
            node_disk_{reads_writes}_completed_total
        )
        WHERE
        (t1 != t2) AND (date_diff('s', t2, t1) < 86400) GROUP BY tags, t2, t1
    """
    for (reads_writes) in ["reads", "writes"]])


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
    #print("alarm!", file=sys.stderr)
    for k in data.keys():
        #print(f"{k} has {len(data[k])} entries", file=sys.stderr)
        if len(data[k]) > 0:
            #print(json.dumps({ "columns": columns, "data": data }), file=sys.stderr)
            headers = {"Content-Type": "application/json"}
            columns = STREAM_CONFIG[k] + ["tags", "fields", "timestamp", "_tp_time"]
            payload = { "columns": columns, "data": data[k] }
            #print(json.dumps(payload), file=open("debug.json", "w"))
            response = requests.post(f"{PROTON_INGEST_URL}{k}", headers=headers, json=payload)
            response.raise_for_status()
            data[k] = []
    signal.alarm(1)

def handle_query(q, lock):
    # child process queries proton and outputs metrics
    setproctitle.setproctitle(q)
    c = client.Client(host=os.environ.get('PROTON_HOST'), port=8463)
    rows = c.execute_iter(q)
    for row in rows:
        (measurement, tags, fields, timestamp) = row
        tag_strings = [f"{tagname}={tags[tagname]}" for tagname in tags.keys()]
        field_strings = [f"{fieldname}={fields[fieldname]}" for fieldname in fields.keys()]
        lock.acquire()
        print(f"{measurement},{','.join(tag_strings)} {'.'.join(field_strings)} {timestamp}")
        lock.release()
        #print(row, file=sys.stderr)
        ## this never terminates

if __name__ == "__main__":
    # create the streams
    c = client.Client(host=os.environ.get('PROTON_HOST'), port=8463)
    for s in STREAM_CONFIG:
        c.execute(f"DROP STREAM IF EXISTS {s}")
        create_stmt = f"CREATE STREAM {s} (" \
            + ", ".join([f"{field} string" for field in STREAM_CONFIG[s]]) \
            + ", tags map(string, string), fields map(string, string), timestamp BIGINT)" \
            + f" PRIMARY KEY ({','.join(STREAM_CONFIG[s])}) SETTINGS mode='versioned_kv' "
        #print(create_stmt, file=sys.stderr)
        c.execute(create_stmt)

    # fork one child per query
    lock = Lock()
    for q in QUERIES:
        Process(target=handle_query, args=(q, lock)).start()


    # parent process does the ingestion into proton
    signal.signal(signal.SIGALRM, dump_metrics)
    signal.alarm(1)
    for line in fileinput.input():
        #print(line, file=sys.stderr)
        (measurement, tags, fields, ts) = parse_line(line)
        data.setdefault(measurement, [])
        #print(f"tags={tags}, k={STREAM_CONFIG[measurement]}", file=sys.stderr)
        pkey_values = [tags[k] for k in STREAM_CONFIG[measurement]]
        data[measurement].append(pkey_values + [tags, fields, ts, datetime.datetime.fromtimestamp(int(ts)/10**9, datetime.timezone.utc).strftime("%F %T.%f")])
