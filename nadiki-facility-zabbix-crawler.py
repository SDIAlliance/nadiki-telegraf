import requests
from requests.auth import HTTPBasicAuth
import os

ZABBIX_URL      = os.environ.get("ZABBIX_URL")
ZABBIX_USERNAME = os.environ.get("ZABBIX_USERNAME")
ZABBIX_PASSWORD = os.environ.get("ZABBIX_PASSWORD")
DC_PREFIX       = os.environ.get("SEVERIUS_DC_PREFIX")

JOULES_PER_KWH = 3600000

# Map the value names that we want to lambdas which calculate the value from Zabbix items.
# In item_dict, the [0] entry is the value and [1] is the timestamp.
#
# FIXME: try to reduce reduncancy in this section
METRIC_MAP = {
    "heatpump_power_consumption_joules": lambda dc_prefix, item_dict: (
        float(item_dict[f"{dc_prefix}_Heat_Pump_Power_Wh"][0])*JOULES_PER_KWH,
        item_dict[f"{dc_prefix}_Heat_Pump_Power_Wh"][1]
    ),
    "office_energy_use_joules": lambda dc_prefix, item_dict: (
        float(item_dict[f"{dc_prefix}_Office_Power_Wh"][0])*JOULES_PER_KWH,
        item_dict[f"{dc_prefix}_Office_Power_Wh"][1]
    ),
    #"dc_water_usage_cubic_meters": lambda dc_prefix, item_dict: { },
    #"office_water_usage_cubic_meters": lambda dc_prefix, item_dict: { },
    "total_generator_energy_joules": lambda dc_prefix, item_dict: (
        float(item_dict[f"{dc_prefix}_Generators_Power_Wh"][0])*JOULES_PER_KWH,
        item_dict[f"{dc_prefix}_Generators_Power_Wh"][1]
    ),
    #"generator_load_factor_ratio": lambda dc_prefix, item_dict: { },
    "grid_transformers_energy_joules": lambda dc_prefix, item_dict: (
        float(item_dict[f"{dc_prefix}_Total_Grid_Power_Wh"][0])*JOULES_PER_KWH,
        item_dict[f"{dc_prefix}_Total_Grid_Power_Wh"][1]
    ),
    "onsite_renewable_energy_joules": lambda dc_prefix, item_dict: (
        float(item_dict[f"{dc_prefix}_Power_PV_Wh"][0])*JOULES_PER_KWH,
        item_dict[f"{dc_prefix}_Power_PV_Wh"][1]
    ),
    "it_power_usage_level1_joules": lambda dc_prefix, item_dict: (
        float(item_dict[f"{dc_prefix}_Total_IT_Power_Basic_Res_Wh"][0])*JOULES_PER_KWH,
        item_dict[f"{dc_prefix}_Total_IT_Power_Basic_Res_Wh"][1]
    ),
    "it_power_usage_level2_joules": lambda dc_prefix, item_dict: (
        float(item_dict[f"{dc_prefix}_Total_IT_Power_Intermediate_Res_Wh"][0])*JOULES_PER_KWH,
        item_dict[f"{dc_prefix}_Total_IT_Power_Intermediate_Res_Wh"][1]
    ),
    #"renewable_energy_certificates_joules": lambda dc_prefix, item_dict: { },
    #"grid_emission_factor_grams": lambda dc_prefix, item_dict: { },
    #"backup_emission_factor_grams": lambda dc_prefix, item_dict: { },
    #"electricity_source": lambda dc_prefix, item_dict: { },
    "pue_1_ratio": lambda dc_prefix, item_dict: (
        float(item_dict[f"{dc_prefix}_PUE_Basic_Res"][0]),
        item_dict[f"{dc_prefix}_PUE_Basic_Res"][1]
    ),
    "pue_2_ratio": lambda dc_prefix, item_dict: (
        float(item_dict[f"{dc_prefix}_PUE_Intermediate_Res"][0]),
        item_dict[f"{dc_prefix}_PUE_Intermediate_Res"][1]
    )
}

class ZabbixClient:

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

if __name__ == "__main__":
    clnt = ZabbixClient(ZABBIX_URL, ZABBIX_USERNAME, ZABBIX_PASSWORD, ZABBIX_USERNAME, ZABBIX_PASSWORD)
    hostid = clnt.get_host_id_by_name("EDS-NADIKI")

    r = clnt._zabbix_api_call("item.get", {"hostids": hostid, "output": ["key_", "lastclock", "lastvalue"]}, clnt.auth_token)

    item_dict = { x["key_"]: (x["lastvalue"], x["lastclock"]) for x in r.json()["result"] }
    for key, func in METRIC_MAP.items():
        try:
            (value, clock) = func(DC_PREFIX, item_dict)
            print(f"facility,country_code={os.environ.get('TAG_COUNTRY_CODE')},facility_id={os.environ.get('TAG_FACILITY_ID')} {key}={value} {int(clock)*10**9}")
        except KeyError:
            #print(f"Key {key} not found")
            pass
