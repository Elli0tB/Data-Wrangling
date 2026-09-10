from dotenv import load_dotenv
import os
import requests
import json
import pandas as pd
# TODO: make sure you define UGRC_API_TOKEN in .env in the same dir
def request(url, params):
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(f"Status Code: {err.response.status_code}")
        print(response.json()["message"])
        return False
    return response.json()

def getGeometryKeys(geometry):
    if isinstance(geometry,dict):
        return tuple(sorted(geometry.keys()))
    return None


def getWKID(geometry): 
    if isinstance(geometry, dict):
        spatialReference = geometry.get("spatialReference")
        if spatialReference is None:
            return None
        return spatialReference.get("wkid")
    return None

def assemble(response):
    #check is the response is a dict that I can use 
    if not isinstance(response, dict):
        print("----ERROR RESPONSE WAS NOT A VALID DICT----")
        return False

    records = response["result"]
    dataFrame = pd.DataFrame(records)

    #check for any null in the geometry which should just be the shape field
    if dataFrame["geometry"].isnull().sum() > 0:
        print("----ERROR GEOMETRY WAS NOT FOUND IN THE RECORDS----")
        return False

    #check that geometry has all of its keys 
    geometry_keys = dataFrame["geometry"].apply(getGeometryKeys)
    print(geometry_keys.value_counts()) 

    #check that wkid exists for all geometry 
    wkid = dataFrame["geometry"].apply(getWKID)
    print(wkid.value_counts())

    #export the file to a cvs
    dataFrame.to_csv('gis_output.csv', index=False)

    return dataFrame

def validate(dataFrame):
    print(f"\nTotal items gathered: {dataFrame.shape[0]}\n")
    print(f"\n----Printing the data frames info----\n")
    dataFrame.info()
    print(f"\n----Printing data frame head----\n{dataFrame.head(10)}\n")

def main():
    load_dotenv()
    token = os.getenv("UGRC_API_TOKEN")
    params = {"apikey": token}

    url = "https://api.mapserv.utah.gov/api/v1/search/utilities.electrical_lines/"
    fields = "objectid,xid,shape@"

    field_request = request(url+fields, params)
    dataFrame = assemble(field_request)
    validate(dataFrame)
    #print(json.dumps(field_request, indent=4))

main()

