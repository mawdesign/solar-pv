# Solar PV Power Calculator

A comprehensive tool to assess the potential of solar photovoltaic (PV) installations. This application fetches real-world meteorological data, calculates power generation based on panel specifications and array geometry, and produces detailed reports and 3D visualizations.

It is designed with a decoupled architecture to run as:

1.  A headless CLI / OpenClaw Agent Skill.
2.  A cross-platform desktop application (macOS/Windows).

## Features

-   **NASA POWER API Integration:** Fetches historical irradiance and meteorological data.
-   **TMY Generation:** Automatically averages the last 5 years of weather data to create a Typical Meteorological Year (TMY) baseline, smoothing out sharp real-world weather anomalies.
-   **Industry Standard Modeling:** Uses `pvlib-python` to calculate precise sun positioning, shading, and panel efficiency.
-   **3D Visualizations:** Generates annual generation surface plots (headless PNG and interactive Plotly).
-   **Automated PDF Reports:** Generates stylized summaries using `reportlab`.

## Setup

1.  Clone this repository.
2.  Ensure you have Python 3.10+ installed.
3.  Install the required dependencies:
    
    ```
    pip install -r requirements.txt
    ```
    
    _(Note: If you are behind a corporate firewall with SSL inspection, you may also need to run `pip install pip-system-certs` to allow Python to use your OS certificate store)._
    

## Usage

### 1\. Command Line Interface (CLI)

You can run the core calculator directly from the terminal. This is the primary interface used by the OpenClaw agent.

```
python src/cli.py --lat -41.2865 --lon 174.7762 --azimuth 0 --tilt 30 --width 5 --length 2 --panel "Standard Monocrystalline (20%)" --output-dir "reports"
```

This will output a JSON summary to the console, save the run to `data/history.jsonl`, and generate a PDF and PNG plot in the `reports` folder.

### 2\. Testing & Raw Data Export

To verify the multi-year averaged data and calculated output, you can export the hourly datasets directly to CSV for review in Excel:

```
python tests/raw_data.py
```

This will generate files like `raw_ghi.csv`, `raw_temp_air.csv`, and `calculated_generation_kw.csv` inside the `tests/export_results` directory.

## License

Creative Commons Zero v1.0 Universal (CC0 1.0)