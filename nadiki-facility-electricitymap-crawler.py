# Partly copied from Robin Pesl's code
import os
import requests
import dateutil.parser
import pprint

def fetch_electricity_data() -> list:
    url = "https://api.electricitymap.org/v3/carbon-intensity/history?zone=NL" # FIXME: take the zone from an env variable but convert it to two letters before
    response = requests.get(url, headers={"auth-token": os.environ.get("ELECTRICITYMAP_AUTH_TOKEN")})
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

def print_em_history_as_influx_data(history):
    for item in history:
        print(f"electricitymap,country_code={os.environ.get('TAG_COUNTRY_CODE')},facility_id={os.environ.get('TAG_FACILITY_ID')} grid_emission_factor_grams={item['carbonIntensity']} {int(dateutil.parser.parse(item['datetime']).timestamp())*10**9}")

if __name__ == "__main__":
    print_em_history_as_influx_data(fetch_electricity_data())
