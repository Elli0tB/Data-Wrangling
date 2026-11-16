from dotenv import load_dotenv
import os
import sys
import requests
import time
import pandas as pd
import numpy as np
import logging

def fetchRawData(URL, params):
    #before fetching data sleep, so we dont overload the api
    raw_data_frame = pd.DataFrame()
    time.sleep(1)
    print(f"requesting data from: {URL}")
    #check the status for the request
    try: 
        request = requests.get(URL,params=params)
        request.raise_for_status()
        response = request.json().get("response")
    except requests.exceptions.HTTPError as err:
        print(f"Error status code {err.response.status_code}") 
        return pd.DataFrame()
    raw_data_frame = pd.DataFrame(response.get("data"))
    return raw_data_frame

def checkDataRaw(data):
    if data.empty:
        empty_frame = pd.DataFrame()
        return empty_frame
    
    #Check for empty rows
    logging.info("---Checking for missing values---" )
    rows_missing_some_data =data[data.isna().any(axis=1)]
    logging.debug(f"---{len(rows_missing_some_data)} rows were missing at least 1 coloums data---")

    #check for empty rows and see if whitespace was hiding anything
    logging.info("---Cheking for empty values with whitespace---")
    df_cleaned = data.replace(r'^\s*$', np.nan, regex=True)
    whitespace_empty_rows = data[df_cleaned.isna().all(axis=1)]
    logging.debug(f"---{len(whitespace_empty_rows)} rows were missing at least 1 coloums data and was hidden with white space---")

    #clear empty rows
    logging.info("---Clearing empty rows---")
    cleard_data =data.dropna(how='all')
    logging.debug("---Empty rows removed---")
    return cleard_data
    
def refineData(raw_data_state, raw_data_com, raw_data_pwr_plnt):
    if isinstance(raw_data_state , pd.DataFrame) == False:
        logging.error("ERROR: raw_state_data was not a pd dataframe")
        logging.critical("Quiting program, ERROR must be resolved")
        sys.exit()
    elif isinstance(raw_data_com , pd.DataFrame) == False:
        logging.error("ERROR: raw_consumption_data was not a pd dataframe")
        logging.critical("Quiting program, ERROR must be resolved")
        sys.exit()
    elif isinstance(raw_data_pwr_plnt , pd.DataFrame) == False:
        logging.error("ERROR: raw_power_plant_data was not a pd dataframe")
        logging.critical("Quiting program, ERROR must be resolved")
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
                                                  'total-disposition-units',
                                                  'missing_data_flag'
                                                ]) 
        #this is the end result table year,state,stateDescription,total-disposition
    
        raw_data_pwr_plnt = raw_data_pwr_plnt.drop(columns=['plantCode',
                              'fuel2002',
                              'fuel2002TypeDescription',
                              'primeMover',
                              'stateDescription',
                              'gross-generation',
                              'gross-generation-units',
                              'missing_data_flag'
                              ]) 
        #this is the end result table period,plantName,fuelType,fuelTypeDescription,state,generation,generation-units,
        #df = df[df['col_name'] != 'value'] this is a good way to drop  rows based off a val in a col

        

        # lets get a hold of the wasted power 
        raw_data_pwr_plnt['generation'] = pd.to_numeric(raw_data_pwr_plnt['generation'], errors='coerce')
        raw_data_pwr_plnt = raw_data_pwr_plnt.dropna(subset=['generation']).reset_index(drop=True)
        wasted = (raw_data_pwr_plnt[raw_data_pwr_plnt['generation'] < 0]
          .groupby(['state_id', 'year'], as_index=False)['generation']
          .sum()
          .rename(columns={'generation': 'wasted_power'}))
        
        # Step 1: best and worst plant per state
        best = (raw_data_pwr_plnt.loc[raw_data_pwr_plnt.groupby('state_id')['generation'].idxmax(), ['year','plantName','fuelType','fuelTypeDescription','state_id','generation','generation-units']]
           .rename(columns={'plantName' : 'best_plant', 'generation' : 'best_generation', 'fuelTypeDescription' : 'fuelTypeDescription_best',}))

        worst = (raw_data_pwr_plnt.loc[raw_data_pwr_plnt.groupby('state_id')['generation'].idxmin(), ['year','plantName','fuelType','fuelTypeDescription','state_id','generation','generation-units']]
            .rename(columns={'plantName': 'worst_plant', 'generation': 'worst_generation', 'fuelTypeDescription' : 'fuelTypeDescription_worst'}))
        
        # Step 2: merge everything on state
        final = (raw_data_state.merge(raw_data_com, on=['state_id', 'year'], how='left')
            .merge(best, on='state_id', how='left')
            .merge(worst, on='state_id', how='left')
            .merge(wasted, on=['state_id', 'year'], how='left'))
        
        final['missing_data_flag'] = final['missing_data_flag'].fillna(False).astype(bool)
        has_data = ~final['missing_data_flag']
        final.loc[has_data, 'wasted_power'] = final.loc[has_data, 'wasted_power'].fillna(0)
        
        column_map = {
            # old name in `final`       : new name in output
            "year"                      : 'Year',
            'state_id'                  : 'State-ID',
            'average-retail-price'      : 'Electricity-Price (¢/kWh)',
            'carbon-dioxide-lbs'        : 'Emisions-Intensity',
            'net-generation'            : 'Total-Generation (MWh)',
            'total-disposition'         : 'Total-Consumption (MWh)',
            'best_plant'                : 'Best-Plant', 
            'best_generation'           : 'Best-Plant-Generation',
            'fuelTypeDescription_best'  : 'Best-Plant-Type',
            'worst_plant'               : 'Worst-Plant',
            'worst_generation'          : 'Worst-Plant-Generation',
            'fuelTypeDescription_worst' : 'Worst-Plant-Type',
            'wasted_power'              : 'Wasted-Power',
            'missing_data_flag'         : 'Missing-Data-Flag'
        }
    
        refined = final[list(column_map)].rename(columns=column_map)
        position = refined.columns.get_loc('Total-Consumption (MWh)') + 1   # position right after this column
        refined.insert(position, 'Diffrence', pd.to_numeric(refined['Total-Generation (MWh)']) - pd.to_numeric(refined['Total-Consumption (MWh)']))

        refined = refined.round(2).sort_values('State-ID').reset_index(drop=True)
        refined.to_csv('Structured.csv', index=False)
        print(refined)
        print(len(refined))
        return refined 

def rankingData(refined_data):
    # what is the goal? 
    # take the refined data and make intresint tables like a ranking of the best power plants/states in order
    # lets make one for best plant, worst plant, worst emisions, highest difference, and maybe more? 
    
    # Best Plant Data
    Best_plant_ranking_data = refined_data.sort_values(by= 'Best-Plant-Generation', ascending=False)
    print("----- BEST PLANT DATA RANKED -----")
    print(Best_plant_ranking_data.head())
    time.sleep(5)
    print("----- MOVING ON TO NEXT RANKING -----")
    Best_plant_ranking_data.to_csv('csv_holder/Best_Plant_Ranking_Data.csv', index= False)

    #Worst Plant data
    Worst_plant_ranking_data = refined_data.sort_values(by= 'Worst-Plant-Generation', ascending=True)
    print("----- WORST PLANT DATA RANKED -----")
    print(Worst_plant_ranking_data.head())
    time.sleep(5)
    print("----- MOVING ON TO NEXT RANKING -----")
    Worst_plant_ranking_data.to_csv('csv_holder/Worst_Plant_Ranking_Data.csv', index= False)

    #Worst emissions data
    Worst_emissions_ranking_data = refined_data.sort_values(by= 'Emisions-Intensity', ascending=False)
    print("----- WORST EMISSIONS DATA RANKED -----")
    print(Worst_emissions_ranking_data.head())
    time.sleep(5)
    print("----- MOVING ON TO NEXT RANKING -----")
    Worst_emissions_ranking_data.to_csv('csv_holder/Emissions_Ranking_Data.csv', index= False)

    #Highest difference data
    Worst_difference_ranking_data = refined_data.sort_values(by= 'Diffrence', ascending=False)
    print("----- HIGHEST DIFFERENCE DATA RANKED -----")
    print(Worst_difference_ranking_data.head())
    time.sleep(5)
    print("----- MOVING ON TO NEXT RANKING -----")
    Worst_difference_ranking_data.to_csv('csv_holder/Difference_Ranking_Data.csv', index= False)

    Best_price_ranking_data = refined_data.sort_values(by= 'Electricity-Price (¢/kWh)', ascending=True)
    print("----- BEST PRICE DATA RANKED -----")
    print(Best_price_ranking_data.head())
    time.sleep(5)
    print("----- MOVING ON TO NEXT RANKING -----")
    Best_price_ranking_data.to_csv('csv_holder/Best_Price_Ranking_Data.csv', index= False)

    #Best State Overall
    overall = refined_data.copy()
    overall["Overall-Score"] = (
        overall["Best-Plant-Generation"].rank(ascending=False)
        + overall["Emisions-Intensity"].rank(ascending=True)
        + overall["Diffrence"].rank(ascending=False)
        + overall["Electricity-Price (¢/kWh)"].rank(ascending=False)
    ) / 4
    overall = overall.sort_values("Overall-Score")
    print("----- OVERALL BEST STATE RANKED -----")
    print(overall.head())
    overall.to_csv("csv_holder/Overall_Ranking_Data.csv", index=False)

    return overall

def CheckForMissingStates(data,year):
    #okay we need to be able to handle missing state data
    # i think the best way we can handle this is by reconstructing a row for a missing state with NaN's 
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
    elif "state" in data.columns:
        returned_states = set(data["state"].unique())
    else:
        logging.error("ERROR: Raw data did not have a stateID or a state identifer")
        logging.critical("Quiting program, ERROR must be resolved")
        sys.exit()

    missing = expected_states - returned_states
    data['missing_data_flag'] = False
    if missing:
        print("Missing States:", missing)
        logging.error("ERROR: State validation failed")
        print(f"The following states are excluded from the data: {missing}")
        logging.debug("Resolving missing states by adding NaN rows")
        tmp_list = []
        for state in missing:
            if "stateID" in data.columns:
                empty_state_row = {"period": year,"stateID": state, "missing_data_flag": True}
            else:
                empty_state_row = {"period": year, "state": state, "missing_data_flag": True}
            tmp_list.append(empty_state_row)
        tmp_df = pd.DataFrame(tmp_list)
        data = pd.concat([data, tmp_df], ignore_index=True)
        return data
    else:
        print("---State check passed---")
        return data

def requestStateData(token,year):
    url_gen = "https://api.eia.gov/v2/electricity/state-electricity-profiles/summary/data/"
    params_gen = {
        "api_key": token, 
        "frequency": "annual", 
        "data[]": [ "average-retail-price",  "average-retail-price-rank", "carbon-dioxide", "carbon-dioxide-lbs", "generation-elect-utils", "net-generation"],
        "facets[stateID][]": ["AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "TN", "TX", "UT", "VA", "VT", "WA", "WI","WV", "WY", "IA", "KS", "NM", "SD"],
        "start": f"{year}",
        "end": f"{year}",
        "sort[0][column]": "stateID",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000
    }
    raw_data_generation = fetchRawData(url_gen,params_gen)
    raw_gen = CheckForMissingStates(raw_data_generation,year)
    checked_raw_gen = checkDataRaw(raw_gen)
    checked_raw_gen.to_csv('raw_gen.csv', index=False)
    return checked_raw_gen
    
def requestStateConsumptionData(token,year):
    url_com = "https://api.eia.gov/v2/electricity/state-electricity-profiles/source-disposition/data/"
    params_com = {
        "api_key": token, 
        "frequency": "annual",
        "data[]": "total-disposition",
        "facets[state][]": ["AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "TN", "TX", "UT", "VA", "VT", "WA", "WI","WV", "WY", "IA", "KS", "NM", "SD"],
        "start": f"{year}",
        "end": f"{year}",
        "sort[0][column]": "state",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000,
    }
    raw_data_consumption = fetchRawData(url_com,params_com)
    raw_con = CheckForMissingStates(raw_data_consumption,year)
    checked_raw_con = checkDataRaw(raw_con)    
    checked_raw_con.to_csv('raw_con.csv', index=False)
    return checked_raw_con

def requestPlantGenerationData(token,year):
    file_path = "raw_data_power_plants.csv"
    more_rows = True
    url_plant = "https://api.eia.gov/v2/electricity/facility-fuel/data/"
    params_plant = {
        "api_key": token, 
        "frequency": "monthly",
        "data[]": ["generation", "gross-generation" ],
        "facets[state][]": ["AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "TN", "TX", "UT", "VA", "VT", "WA", "WI","WV", "WY", "IA", "KS", "NM", "SD"],
        "facets[fuelType][]": ["COL", "DFO", "GEO", "HPS", "HYC", "MLG", "NG", "NUC", "OOG", "ORW", "OTH", "PC", "RFO","SUN", "WND", "WOC", "WOO", "WWW" ],
        "start": f"{year}-01",
        "end": f"{year}-12",
        "sort[0][column]": "state",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000,
    }

    while more_rows == True:
        raw_data_power_plants = fetchRawData(url_plant,params_plant)
        checked_data = checkDataRaw(raw_data_power_plants)
        if checked_data.empty:
            more_rows = False
            break
        # Check if it needs to append to it or create the file
        if os.path.isfile(file_path):
            checked_data.to_csv('raw_data_power_plants.csv', mode='a', index=False, header=False)
        else: 
            checked_data.to_csv('raw_data_power_plants.csv', index=False)     
        # increment and do it again   
        params_plant["offset"] += 5000
    print("---Fetched all rows for request---")
    data_frame = pd.read_csv('raw_data_power_plants.csv')
    checked_raw_plant = CheckForMissingStates(data_frame,year)
    return checked_raw_plant

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

    # make all the data fetch functions check their own data!
    # then have it send it to main for procesing
    year = input("What year would you like to look at:")
    raw_data_state = requestStateData(token,year)
    raw_data_consumption = requestStateConsumptionData(token,year)
    raw_data_power_plants = requestPlantGenerationData(token,year)
    
    #process the data into somehting clean and useable
    refined_data = refineData(raw_data_state, raw_data_consumption, raw_data_power_plants)
    
    # compling rankings and other intresting tables out of the enriched and structerd data
    
    
    ranked_data = rankingData(refined_data)
    

    
Main()