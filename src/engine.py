import json
import os
import pandas as pd
import numpy as np
import pvlib
from pvlib.pvsystem import PVSystem
from pvlib.location import Location
from pvlib.modelchain import ModelChain

from get_data import fetch_nasa_power_data

def load_panel_config(panel_name: str, config_path: str = "data/panels.json") -> dict:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Panel configuration file not found at {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        panels = json.load(f)
    if panel_name not in panels:
        raise ValueError(f"Panel type '{panel_name}' not found in configuration.")
    return panels[panel_name]

def extract_seasonal_profiles(tmy_series: pd.Series) -> dict:
    tmy_year = tmy_series.index[0].year
    dates = {
        "March Equinox": f"{tmy_year}-03-21",
        "June Solstice": f"{tmy_year}-06-21",
        "September Equinox": f"{tmy_year}-09-21",
        "December Solstice": f"{tmy_year}-12-21"
    }
    profiles = {}
    for name, date_str in dates.items():
        day_data = tmy_series.loc[date_str]
        profiles[name] = [float(val) for val in day_data.values]
    return profiles

def run_simulation(lat: float, lon: float, azimuth: float, tilt: float, 
                   width: float, length: float, panel_name: str) -> dict:
    
    panel_specs = load_panel_config(panel_name)
    area_m2 = width * length
    capacity_w = area_m2 * 1000 * panel_specs['efficiency']
    
    # 1. Fetch the FULL 5-year weather dataset
    weather_df = fetch_nasa_power_data(lat, lon)
    
    # 2. Setup System & Run Simulation on full 5 years
    location = Location(lat, lon, tz='UTC')
    system = PVSystem(
        surface_tilt=tilt, surface_azimuth=azimuth,
        module_parameters={'pdc0': capacity_w, 'gamma_pdc': panel_specs['gamma_pdc']},
        inverter_parameters={'pdc0': capacity_w},
        temperature_model_parameters=pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
    )
    
    mc = ModelChain(system, location, aoi_model='no_loss', spectral_model='no_loss', dc_model='pvwatts', ac_model='pvwatts')
    mc.run_model(weather_df)
    
    # Convert results to kW
    ac_power_kw = mc.results.ac / 1000.0
    if isinstance(ac_power_kw, pd.DataFrame):
        ac_power_kw = ac_power_kw.iloc[:, 0]
    ac_power_kw = ac_power_kw.fillna(0).clip(lower=0)
    
    # --- 3. Full 5-Year Extreme Metrics (For Battery Planning) ---
    # Aggregate to daily total generation (kWh)
    daily_kwh = ac_power_kw.resample('D').sum()
    
    best_day_date = daily_kwh.idxmax()
    best_day_kwh = daily_kwh.max()
    worst_day_date = daily_kwh.idxmin()
    worst_day_kwh = daily_kwh.min()
    
    # Worst 3 Consecutive Days
    rolling_3d_kwh = daily_kwh.rolling(window=3).sum()
    worst_3d_end_date = rolling_3d_kwh.idxmin()
    worst_3d_start_date = worst_3d_end_date - pd.Timedelta(days=2)
    worst_3d_kwh = rolling_3d_kwh.min()
    
    # --- 4. TMY Generation & Averages ---
    # Monthly average by hour (12 months x 24 hours)
    monthly_hourly_avg = ac_power_kw.groupby([ac_power_kw.index.month, ac_power_kw.index.hour]).mean()
    monthly_hourly_profiles = {}
    for month in range(1, 13):
        if month in monthly_hourly_avg:
            monthly_hourly_profiles[f"Month_{month}"] = monthly_hourly_avg[month].tolist()

    # Drop leap days to build the standard 8760 TMY array
    tmy_kw = ac_power_kw[~((ac_power_kw.index.month == 2) & (ac_power_kw.index.day == 29))]
    tmy_kw_avg = tmy_kw.groupby([tmy_kw.index.month, tmy_kw.index.day, tmy_kw.index.hour]).mean()
    
    # Reindex to a dummy year (e.g., 2023) for standard graphing
    dummy_year = 2023
    tmy_kw_avg.index = pd.date_range(start=f"{dummy_year}-01-01 00:00:00", periods=8760, freq="h")
    
    return {
        "inputs": {
            "latitude": lat, "longitude": lon, "azimuth": azimuth, "tilt": tilt,
            "width": width, "length": length, "area_m2": area_m2,
            "panel_type": panel_name, "stc_capacity_kw": capacity_w / 1000.0
        },
        "metrics": {
            "annual_output_kwh": float(tmy_kw_avg.sum()),
            "max_hour_output_kw": float(tmy_kw_avg.max()),
            "extremes": {
                "best_day": {"date": best_day_date.strftime("%Y-%m-%d"), "kwh": float(best_day_kwh)},
                "worst_day": {"date": worst_day_date.strftime("%Y-%m-%d"), "kwh": float(worst_day_kwh)},
                "worst_3_consecutive_days": {
                    "start_date": worst_3d_start_date.strftime("%Y-%m-%d"),
                    "end_date": worst_3d_end_date.strftime("%Y-%m-%d"),
                    "total_kwh": float(worst_3d_kwh)
                }
            },
            "monthly_hourly_profiles_kw": monthly_hourly_profiles,
            "seasonal_daily_profiles_kw": extract_seasonal_profiles(tmy_kw_avg)
        },
        "raw_hourly_kw": tmy_kw_avg.tolist() # 8760 list of floats
    }