#!env python3
#
#

import fileinput
import pprint
import shlex
import subprocess
import re
import sys
import json

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

regex = re.compile("cri-containerd-([^.]*).scope")

# FIXME: refresh this table every now and then
cp = subprocess.run(["crictl", "ps", "-o", "json"], capture_output=True)
containers = json.loads(cp.stdout)
# create a translation table from pod (sandbox) ID to a dictionary of labels
# (we assume that most of the time, all running pods will be requested though
# the batching feature of proton remote UDFs, so it does not hurt
# to create the whole table)
pod2label = {}
for c in containers["containers"]:
    pod2label[c["podSandboxId"]] = c["labels"]

# main loop
for line in fileinput.input():
    (measurement, tags, fields, ts) = parse_line(line)
    if tags.get("id") != None:
      podid = ""
      try:
        podid = regex.findall(tags["id"])[0]
        print(podid, file=sys.stderr)
        tags = { **tags,  **pod2label[podid] }
        print(f'{measurement},{",".join([f"{k}={tags[k]}" for k in tags.keys()])} {".".join([f"{fieldname}={fields[fieldname]}" for fieldname in fields.keys()])} {ts}') 
      except:
          print(f"Something went wrong with id {tags.get('id')}", file=sys.stderr)
          pass

