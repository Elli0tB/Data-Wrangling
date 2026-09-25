from dotenv import load_dotenv
import os
import sys
import requests
import time
import pandas as pd

def fetchRawData(URL, params):
    #before fetching data sleep, so we dont overload the api
    raw_data_frame = pd.DataFrame()
    time.sleep(1)
    print("requesting data from:", URL)
    #check the status for the request
    try: 
        request = requests.get(URL,params=params)
        request.raise_for_status()
        response = request.json().get("response")
        
    except requests.exceptions.HTTPError as err:
        print(f"Error status code {err.response.status_code}") 
        return False
    raw_data_frame = pd.DataFrame(response.get("data"))
    return raw_data_frame
   
def refineData(raw_data_gen, raw_data_com):
    if isinstance(raw_data_gen, pd.DataFrame):
        if isinstance(raw_data_com, pd.DataFrame):
            raw_data_com = raw_data_com.rename(columns={"state": "stateID"})
            merged = pd.merge(raw_data_gen, raw_data_com, on="stateID", suffixes=("_gen", "_com"), how="inner") 
            merged.dropna(axis=0, inplace= True)
            refined_data = []
            
            """ 
            Change list and explanation:
                "emisions-intensity": this is from carbon-dioxide-lbs. I chnaged the name becasue it was unintuitive what this really was
                I know this becasue i spent about an hour trying to produce this number and did not realise this was already the rate i was looking for
                
                the type casts are for easier downstream use since i was annoyed that i had to do this for the required math and no i wont need to do it again anywhere else
                
                Price-¢/kilowatthour is a name change because I think its cleaner than a price that has what its value is in a diffrent coloum to be annoying
                the diffrance is the total generation and consumption on the same table which I couldnt find from one end point so i made it my self

                the unit name change I did because I think it looks cleaner
            """
            for index, row in merged.iterrows():
                refined_row = {"Year": row['period_gen'],
                "State-ID" :row['stateID'], 
                "State-Name": row['stateDescription_gen'], 
                "emisions-intensity": float(row['carbon-dioxide-lbs']), 
                "Price-¢/kilowatthour": float(row['average-retail-price']), 
                "Total-Generation": float(row['net-generation']), 
                "Total-Consumption": float(row['total-disposition']), 
                "Difference": float(row['total-disposition']) - float(row['net-generation']), 
                "Total-Generation-Unit": "Megawatthours", 
                "Total-Consumption-Unit": "Megawatthours", 
                "Difference-Unit": "Megawatthours",
                "Difference-Notes": "Positive numbers are a deficit, negative numbers are a surplus"}
                refined_data.append(refined_row) 
            return pd.DataFrame(refined_data)
    print("ERROR: Excpected pandas dataframe recived flase value, check HTTPS status code above!")
    print("Quiting program, ERROR must be resolved")
    sys.exit()

def checkDataRaw(data):
    expected_states = {"AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI",
            "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN",
            "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY", "OH",
            "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "US", "UT", "VA", "VT",
            "WA", "WI", "WV", "WY"}
    if "stateID" in data.columns:
        returned_states = set(data["stateID"].unique())
        data.to_csv('raw_data_generation.csv', index=False)
    elif "state" in data.columns:
        returned_states = set(data["state"].unique())
        data.to_csv('raw_data_consumption.csv', index=False)
    else:
        print("ERROR: Raw data did not have a stateID or a state identifer")
        print("Quiting program, ERROR must be resolved")
        sys.exit()

    missing = expected_states - returned_states
    unexpected = returned_states - expected_states

    if missing or unexpected:
        print("Missing States:", missing)
        print("Unexpected States:", unexpected)
        print("ERROR: State validation failed")
        print("Quiting program, ERROR must be resolved")
        sys.exit()
    print("State check passed")

def checkDataClean(refined_data):
    refined_data.dropna(axis=0, inplace= True)
    if refined_data["State-ID"].is_unique:
        print("No duplicate states found in refined data")
        print("Exporting to cvs")
        refined_data.to_csv('refined_data.csv', index=False)
    else:
        print("Duplicate states found in refined data")
        print("Quiting program, ERROR must be resolved")
        sys.exit()


def Main():
    load_dotenv()
    token = os.getenv("API_TOKEN")
    #
    url_gen = "https://api.eia.gov/v2/electricity/state-electricity-profiles/summary/data/"
    params_gen = {
        "api_key": token, 
        "frequency": "annual", 
        "data[]": [ "average-retail-price",  "average-retail-price-rank", "carbon-dioxide", "carbon-dioxide-lbs", "generation-elect-utils", "net-generation"],
        "facets[stateID][]": ["AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "TN", "TX", "US", "UT", "VA", "VT", "WA", "WI","WV", "WY", "IA", "KS", "NM", "SD"],
        "start": "2018",
        "end": "2018",
        "sort[0][column]": "stateID",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000
    }
    raw_data_generation = fetchRawData(url_gen,params_gen)
    url_com = "https://api.eia.gov/v2/electricity/state-electricity-profiles/source-disposition/data/"
    params_com = {
        "api_key": token, 
        "frequency": "annual",
        "data[]": "total-disposition",
        "facets[state][]": ["AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "TN", "TX", "US", "UT", "VA", "VT", "WA", "WI","WV", "WY", "IA", "KS", "NM", "SD"],
        "start": "2018",
        "end": "2018",
        "sort[0][column]": "state",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000,
        }
    raw_data_consumption = fetchRawData(url_com,params_com)
    checkDataRaw(raw_data_generation)
    checkDataRaw(raw_data_consumption)
    refined_data = refineData(raw_data_generation,raw_data_consumption)
    print(refined_data)
    checkDataClean(refined_data)
    


Main()