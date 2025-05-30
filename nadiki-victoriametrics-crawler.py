import requests
from requests.auth import HTTPBasicAuth
import os

SOCKS_PROXY=os.environ.get("SOCKS_PROXY")

class VMQuery:

    def __init__(self, url):
        self.url = url
    
    def query(self, metricname):
        response = requests.get(f"{self.url}/select/0/prometheus/api/v1/query?query={metricname}", proxies=dict(http=SOCKS_PROXY, https=SOCKS_PROXY))
        response.raise_for_status()
        return response.json()

if __name__ == "__main__":
    vmq = VMQuery(os.environ.get("VICTORIA_METRICS_URL"))
    r = vmq.query(os.environ.get("VICTORIA_METRICS_METRIC"))
    for x in r["data"]["result"]:
        tag_string = ",".join([f"{k}={x['metric'][k]}" for k in x["metric"]])
        field_string = f"value={x['value'][1]}"
        timestamp = x["value"][0]
        print(f"{os.environ.get('VICTORIA_METRICS_METRIC')},{tag_string} {field_string} {timestamp}000000")
