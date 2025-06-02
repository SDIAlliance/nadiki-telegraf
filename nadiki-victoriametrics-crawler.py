import requests
from requests.auth import HTTPBasicAuth
import os
import sys
import time
import signal
import json
import pprint

SOCKS_PROXY=os.environ.get("SOCKS_PROXY")

last_timestamp = dict()

class VMQuery:

    def __init__(self, url):
        self.url = url
    
    def query(self, metricname):
        #response = requests.get(f"{self.url}/select/0/prometheus/api/v1/query?query={metricname}", proxies=dict(http=SOCKS_PROXY, https=SOCKS_PROXY))
        # We use the VictoriaMetrics expor instead of the query endpoint because we need stable timestamps without interpolation:
        response = requests.get(f"{self.url}/select/0/prometheus/api/v1/export?match[]={metricname}&start=-1h", proxies=dict(http=SOCKS_PROXY, https=SOCKS_PROXY))
        response.raise_for_status()
        return response.text

def signal_handler(a,b):
#    pprint.pprint(last_timestamp)
    vmq = VMQuery(os.environ.get("VICTORIA_METRICS_URL"))
    r = vmq.query(os.environ.get("VICTORIA_METRICS_METRIC"))
    for line in r.split("\n"):
        if not line.strip(): # ignore empty lines
            continue
        data_point = json.loads(line)
        timestamp = data_point["timestamps"][0]
#        # only consider lines newer than the last one seen
#        try:
#            last_ts = last_timestamp[f'{data_point["metric"]["__name__"]}/{data_point["metric"]["instance"]}']
#            if last_ts >= timestamp:
#                continue
#        except:
#            pass
        tag_string = ",".join([f"{k}={data_point['metric'][k]}" for k in data_point["metric"]])
        field_string = f"value={data_point['values'][0]}"
        last_timestamp[f'{data_point["metric"]["__name__"]}/{data_point["metric"]["instance"]}'] = timestamp
        print(f"{os.environ.get('VICTORIA_METRICS_METRIC')},{tag_string} {field_string} {timestamp}000000")

def main():
    signal.signal(signal.SIGHUP, signal_handler)
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
