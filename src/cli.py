import argparse
import json
import sys
import os

from engine import run_simulation
from visuals import generate_3d_surface_png
from report import generate_pdf_report
import storage

def main():
    parser = argparse.ArgumentParser(description="Solar PV Power Calculator CLI")
    parser.add_argument('--lat', type=float, required=True, help="Latitude")
    parser.add_argument('--lon', type=float, required=True, help="Longitude")
    parser.add_argument('--azimuth', type=float, required=True, help="Angle to sun (e.g., 180 for South, 0 for North)")
    parser.add_argument('--tilt', type=float, required=True, help="Angle from horizontal")
    parser.add_argument('--width', type=float, required=True, help="Width of the array (m)")
    parser.add_argument('--length', type=float, required=True, help="Length of the array (m)")
    parser.add_argument('--panel', type=str, required=True, help="Panel type name matching panels.json")
    parser.add_argument('--output-dir', type=str, default=".", help="Directory to save the PDF and PNG")

    args = parser.parse_args()

    try:
        # 1. Run Core Engine (which fetches NASA POWER data and calculates via pvlib)
        results = run_simulation(
            lat=args.lat,
            lon=args.lon,
            azimuth=args.azimuth,
            tilt=args.tilt,
            width=args.width,
            length=args.length,
            panel_name=args.panel
        )

        # 2. Extract Data
        inputs = results['inputs']
        metrics = results['metrics']
        hourly_data = results['raw_hourly_kw']

        # 3. Generate Visuals and Reports
        os.makedirs(args.output_dir, exist_ok=True)
        # Create safe filenames based on coordinates
        file_suffix = f"{str(args.lat).replace('.', '_')}_{str(args.lon).replace('.', '_')}"
        png_path = os.path.join(args.output_dir, f"solar_plot_{file_suffix}.png")
        pdf_path = os.path.join(args.output_dir, f"solar_report_{file_suffix}.pdf")

        png_abs = generate_3d_surface_png(hourly_data, png_path)
        pdf_abs = generate_pdf_report(results, png_abs, pdf_path)

        # 4. Save to Datastore (JSONL)
        storage.save_run(inputs, metrics)

        # 5. Output JSON for OpenClaw Agent
        output = {
            "status": "success",
            "metrics": metrics,
            "files": {
                "plot_png": png_abs,
                "report_pdf": pdf_abs
            }
        }
        # Print JSON to stdout so OpenClaw can easily parse it
        print(json.dumps(output, indent=2))

    except Exception as e:
        error_output = {
            "status": "error",
            "message": str(e)
        }
        # Print errors in standard JSON format as well
        print(json.dumps(error_output, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()