import json
import os
import requests
import pandas as pd
import numpy as np
import pvlib
from pvlib.pvsystem import PVSystem
from pvlib.location import Location
from pvlib.modelchain import ModelChain

# Use a recent non-leap year as our baseline standard year
BASELINE_YEAR = 2023

def load_panel_config(panel_name: str, config_path: str = "data/panels.json") -> dict:
    """Loads panel properties from the JSON configuration file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Panel configuration file not found at {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        panels = json.load(f)
        
    if panel_name not in panels:
        raise ValueError(f"Panel type '{panel_name}' not found in configuration.")
        
    return panels[panel_name]

def fetch_weather_data(lat: float, lon: float) -> pd.DataFrame:
    """
    Fetches hourly historical solar radiation and weather data from Open-Meteo 
    for the baseline year.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{BASELINE_YEAR}-01-01",
        "end_date": f"{BASELINE_YEAR}-12-31",
        "hourly": "shortwave_radiation,direct_normal_irradiance,diffuse_radiation,temperature_2m,wind_speed_10m",
        "timezone": "UTC"
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    
    # Load into pandas dataframe
    df = pd.DataFrame(data["hourly"])
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    # Rename columns to match what pvlib expects
    df.rename(columns={
        "shortwave_radiation": "ghi",
        "direct_normal_irradiance": "dni",
        "diffuse_radiation": "dhi",
        "temperature_2m": "temp_air",
        "wind_speed_10m": "wind_speed"
    }, inplace=True)
    
    return df

def extract_seasonal_profiles(hourly_power_series: pd.Series) -> dict:
    """Extracts 24-hour profiles for specific seasonal milestone dates."""
    dates = {
        "March Equinox": f"{BASELINE_YEAR}-03-21",
        "June Solstice": f"{BASELINE_YEAR}-06-21",
        "September Equinox": f"{BASELINE_YEAR}-09-21",
        "December Solstice": f"{BASELINE_YEAR}-12-21"
    }
    
    profiles = {}
    for name, date_str in dates.items():
        # Extract the 24 hours for the given date, returning as a list of floats (kW)
        day_data = hourly_power_series.loc[date_str]
        profiles[name] = [float(val) / 1000.0 for val in day_data.values]
        
    return profiles

def run_simulation(lat: float, lon: float, azimuth: float, tilt: float, 
                   width: float, length: float, panel_name: str) -> dict:
    """
    Main function to run the PV simulation.
    Returns a dictionary of all required metrics and the raw series.
    """
    # 1. Fetch panel specs and calculate system capacity
    panel_specs = load_panel_config(panel_name)
    area_m2 = width * length
    # Standard Test Conditions (STC) irradiance is 1000 W/m^2
    # Capacity in Watts = Area * 1000 * efficiency
    capacity_w = area_m2 * 1000 * panel_specs['efficiency']
    
    # 2. Fetch baseline weather data
    weather_df = fetch_weather_data(lat, lon)
    
    # 3. Setup pvlib Location and PVSystem
    location = Location(lat, lon, tz='UTC')
    
    # Using PVWatts models for simplified efficiency-based calculation
    system = PVSystem(
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        module_parameters={'pdc0': capacity_w, 'gamma_pdc': panel_specs['gamma_pdc']},
        inverter_parameters={'pdc0': capacity_w}, # Assume inverter matches array size
        temperature_model_parameters=pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
    )
    
    # 4. Build and run the ModelChain
    mc = ModelChain(
        system, 
        location, 
        aoi_model='no_loss', 
        spectral_model='no_loss', 
        dc_model='pvwatts', 
        ac_model='pvwatts'
    )
    
    mc.run_model(weather_df)
    
    # The result is in Watts. Convert to a Pandas Series.
    ac_power_watts = mc.results.ac
    # Some older pvlib versions return a tuple or frame, ensure it's a series and fill NaNs
    if isinstance(ac_power_watts, pd.DataFrame):
        ac_power_watts = ac_power_watts.iloc[:, 0]
    ac_power_watts = ac_power_watts.fillna(0).clip(lower=0) 
    
    # 5. Extract requested metrics
    annual_output_kwh = float(ac_power_watts.sum() / 1000.0)
    max_hour_kw = float(ac_power_watts.max() / 1000.0)
    seasonal_profiles = extract_seasonal_profiles(ac_power_watts)
    
    # 6. Format raw data for 3D Graph generation
    # Extract the Z-axis (power in kW) as an array for visuals/storage
    hourly_kw_list = (ac_power_watts / 1000.0).tolist()
    
    return {
        "inputs": {
            "latitude": lat,
            "longitude": lon,
            "azimuth": azimuth,
            "tilt": tilt,
            "width": width,
            "length": length,
            "area_m2": area_m2,
            "panel_type": panel_name,
            "stc_capacity_kw": capacity_w / 1000.0
        },
        "metrics": {
            "annual_output_kwh": annual_output_kwh,
            "max_hour_output_kw": max_hour_kw,
            "seasonal_daily_profiles_kw": seasonal_profiles
        },
        "raw_hourly_kw": hourly_kw_list # Array of 8760 floats
    }

if __name__ == "__main__":
    # Quick test execution
    print("Testing Engine Configuration...")
    try:
        # Wellington coordinates: 41.2865 S, 174.7762 E
        # Facing North (Azimuth 0 in Southern Hemisphere), Tilt 30
        res = run_simulation(-41.2865, 174.7762, 0, 30, 5, 2, "Standard Monocrystalline (20%)")
        print(f"Success! Calculated Annual Output: {res['metrics']['annual_output_kwh']:.2f} kWh")
        print(f"Max Peak Hour: {res['metrics']['max_hour_output_kw']:.2f} kW")
        print(f"Data points generated: {len(res['raw_hourly_kw'])}")
    except Exception as e:
        print(f"Error: {e}")
