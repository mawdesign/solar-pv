import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import datetime

def fetch_nasa_power_data(lat: float, lon: float, end_year: int = None, num_years: int = 5) -> pd.DataFrame:
    """
    Fetches hourly historical solar radiation and weather data from the NASA POWER API,
    and averages it over the specified number of years to create a typical year.
    """
    if end_year is None:
        # Default to the last complete year
        end_year = datetime.date.today().year - 1
        
    start_year = end_year - num_years + 1

    url = "https://power.larc.nasa.gov/api/temporal/hourly/point"
    
    # Format dates as YYYYMMDD for NASA POWER
    start_date = f"{start_year}0101"
    end_date = f"{end_year}1231"
    
    # Parameters required for the pvlib model:
    # ALLSKY_SFC_SW_DWN: Global Horizontal Irradiance (GHI)
    # ALLSKY_SFC_SW_DNI: Direct Normal Irradiance (DNI)
    # ALLSKY_SFC_SW_DIFF: Diffuse Horizontal Irradiance (DHI)
    # T2M: Temperature at 2 Meters
    # WS10M: Wind Speed at 10 Meters
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI,ALLSKY_SFC_SW_DIFF,T2M,WS10M",
        "community": "RE", # Renewable Energy community
        "longitude": lon,
        "latitude": lat,
        "start": start_date,
        "end": end_date,
        "format": "JSON",
        "time": "UTC"
    }
    
    # Create a session with a retry strategy for network stability
    session = requests.Session()
    retry_strategy = Retry(
        total=5, 
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    try:
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Failed to fetch data from NASA POWER API. Details: {e}")
        
    data = response.json()
    
    # NASA POWER JSON structure nests the timeseries inside properties -> parameter
    if 'properties' not in data or 'parameter' not in data['properties']:
        raise ValueError("Unexpected response structure from NASA POWER API.")
        
    df = pd.DataFrame(data["properties"]["parameter"])
    
    # The index comes in as YYYYMMDDHH strings. Convert to datetime.
    df = df.reset_index()
    df = df.rename(columns={'index': 'time'})
    df['time'] = pd.to_datetime(df['time'], format='%Y%m%d%H')
    df.set_index('time', inplace=True)
    
    # Rename columns to match what pvlib expects
    df.rename(columns={
        "ALLSKY_SFC_SW_DWN": "ghi",
        "ALLSKY_SFC_SW_DNI": "dni",
        "ALLSKY_SFC_SW_DIFF": "dhi",
        "T2M": "temp_air",
        "WS10M": "wind_speed"
    }, inplace=True)
    
    # Remove leap days (February 29th) to ensure uniform 8760 hours per year
    df = df[~((df.index.month == 2) & (df.index.day == 29))]
    
    # NASA POWER uses -999.0 as a fill value for missing/invalid data.
    # Replace these with NaN, then appropriately fill/interpolate.
    df.replace(-999.0, pd.NA, inplace=True)
    
    df['ghi'] = df['ghi'].fillna(0.0)
    df['dni'] = df['dni'].fillna(0.0)
    df['dhi'] = df['dhi'].fillna(0.0)
    df['temp_air'] = df['temp_air'].interpolate(method='linear').fillna(15.0) 
    df['wind_speed'] = df['wind_speed'].interpolate(method='linear').fillna(0.0)
    
    # Average the data across the multiple years
    df_avg = df.groupby([df.index.month, df.index.day, df.index.hour]).mean()
    
    # Reconstruct a dummy datetime index for a standard non-leap year (e.g., 2023)
    # pvlib requires a valid datetime index to calculate solar positions
    df_avg.index = pd.date_range(start=f"{end_year}-01-01 00:00:00", periods=8760, freq="h")
    
    return df_avg

if __name__ == "__main__":
    # Quick test execution for data fetching
    print("Testing NASA POWER API Fetch (5-Year Average)...")
    test_df = fetch_nasa_power_data(-41.2865, 174.7762)
    print(f"Success! Fetched {len(test_df)} rows of averaged data.")
    print(test_df.head())