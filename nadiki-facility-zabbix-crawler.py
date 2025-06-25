"""

Telegraf execd input to crawl Zabbix

This script can be run from telegraf as an execd
plugin. It will run forever and output data when
receiving a SIGHUP. This script is part of the Nadiki project
(https://www.ier.uni-stuttgart.de/forschung/projekte/aktuell/nadiki/)
and is geared towards the requirements in this project.

The configuration is done with envitonment variables:

- ZABBIX_URL must contain the URL of a Zabbix instance.
- ZABBIX_USERNAME and ZABBIX_PASSWORD must contain username and password
  for Zabbix. These will be used for HTTP basic auth and for logging into Zabbix.
- DC_PREFIX is used as a prefix for the Zabbix metric names
- NADIKI_HOST is the host inside Zabbix which contains the metrics relevant for us.

The global dict METRIC_MAP describes which output metrics are generated from which
Zabbix metrics. The keys are names of fields in the output (the measurement name
is always "facility"). The value is again a dictionary with these keys:

- `zabbix_key` is the name of the key in Zabbix
- `diff` is a bool stating whether to calculate differenes between consecutive values
- `rate` is a bool stating whether to divide each value by the fraction of an hour betwee the data points

"""
import requests
from requests.auth import HTTPBasicAuth
import os, sys
import signal
import time

ZABBIX_URL      = os.environ.get("ZABBIX_URL")
ZABBIX_USERNAME = os.environ.get("ZABBIX_USERNAME")
ZABBIX_PASSWORD = os.environ.get("ZABBIX_PASSWORD")
DC_PREFIX       = os.environ.get("SEVERIUS_DC_PREFIX")
NADIKI_HOST     = os.environ.get("NADIKI_HOST", "EDS-NADIKI")
#JOULES_PER_KWH = 3600000

METRIC_MAP = {
    "heatpump_avg_watts": {
        "zabbix_key": f"{DC_PREFIX}_Heat_Pump_Power_Wh",
#        "diff": True,
#        "rate": True
    },
    "office_avg_watts": {
        "zabbix_key": f"{DC_PREFIX}_Office_Power_Wh",
#        "diff": True,
#        "rate": True
    },
    "total_generator_avg_watts": {
        "zabbix_key": f"{DC_PREFIX}_Generators_Power_Wh",
#        "diff": True,
#        "rate": True
    },
    "grid_transformers_avg_watts": {
        "zabbix_key": f"{DC_PREFIX}_Total_Grid_Power_Wh",
#        "diff": True,
#        "rate": True
    },
    "onsite_renewable_energy_avg_watts": {
        "zabbix_key": f"{DC_PREFIX}_Power_PV_Wh",
#        "diff": True,
#        "rate": True
    },
    "it_power_usage_level1_avg_watts": {
        "zabbix_key": f"{DC_PREFIX}_Total_IT_Power_Basic_Res_Wh",
#        "diff": True,
#        "rate": True
    },
    "it_power_usage_level2_avg_watts": {
        "zabbix_key": f"{DC_PREFIX}_Total_IT_Power_Intermediate_Res_Wh",
#        "diff": True,
#        "rate": True
    },
    "pue_1_ratio": {
        "zabbix_key": f"{DC_PREFIX}_PUE_Basic_Res",
#        "diff": False,
#        "rate": False
    },
    "pue_2_ratio": {
        "zabbix_key": f"{DC_PREFIX}_PUE_Intermediate_Res",
#        "diff": False,
#        "rate": False
    }
}

class ZabbixClient:
    """
    Generic client for the Zabbix API

    The only assumption that we make here is that the same credentials are used for HTTP basic auth and 
    for Zabbix itself.
    """
    def __init__(self, url, username, password, basic_auth_username, basic_auth_password):
        self.url = url
        self.username = username
        self.password = password
        self.basic_auth_username = basic_auth_username
        self.basic_auth_password = basic_auth_password
        self.basic_auth_token = HTTPBasicAuth(basic_auth_username, basic_auth_password)
        self.auth_token = self._authenticate()

    def _zabbix_api_call(self, method, params, auth=None):
        headers = {"Content-Type": "application/json-rpc"}
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
            "auth": auth,
        }
        response = requests.post(self.url, headers=headers, json=payload, auth=self.basic_auth_token)
        response.raise_for_status()
        if response.json().get("error"):
            raise Exception(response.json()["error"])
        return response

    def _authenticate(self):
        response = self._zabbix_api_call("user.login", {"user": self.username, "password": self.password})
        return response.json()["result"]

    def get_host_id_by_name(self, hostname):
        response = self._zabbix_api_call("host.get", {"output": ["hostid"], "filter":{"host": hostname}}, self.auth_token)
        assert len(response.json()["result"]) == 1, f"Expected one result, but received {response.json()['result']}"
        return response.json()["result"][0]["hostid"]

#    def get_item_id_by_name(self, hostid, itemname):
#        response = self._zabbix_api_call("item.get", {"output": ["itemid"], "filter":{"key_": itemname}, "hostids": hostid}, self.auth_token)
#        assert len(response.json()["result"]) == 1, f"Expected one result, but received {response.json()['result']}"
#        return response.json()["result"][0]["itemid"]
#
#    def get_item(self, hostid, itemid):
#        response = self._zabbix_api_call("item.get", {"hostids": hostid, "itemids": itemid, "output": ["lastvalue"]}, self.auth_token)
#        #print(response.json())

def signal_handler(signum, frame):
    """
    Signal handler which retrieves metrics from Zabbix and outputs
    them. Since we do not know in which intervals Zabbix delivers new
    data, we store the latest timestamp and value per metric and compare
    them each time. This means that we can poll Zabbix every 30s without
    creating duplicate data.

    """
    r = clnt._zabbix_api_call("item.get", {"hostids": hostid, "output": ["key_", "lastclock", "lastvalue"]}, clnt.auth_token)

    item_dict = { x["key_"]: (float(x["lastvalue"]), int(x["lastclock"])) for x in r.json()["result"] }
    for key, desc in METRIC_MAP.items():
        try:
            (value, clock) = item_dict[desc["zabbix_key"]]
            # Skip data points that we've already seen
            if previous_metric.get(key) != None:
                if previous_metric.get(key).get("clock") == clock:
                    continue
            print(f"facility,country_code={os.environ.get('TAG_COUNTRY_CODE')},facility_id={os.environ.get('TAG_FACILITY_ID')} {key}={value} {int(clock)*10**9}")
            previous_metric[key] = { "clock": clock, "value": value }
        except KeyError as e:
            print(e, file=sys.stderr)
            pass

if __name__ == "__main__":
    clnt = ZabbixClient(ZABBIX_URL, ZABBIX_USERNAME, ZABBIX_PASSWORD, ZABBIX_USERNAME, ZABBIX_PASSWORD)
    hostid = clnt.get_host_id_by_name(NADIKI_HOST)
    signal.signal(signal.SIGHUP, signal_handler)
    # this hash will store the latest timestamps and values per metric
    previous_metric = {}
    while True:
        time.sleep(3600)
