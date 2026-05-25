import os
import sys
import pandas as pd

# Ensure the src directory is in the path so we can import our modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from get_data import fetch_nasa_power_data
from engine import run_simulation

def export_to_daily_hourly_csv(series: pd.Series, output_name: str, output_dir: str):
    """
    Takes a pandas Series with a DateTime index, pivots it to have dates as rows
    and hours (0-23) as columns, and saves it to a CSV.
    """
    df = series.to_frame(name='value')
    
    # Extract date and hour from the DateTime index
    df['date'] = df.index.date
    df['hour'] = df.index.hour
    
    # Pivot the data: rows = date, columns = hour, values = the actual data
    pivot_df = df.pivot(index='date', columns='hour', values='value')
    
    # Ensure column names are strictly 0 to 23
    pivot_df.columns = [str(c) for c in pivot_df.columns]
    
    # Save to CSV
    output_path = os.path.join(output_dir, f"{output_name}.csv")
    pivot_df.to_csv(output_path)
    print(f"Saved {output_name}.csv to {output_path}")

def main():
    # Test Parameters
    lat, lon = -41.2865, 174.7762  # Wellington
    panel_name = "Standard Monocrystalline (20%)"
    
    # Setup Output Directory
    output_dir = os.path.join(project_root, 'tests', 'export_results')
    os.makedirs(output_dir, exist_ok=True)
    
    print("Fetching raw data from NASA POWER (5-year average)...")
    raw_df = fetch_nasa_power_data(lat, lon)
    
    # Export each raw metric
    metrics_to_export = ['ghi', 'dni', 'dhi', 'temp_air', 'wind_speed']
    for metric in metrics_to_export:
        if metric in raw_df.columns:
            export_to_daily_hourly_csv(raw_df[metric], f"raw_{metric}", output_dir)
            
    print("\nRunning PV Simulation...")
    # Run the engine simulation to get the calculated kW results
    sim_results = run_simulation(
        lat=lat, lon=lon, azimuth=0, tilt=30, width=5, length=2, panel_name=panel_name
    )
    
    # The simulation returns a flat list of 8760 hourly floats.
    # We need to map this back to a DateTime index to reuse our pivot function.
    hourly_kw_list = sim_results['raw_hourly_kw']
    
    # We can reuse the index from raw_df which already has the 8760-hour standard dummy year
    calculated_series = pd.Series(hourly_kw_list, index=raw_df.index)
    export_to_daily_hourly_csv(calculated_series, "calculated_generation_kw", output_dir)

    print("\nData export complete! You can open these files in Excel to review the hourly spreads.")

if __name__ == "__main__":
    main()