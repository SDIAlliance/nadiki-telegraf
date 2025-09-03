"""
Call electricitymap.com API to retrieve histories of various values and output them
in InfluxDB format.

The following environment variables must be set:
- ELECTRICITYMAP_AUTH_TOKEN: the auth token to use for authenticating with the electricitimaps API
- ELECTRICITYMAP_ZONE: zone parameter to use for electricitimap, defaults to NL
- TAG_COUNTRY_CODE: country_code to tag output metrics
- TAG_FACILITY_ID: facility_id to tag output metrict
"""

import os
import requests
import dateutil.parser
#import pprint

DEFAULT_ZONE = "NL"

def fetch_electricity_data(data_type: str, zone: str, auth_token: str) -> list:
    """
    Perform an API call to electricitymaps and return the result 

    Args:
        data_type (str): name of the data to retrieve (see electricitymaps documentation)
        zone (str): zone parameter for the API call, usually a two-letter country-code
        auth_token (str): auth token to use for authenticating with the electricitymaps API
    Returns:
        list: list of dictionaries as returned by electricitymaps
    """
    url = f"https://api.electricitymap.org/v3/{data_type}/history?zone={zone}"
    response = requests.get(url, headers={"auth-token": auth_token})
    response.raise_for_status()
    data = response.json()
    history = data.get("history", [])
    return history
#    history = [
#        {
#            "value": float(item["carbonIntensity"]),
#            "time": dateutil.parser.isoparse(item["datetime"]),
#        }
#        for item in history
#    ]
#    return history

def print_em_history_as_influx_data(history: list, metricname: str, propertyname: str) -> None:
    """
    Print an electricitymaps history structure as a list of Influx metrics

    Args:
        history (list): list of dicts as returned by electricitymaps calls of type "history"
        metricname (str): name of the metric to print
        propertyname (str): name of the property in each of history's entries, containing the value to print
    Returns:
        None
    """
    for item in history:
        print(f"electricitymap,country_code={os.environ.get('TAG_COUNTRY_CODE')},facility_id={os.environ.get('TAG_FACILITY_ID')} {metricname}={item[propertyname]} {int(dateutil.parser.parse(item['datetime']).timestamp())*10**9}")

if __name__ == "__main__":
    print_em_history_as_influx_data(fetch_electricity_data("carbon-intensity", os.environ.get("ELECTRICITYMAP_ZONE", DEFAULT_ZONE), os.environ.get("ELECTRICITYMAP_AUTH_TOKEN")), "grid_emission_factor_grams", "carbonIntensity")
    print_em_history_as_influx_data(fetch_electricity_data("power-breakdown", os.environ.get("ELECTRICITYMAP_ZONE", DEFAULT_ZONE), os.environ.get("ELECTRICITYMAP_AUTH_TOKEN")), "grid_renewable_percentage", "renewablePercentage")
