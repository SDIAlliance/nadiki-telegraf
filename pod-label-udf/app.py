from flask import Flask, request
import json
import subprocess
import os
import sys

if os.getuid() != 0:
    sys.exit("This process must be run as root in order to use crictl!")

app = Flask(__name__)

#
# This app implements a remote UDF for Proton (https://docs.timeplus.com/remote-udf)
#
# It translates pod IDs (which are used in cadvisor metrics) into labels.
#

@app.route("/", methods=["GET", "POST"])
def index():
    pod_ids = request.json["pod_id"] # this is an array

    # call crictl and get all containers
    #cp = subprocess.run(["cat", "crictl-ps.json"], capture_output=True)   
    cp = subprocess.run(["crictl", "ps", "-o", "json"], capture_output=True)
    print(cp.stderr)
    containers = json.loads(cp.stdout)
    # create a translation table from pod (sandbox) ID to a dictionary of labels
    # (we assume that most of the time, all running pods will be requested though
    # the batching feature of proton remote UDFs, so it does not hurt
    # to create the whole table)
    pod2label = {}
    for c in containers["containers"]:
        pod2label[c["podSandboxId"]] = c["labels"]
    # and now, create the result by looking up all input IDs in our translation table
    result = []
    for id in pod_ids:
        result.append(pod2label[id])
    return(json.dumps({ "result": result }))
