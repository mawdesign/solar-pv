# Development Plan: Solar PV Power Calculator

## 1\. System Architecture & Tech Stack

To support both a desktop application (macOS/Windows) and an OpenClaw skill, the architecture must separate the core mathematical modeling from the user interface.

**Recommended Python Tech Stack:**

-   **Language:** Python 3.10+ (using `uv` or `pip` for dependency management)
-   **Core PV Engine:** `pvlib-python`. This is the industry-standard library for simulating the performance of photovoltaic energy systems. It handles solar positioning, irradiance tracking on tilted surfaces, and panel efficiency modeling.
-   **Meteorological Data:** `requests` or `httpx` for fetching real-world historical/forecast solar radiation data from the Open-Meteo API, eliminating the need to rely purely on idealized clear-sky models.
-   **Data Processing:** `pandas` and `numpy` for handling time-series data (8760 hours in a year).
-   **3D Graphing / Visualization:** \* `matplotlib`: For generating static, headless 3D surface plots (saved as PNGs for the OpenClaw skill and PDF).
    
    -   `plotly`: For rendering an interactive 3D graph within the desktop UI.
-   **PDF Generation:** `Jinja2` (for HTML templating) combined with `WeasyPrint` or `pdfkit` to convert the template and data into a polished PDF report.
-   **Desktop UI Framework:** `Flet` (based on Flutter). It allows you to build native-feeling, modern desktop applications for macOS and Windows entirely in Python, and handles Plotly charts beautifully.
-   **Storage:** `JSONLines` (`.jsonl`) or a standard `.json` file. This acts as a simple, append-only text database for saving historical runs.

## 2\. Core Model Definition

The core engine will use `pvlib` combined with Open-Meteo data to calculate a simulated year of solar generation (8760 hourly data points) for a specific location.

### 2.1 Inputs

1.  **Latitude & Longitude:** For solar positioning and fetching precise weather data.
2.  **Angle to Sun (Azimuth):** Compass direction the array faces (e.g., 180° for South in the Northern Hemisphere, 0° for North in the Southern Hemisphere).
3.  **Angle from Horizontal (Tilt):** The physical tilt of the array (e.g., 30°).
4.  **Width & Length:** Used to calculate total active array area (m2).
5.  **Panel Type:** Loaded from an external JSON configuration file (e.g., `panels.json`). This file will contain a dictionary of panel types mapping to efficiency ratings, temperature coefficients, and base parameters (e.g., "Standard Monocrystalline (20%)", "Premium SunPower (22%)"). This makes maintaining and updating the panel database much easier than hardcoding it.

### 2.2 Processing (The `pvlib` + API pipeline)

1.  **Meteorological Data Fetching (Open-Meteo):** Query the Open-Meteo Historical Weather API (ERA5 reanalysis dataset) for a standard baseline year. Fetch hourly `shortwave_radiation` (GHI), `direct_normal_irradiance` (DNI), and `diffuse_radiation` (DHI) for the provided Latitude and Longitude.
2.  **Location Setup:** Create a `pvlib.location.Location` object and align the Open-Meteo time-series data into a Pandas DataFrame index. _(Fallback: If the API fails or is offline, generate a fallback Clear Sky dataset using `pvlib`)_.
3.  **System Setup:** Create a `pvlib.pvsystem.PVSystem` using `FixedMount(surface_tilt, surface_azimuth)`, combining it with the area and panel efficiency parameters read from the `panels.json` file.
4.  **Simulation:** Run a `ModelChain` passing the real-world Open-Meteo irradiance data to yield hourly AC or DC power outputs over the year.

### 2.3 Outputs

-   **Annual Output (kWh):** Sum of the 8760 hourly outputs.
-   **Max Hour Output (kW):** The peak generation hour of the year.
-   **Daily Profiles:** 24-hour generation curves extracted for specific days (e.g., Summer Solstice, Winter Solstice, Vernal Equinox, Autumnal Equinox).
-   **3D Graph:** A surface plot where:
    
    -   **Z-axis:** Power Output (kW)
    -   **Y-axis:** Day of the Year (1-365)
    -   **X-axis:** Hour of the Day (0-23)

## 3\. OpenClaw Skill Integration

OpenClaw agents operate locally and interact with your filesystem and shell. To expose your app to OpenClaw, you will build a standard CLI interface and a `SKILL.md` file.

**1\. The CLI Wrapper (`cli.py`):** A simple argparse script that takes JSON string inputs or direct flags, runs the core engine, saves the PDF and 3D Image, and outputs a JSON response to `stdout`.

**2\. The OpenClaw Skill Definition (`SKILL.md`):** You will create a skill directory (e.g., `~/.openclaw/workspace/skills/pv-calculator/SKILL.md`) that tells the agent how to run your Python script.

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

For the GitHub repository, the following structure keeps the core logic separate from the user interfaces (CLI/Desktop) and data stores:

```
pv-calculator/
├── .gitignore                  # Ignore pycache, venv, generated PDFs/PNGs
├── README.md                   # Project overview and setup instructions
├── requirements.txt            # Python dependencies (or pyproject.toml if using uv)
├── docs/
│   └── pv_app_plan.md          # This development plan document
├── src/
│   ├── __init__.py
│   ├── engine.py               # Core pvlib logic and Open-Meteo API fetching
│   ├── visuals.py              # Matplotlib and Plotly graphing functions
│   ├── report.py               # PDF generation with Jinja2 and WeasyPrint
│   ├── storage.py              # jsonl database read/write logic
│   ├── cli.py                  # Command-line interface wrapper for OpenClaw
│   ├── main_ui.py              # Flet desktop GUI application
│   └── templates/
│       └── report_base.html    # HTML template for the PDF report
├── data/
│   ├── panels.json             # Pre-loaded panel specifications dictionary
│   └── history.jsonl           # Local datastore for saved runs
└── openclaw/
    └── SKILL.md                # OpenClaw skill definition metadata
```

## 5\. Development Steps

### Phase 1: Core Mathematical Engine & API Integration

1.  Initialize a Python environment and install `pvlib`, `pandas`, `numpy`, and `requests`.
2.  Create `src/engine.py` and a `data/panels.json` configuration file with your default array of panel specs.
3.  Write the API client function to fetch historical baseline solar irradiance (GHI, DNI, DHI) from the Open-Meteo API using the provided Lat/Lon.
4.  Implement the `pvlib` modeling chain to convert the Open-Meteo irradiance data into actual power output based on tilt, azimuth, area, and panel properties loaded from `panels.json`.
5.  Extract the required metrics (Annual, Max Hour, 4 Seasonal Daily Profiles).

### Phase 2: Visualization and Export

1.  Install `matplotlib`, `plotly`, `Jinja2`, `WeasyPrint`.
2.  Create `src/visuals.py`. Write a Matplotlib function to generate and save the 3D surface plot to a `.png` file. Write a Plotly equivalent for the UI.
3.  Create `src/report.py`. Design a basic HTML template (`src/templates/report_base.html`) with placeholders for the outputs and the 3D graph image.
4.  Implement a function that populates the HTML with the calculated data and compiles it to a PDF.

### Phase 3: Data Storage & CLI

1.  Create `src/storage.py`. Implement a simple JSONLines (`.jsonl`) append/read mechanism. Each run saves a dictionary of the inputs, timestamp, and high-level outputs to `data/history.jsonl`.
2.  Create `src/cli.py`. Map command-line arguments to the `engine.py` functions.
3.  Ensure the script saves the run to the datastore, generates the PNG and PDF, and prints a final JSON string to the terminal.

### Phase 4: OpenClaw Skill Setup

1.  Copy the `openclaw/SKILL.md` to your local `~/.openclaw/workspace/skills/pv-calculator/` directory.
2.  Ensure the skill references the absolute path to your repo's `cli.py` (or set it up relative to the workspace).
3.  Test the integration from your OpenClaw interface (Telegram/Web/CLI) by saying _"Calculate the solar output for a 10x5m array in Wellington..."_ and verifying the agent successfully runs the CLI and returns the image/JSON.

### Phase 5: Desktop User Interface (Flet)

1.  Create `src/main_ui.py` using `Flet`.
2.  Build a sidebar/form for Inputs (Text fields for dimensions/location, dropdowns that populate automatically from `data/panels.json`).
3.  Build a main viewing area with tabs:
    
    -   **Tab 1: Dashboard** (Big numbers for Annual Output and Peak Output, plus the 4 daily profile line charts).
    -   **Tab 2: 3D Visualization** (Embed the Plotly 3D interactive graph).
    -   **Tab 3: History** (A simple list view reading from the `.jsonl` datastore).
4.  Wire the "Calculate" button to the core engine, updating the UI state with the results upon completion. Provide an "Export PDF" button that triggers `report.py`.

### Phase 6: Packaging

1.  Use `PyInstaller` (which integrates well with Flet) to package the application into standalone executables for macOS (`.app`) and Windows (`.exe`).
2.  Document setup instructions for OpenClaw skill users in the `README.md`.
