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
