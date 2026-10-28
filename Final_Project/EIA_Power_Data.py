from dotenv import load_dotenv
import os
import sys
import requests
import time
import pandas as pd
import numpy as np

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
        #return False
    raw_data_frame = pd.DataFrame(response.get("data"))
    return raw_data_frame

def refineData(raw_data_state, raw_data_com, raw_data_pwr_plnt):
    if isinstance(raw_data_state , pd.DataFrame) == False:
        print("ERROR: raw_state_data was not a pd dataframe")
        print("Quiting program, ERROR must be resolved")
        sys.exit()
    elif isinstance(raw_data_com , pd.DataFrame) == False:
        print("ERROR: raw_consumption_data was not a pd dataframe")
        print("Quiting program, ERROR must be resolved")
        sys.exit()
    elif isinstance(raw_data_pwr_plnt , pd.DataFrame) == False:
        print("ERROR: raw_power_plant_data was not a pd dataframe")
        print("Quiting program, ERROR must be resolved")
        sys.exit()
    else:
        raw_data_state = raw_data_state.rename(columns={"stateID": "state_id", "period": "year"})
        raw_data_com = raw_data_com.rename(columns={"state": "state_id","period": "year"})
        raw_data_pwr_plnt = raw_data_pwr_plnt.rename(columns={"state": "state_id","period": "year"})

        raw_data_state = raw_data_state.drop(columns=['stateDescription',
                                                    'average-retail-price-rank',
                                                    'carbon-dioxide',
                                                    'generation-elect-utils',
                                                    'average-retail-price-units',
                                                    'average-retail-price-rank-units',
                                                    'carbon-dioxide-units',
                                                    'carbon-dioxide-lbs-units',
                                                    'generation-elect-utils-units',
                                                    'net-generation-units'
                                                    ]) 
        #this is the end result table year,stateID,average-retail-price,carbon-dioxide-lbs,net-generation,

        
        raw_data_com = raw_data_com.drop(columns=['stateDescription',
                                                  'total-disposition-units'
                                                ]) 
        #this is the end result table year,state,stateDescription,total-disposition
    
        raw_data_pwr_plnt = raw_data_pwr_plnt.drop(columns=['plantCode',
                              'fuel2002',
                              'fuel2002TypeDescription',
                              'primeMover',
                              'stateDescription',
                              'gross-generation',
                              'gross-generation-units'
                              ]) 
        #this is the end result table period,plantName,fuelType,fuelTypeDescription,state,generation,generation-units,

        
        # Step 1: best and worst plant per state
        best = (raw_data_pwr_plnt.loc[raw_data_pwr_plnt.groupby('state_id')['generation'].idxmax(), ['year','plantName','fuelType','fuelTypeDescription','state_id','generation','generation-units']]
           .rename(columns={'plantName': 'best_plant', 'generation': 'best_generation', 'fuelTypeDescription'   : 'fuelTypeDescription_best',}))

        worst = (raw_data_pwr_plnt.loc[raw_data_pwr_plnt.groupby('state_id')['generation'].idxmin(), ['year','plantName','fuelType','fuelTypeDescription','state_id','generation','generation-units']]
            .rename(columns={'plantName': 'worst_plant', 'generation': 'worst_generation', 'fuelTypeDescription'   : 'fuelTypeDescription_worst'}))

        # Step 2: merge everything on state
        final = (raw_data_state.merge(raw_data_com, on=['state_id', 'year'], how='left')
            .merge(best, on='state_id', how='left')
            .merge(worst, on='state_id', how='left'))
        
        column_map = {
            # old name in `final`       : new name in output
            "year"                      : 'Year',
            'state_id'                  : 'State-ID',
            'average-retail-price'      : 'Electricity Price (¢/kWh)',
            'carbon-dioxide-lbs'        : 'Emisions-Intensity',
            'net-generation'            : 'Total-Generation (MWh)',
            'total-disposition'         : 'Total-Consumption (MWh)',
            'best_plant'                : 'Best Plant',
            'best_generation'           : 'Best-Plant-Generation',
            'fuelTypeDescription_best'  : 'Best-Plant-Type',
            'worst_plant'               : 'Worst-Plant',
            'worst_generation'          : 'Worst-Plant-Generation',
            'fuelTypeDescription_worst' : 'Worst-Plant-Type',
        }
    
        refined = final[list(column_map)].rename(columns=column_map)
        position = refined.columns.get_loc('Total-Consumption (MWh)') + 1   # position right after this column
        refined.insert(position, 'Diffrence', refined['Total-Generation (MWh)'].astype(int) - refined['Total-Consumption (MWh)'].astype(int))

        refined = refined.round(2).sort_values('State-ID').reset_index(drop=True)
        refined.to_csv('Structured.csv', index=False)
        print(refined)
        print(len(refined))
        return refined
    sys.exit()


def checkDataRaw(data):
    if data.empty:
        empty_frame = pd.DataFrame()
        return empty_frame
    
    #Check for empty rows
    print("---Checking for missing values---" )
    rows_missing_some_data =data[data.isna().any(axis=1)]
    print(f"---{len(rows_missing_some_data)} rows were missing at least 1 coloums data---")

    #check for empty rows and see if whitespace was hiding anything
    print("---Cheking for empty values with whitespace---")
    df_cleaned = data.replace(r'^\s*$', np.nan, regex=True)
    whitespace_empty_rows = data[df_cleaned.isna().all(axis=1)]
    print(f"---{len(whitespace_empty_rows)} rows were missing at least 1 coloums data and was hidden with white space---")

    #clear empty rows
    print("---Clearing empty rows---")
    cleard_data =data.dropna(how='all')
    print("---Empty rows removed---")
    return cleard_data
    
def CheckForMissingStates(data):
    if data.empty:
        empty_frame = pd.DataFrame()
        return empty_frame
    expected_states = {"AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI",
            "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN",
            "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY", "OH",
            "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT",
            "WA", "WI", "WV", "WY"}
    if "stateID" in data.columns:
        returned_states = set(data["stateID"].unique())
        #data.to_csv('raw_data_generation.csv', index=False)
    elif "state" in data.columns:
        returned_states = set(data["state"].unique())
        #data.to_csv('raw_data_consumption.csv', index=False)
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
        print(f"The following states are excluded from the data: {missing}")
        # print("Quiting program, ERROR must be resolved")
        # sys.exit()
    else :
        print("---State check passed---")

"""
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
"""

def requestStateData(token):
    url_gen = "https://api.eia.gov/v2/electricity/state-electricity-profiles/summary/data/"
    params_gen = {
        "api_key": token, 
        "frequency": "annual", 
        "data[]": [ "average-retail-price",  "average-retail-price-rank", "carbon-dioxide", "carbon-dioxide-lbs", "generation-elect-utils", "net-generation"],
        "facets[stateID][]": ["AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "TN", "TX", "UT", "VA", "VT", "WA", "WI","WV", "WY", "IA", "KS", "NM", "SD"],
        "start": "2018",
        "end": "2018",
        "sort[0][column]": "stateID",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000
    }
    raw_data_generation = fetchRawData(url_gen,params_gen)
    raw_gen = checkDataRaw(raw_data_generation)
    raw_gen.to_csv('raw_gen.csv', index=False)
    return raw_data_generation
    
def requestStateConsumptionData(token):
    url_com = "https://api.eia.gov/v2/electricity/state-electricity-profiles/source-disposition/data/"
    params_com = {
        "api_key": token, 
        "frequency": "annual",
        "data[]": "total-disposition",
        "facets[state][]": ["AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "TN", "TX", "UT", "VA", "VT", "WA", "WI","WV", "WY", "IA", "KS", "NM", "SD"],
        "start": "2018",
        "end": "2018",
        "sort[0][column]": "state",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000,
    }
    raw_data_consumption = fetchRawData(url_com,params_com)
    raw_con = checkDataRaw(raw_data_consumption)    
    CheckForMissingStates(raw_con)
    raw_con.to_csv('raw_con.csv', index=False)
    return raw_data_consumption

def requestPlantGenerationData(token):
    total_rows = 410564
    more_rows = True
    url_plant = "https://api.eia.gov/v2/electricity/facility-fuel/data/"
    params_plant = {
        "api_key": token, 
        "frequency": "monthly",
        "data[]": ["generation", "gross-generation" ],
        "facets[state][]": ["AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "TN", "TX", "UT", "VA", "VT", "WA", "WI","WV", "WY", "IA", "KS", "NM", "SD"],
        "facets[fuelType][]": ["ALL", "COL", "DFO", "GEO", "HPS", "HYC", "MLG", "NG", "NUC", "OOG", "ORW", "OTH", "PC", "RFO","SUN", "WND", "WOC", "WOO", "WWW" ],
        "start": "2018-01",
        "end": "2018-12",
        "sort[0][column]": "state",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000,
    }

    while more_rows == True:
        raw_data_power_plants = fetchRawData(url_plant,params_plant)
        non_empty_data = checkDataRaw(raw_data_power_plants)
        if non_empty_data.empty:
            more_rows = False
            break
        file_path = "raw_data_power_plants.csv"
        # Check if it is a regular file
        if os.path.isfile(file_path):
            non_empty_data.to_csv('raw_data_power_plants.csv', mode='a', index=False, header=False)
        else: 
            non_empty_data.to_csv('raw_data_power_plants.csv', index=False)        
        params_plant["offset"] += 5000
        if params_plant["offset"] >= total_rows:
            more_rows = False
    print("---Fetched all rows for request---")
    data_frame = pd.read_csv('raw_data_power_plants.csv')
    CheckForMissingStates(data_frame)
    return data_frame

def Main():
    load_dotenv()
    token = os.getenv("API_TOKEN")

    # clear the old file on start up 
    file_path = "raw_data_power_plants.csv"
    if os.path.isfile(file_path):
        os.remove(file_path)
        print("File deleted successfully.")
    else:
        print("The file does not exist.")

    raw_data_state = requestStateData(token)
    raw_data_consumption = requestStateConsumptionData(token)
    raw_data_power_plants = requestPlantGenerationData(token)
    # make all the data fetch functions check their own data!
    # then have it send it to main for procesing
    refined_data = refineData(raw_data_state, raw_data_consumption, raw_data_power_plants)
    
    
    
    # refined_data = refineData(raw_data_generation,raw_data_consumption)
    # print(refined_data)
    # checkDataClean(refined_data)
    

Main()