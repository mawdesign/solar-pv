# Development Plan: Solar PV Power Calculator

## 1\. System Architecture & Tech Stack

To support both a desktop application (macOS/Windows) and an OpenClaw skill, the architecture must separate the core mathematical modeling from the user interface.

**Recommended Python Tech Stack:**

-   **Language:** Python 3.10+ (using `uv` or `pip` for dependency management)
-   **Core PV Engine:** `pvlib-python`. This is the industry-standard library for simulating the performance of photovoltaic energy systems. It handles solar positioning, irradiance tracking on tilted surfaces, and panel efficiency modeling.
-   **Meteorological Data:** `requests` fetching from the **NASA POWER API**. This provides robust, global solar radiation and meteorological datasets.
-   **Data Processing:** `pandas` and `numpy` for handling time-series data and generating a Typical Meteorological Year (TMY) by averaging 5 years of historical data.
-   **3D Graphing / Visualization:** \* `matplotlib`: For generating static, headless 3D surface plots (saved as PNGs for the OpenClaw skill and PDF).
    
    -   `plotly`: For rendering an interactive 3D graph within the desktop UI.
-   **PDF Generation:** `reportlab`. A pure Python library used to programmatically generate the PDF reports (chosen for compatibility with strict corporate firewalls, avoiding the need for GTK/WeasyPrint installations).
-   **Desktop UI Framework:** `Flet` (based on Flutter). It allows you to build native-feeling, modern desktop applications for macOS and Windows entirely in Python, and handles Plotly charts beautifully.
-   **Storage:** `JSONLines` (`.jsonl`) or a standard `.json` file. This acts as a simple, append-only text database for saving historical runs.

## 2\. Core Model Definition

The core engine uses `pvlib` combined with NASA POWER data to calculate a simulated typical year of solar generation (8760 hourly data points) for a specific location.

### 2.1 Inputs

1.  **Latitude & Longitude:** For solar positioning and fetching precise weather data.
2.  **Angle to Sun (Azimuth):** Compass direction the array faces (e.g., 180° for South in the Northern Hemisphere, 0° for North in the Southern Hemisphere).
3.  **Angle from Horizontal (Tilt):** The physical tilt of the array (e.g., 30°).
4.  **Width & Length:** Used to calculate total active array area (m2).
5.  **Panel Type:** Loaded from an external JSON configuration file (`data/panels.json`).

### 2.2 Processing (The `pvlib` + API pipeline)

1.  **Meteorological Data Fetching:** Query the NASA POWER API for the last 5 complete years of data.
2.  **TMY Generation:** Drop leap days and average the 5 years of hourly data (GHI, DNI, DHI, Temp, Wind Speed) into a single 8760-hour typical year profile to smooth out anomalous weather events.
3.  **System Setup:** Create a `pvlib.pvsystem.PVSystem` combining the area and panel efficiency parameters read from `panels.json`.
4.  **Simulation:** Run a `ModelChain` passing the averaged NASA irradiance data to yield hourly AC or DC power outputs over the year.

### 2.3 Outputs

-   **Annual Output (kWh):** Sum of the 8760 hourly outputs.
-   **Max Hour Output (kW):** The peak generation hour of the year.
-   **Daily Profiles:** 24-hour generation curves extracted for specific days (e.g., Summer Solstice, Winter Solstice, Vernal Equinox, Autumnal Equinox).
-   **3D Graph:** A surface plot (Z-axis: kW, Y-axis: Day, X-axis: Hour).

## 3\. OpenClaw Skill Integration

OpenClaw agents operate locally and interact with the filesystem. The skill relies on a standard CLI wrapper (`cli.py`).

**The OpenClaw Skill Definition (`SKILL.md`):**

```
---
name: pv-calculator
description: Calculates solar PV power output for a fixed-angle array and generates PDF reports and 3D graphs.
metadata.openclaw.requires.bins: ["python3"]
---
# Solar PV Calculator Skill

When the user asks to calculate solar generation, panel output, or PV viability:
1. Ensure you have the required inputs: Latitude, Longitude, Azimuth, Tilt, Width, Length, and Panel Type.
2. If missing, ask the user for them.
3. Use the `exec` tool to run the Python module:
   `python3 /path/to/app/src/cli.py --lat {lat} --lon {lon} --azimuth {az} --tilt {tilt} --width {w} --length {l} --panel "{panel}"`
4. The script will return a JSON object with the output stats and the file paths to the generated PNG image and PDF report.
5. Present the summary to the user and display the PNG image using the appropriate chat tool. Provide the path to the PDF.
```

## 4\. Project File Structure

```
pv-calculator/
├── .gitignore                  
├── README.md                   
├── requirements.txt            
├── docs/
│   └── pv_app_plan.md          # This development plan document
├── tests/
│   ├── raw_data.py             # Script to export raw hourly data to CSV grids
│   └── export_results/         # Directory for generated CSV test files
├── src/
│   ├── __init__.py
│   ├── get_data.py             # NASA POWER API fetcher and TMY averager
│   ├── engine.py               # Core pvlib simulation logic
│   ├── visuals.py              # Matplotlib and Plotly graphing functions
│   ├── report.py               # PDF generation utilizing ReportLab
│   ├── storage.py              # jsonl database read/write logic
│   ├── cli.py                  # Command-line interface wrapper for OpenClaw
│   ├── main_ui.py              # Flet desktop GUI application
│   └── templates/
│       └── report_layout.py    # ReportLab layout structures for the PDF
├── data/
│   ├── panels.json             # Pre-loaded panel specifications dictionary
│   └── history.jsonl           # Local datastore for saved runs
└── openclaw/
    └── SKILL.md                # OpenClaw skill definition metadata
```

## 5\. Development Steps

### Phase 1: Core Mathematical Engine & API Integration _(Completed)_

1.  Configured NASA POWER API client (`get_data.py`) with 5-year TMY averaging.
2.  Built `engine.py` using `pvlib` to convert irradiance into power output based on `panels.json` properties.
3.  Created test script (`raw_data.py`) to verify multi-year smoothing and hourly spreads.

### Phase 2: Visualization and Export _(Completed)_

1.  Created `visuals.py` for headless 3D Matplotlib generation and interactive Plotly graphs.
2.  Built `report_layout.py` and `report.py` to generate standalone PDF reports using `reportlab`.

### Phase 3: Data Storage & CLI _(Completed)_

1.  Created `storage.py` JSONLines datastore for preserving history.
2.  Created `cli.py` to orchestrate data fetching, simulation, exporting, and returning JSON.

### Phase 4: OpenClaw Skill Setup

1.  Copy the `openclaw/SKILL.md` to your local `~/.openclaw/workspace/skills/pv-calculator/` directory.
2.  Test the integration from your OpenClaw interface.

### Phase 5: Desktop User Interface (Flet)

1.  Create `src/main_ui.py` using `Flet`.
2.  Build a sidebar/form for Inputs (dropdowns that populate automatically from `data/panels.json`).
3.  Build a main viewing area with tabs:
    
    -   **Tab 1: Dashboard** (Metrics and daily profile line charts).
    -   **Tab 2: 3D Visualization** (Embed the Plotly 3D interactive graph).
    -   **Tab 3: History** (List view reading from the `.jsonl` datastore).
4.  Wire the UI to the engine and report generator.

### Phase 6: Packaging

1.  Use `PyInstaller` to package the application into standalone executables for macOS (`.app`) and Windows (`.exe`).