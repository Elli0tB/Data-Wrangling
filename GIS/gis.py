from dotenv import load_dotenv
import os
import requests
import json
import pandas as pd
# TODO: make sure you define UGRC_API_TOKEN in .env in the same dir
load_dotenv()
token = os.getenv("UGRC_API_TOKEN")
def request(url, params):
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(f"Status Code: {err.response.status_code}")
        print(response.json()["message"])
        return False
    return response.json()

def assemble(response):
    records = response["result"]
    print(records[0])

    dataFrame = pd.DataFrame(records)
    print(dataFrame["attributes"].iloc[0])
    print(dataFrame["geometry"].iloc[0])

   # print(dataFrame.columns)
    """
    print(dataFrame["shape@"].iloc[0])  # inspect one raw geometry value
    print(type(dataFrame["shape@"].iloc[0]))

    print(dataFrame["shape@"].isna().sum())
    print(dataFrame["shape@"].apply(lambda g: g is None or g == {}).sum())
    dataFrame["geom_keys"] = dataFrame["shape@"].apply(lambda g: tuple(sorted(g.keys())) if isinstance(g, dict) else None)
    print(dataFrame["geom_keys"].value_counts())

    dataFrame["wkid"] = dataFrame["shape@"].apply(lambda g: g.get("spatialReference", {}).get("wkid") if isinstance(g, dict) else None)
    print(dataFrame["wkid"].value_counts())

    # Export your clean DataFrame to gis_output.csv (using index=False).
    """

params = {"apikey": token}

url_SIGD = "https://api.mapserv.utah.gov/api/v1/info/featureClassNames?sgidCategory=utilities"

url_Field = "https://api.mapserv.utah.gov/api/v1/info/fieldnames/electrical_lines"

url = "https://api.mapserv.utah.gov/api/v1/search/utilities.electrical_lines/"
fields = "objectid, xid, shape@"

field_request = request(url+fields, params)

assemble(field_request)
#print(json.dumps(field_request, indent=4))



