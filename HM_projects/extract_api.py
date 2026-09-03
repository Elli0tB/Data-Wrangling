import requests
import time
import pandas as pd


url = "https://api.open-meteo.com/v1/forecast"
locations_lat_lng= {"Saint George": {"lat": 37.095169, "lng":-113.575974 },
                "Anchorage": {"lat":61.2174 , "lng":-149.8631 },
                "Layton": {"lat": 41.0602, "lng":-111.9711 },
                "London": {"lat": 51.5074, "lng":-0.1278 },
                "Tokyo": {"lat": 35.6895, "lng":139.6917 },
                } 
all_location_data = {}

for location_name in locations_lat_lng:
    #find the location
    latitude = locations_lat_lng[location_name]["lat"]
    longitude = locations_lat_lng[location_name]["lng"]
    params = {"hourly": ["temperature_2m", "wind_speed_10m"],
          "latitude":latitude,
          "longitude":longitude,
          }
    #create the request and sleep they way we dont just spam requests
    time.sleep(1)
    #send the request 
    print("requesting location", location_name)
    req = requests.get(url,params=params)
    #check the status for the request
    try: 
        error_code = req.raise_for_status()
    except:
        print(f"Error status code {error_code}") 
   
    resp = req.json()
    all_location_data[location_name] = resp

# process the hourly data for each location
all_locational_hourly_data = []
for location in all_location_data:
    response = all_location_data[location]
    hourly = response.get("hourly", {})
    locational_hourly_dataframe = pd.DataFrame({
        "date": pd.to_datetime(hourly.get("time", [])),
        "temperature_2m": hourly.get("temperature_2m"),
        "wind_speed_10m": hourly.get("wind_speed_10m"),
    })
    locational_hourly_dataframe["location"] = location
    locational_hourly_dataframe["latitude"] = response.get("latitude")
    locational_hourly_dataframe["longitude"] = response.get("longitude")
    all_locational_hourly_data.append(locational_hourly_dataframe)


    all_locational_hourly_data.append(locational_hourly_dataframe) 

all_locational_hourly_dataframe = pd.concat(all_locational_hourly_data, ignore_index=True)
print("\nHourly data\n", "----Head of Data----\n", all_locational_hourly_dataframe.head(),'\n', "----Tail of Data----\n", all_locational_hourly_dataframe.tail() )
all_locational_hourly_dataframe.to_csv('output.csv', index=False)
