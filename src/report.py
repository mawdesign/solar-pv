import os
import sys
from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.pagesizes import A4

# Ensure the 'templates' directory can be imported securely regardless of where the script is run from
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from templates.report_layout import get_report_story

def generate_pdf_report(results_dict: dict, plot_image_path: str, output_pdf_path: str = "Solar_Assessment_Report.pdf") -> str:
    """
    Takes the output dictionary from the engine, builds ReportLab elements from the template layout,
    and generates a PDF report using ReportLab.
    """
    # Ensure absolute paths
    output_pdf_path = os.path.abspath(output_pdf_path)
    abs_image_path = os.path.abspath(plot_image_path)
    
    # Initialize the PDF document
    doc = SimpleDocTemplate(
        output_pdf_path, 
        pagesize=A4,
        rightMargin=50, 
        leftMargin=50,
        topMargin=50, 
        bottomMargin=50
    )
    
    # Get the layout elements (story) from the template script
    story = get_report_story(results_dict, abs_image_path)
    
    # Build and save the PDF
    doc.build(story)
    
    return output_pdf_path

if __name__ == "__main__":
    # Quick test to generate a dummy PDF report
    print("Testing PDF Generation...")
    
    # Create a dummy image first
    from visuals import generate_3d_surface_png
    import numpy as np
    dummy_data = [np.sin(i / 100.0) * 5 for i in range(8760)]
    img_path = generate_3d_surface_png(dummy_data, "temp_test_plot.png")
    
    # Dummy results dictionary matching the engine's output format
    dummy_results = {
        "inputs": {
            "latitude": -41.2865,
            "longitude": 174.7762,
            "azimuth": 0,
            "tilt": 30,
            "width": 5,
            "length": 2,
            "area_m2": 10,
            "panel_type": "Standard Monocrystalline (20%)",
            "stc_capacity_kw": 2.0
        },
        "metrics": {
            "annual_output_kwh": 3150.45,
            "max_hour_output_kw": 1.85,
            "seasonal_daily_profiles_kw": {
                "March Equinox": [0]*6 + [0.5, 1.0, 1.5, 1.8, 1.5, 1.0, 0.5] + [0]*11,
                "June Solstice": [0]*8 + [0.3, 0.8, 1.0, 0.8, 0.3] + [0]*11,
                "September Equinox": [0]*6 + [0.5, 1.0, 1.5, 1.8, 1.5, 1.0, 0.5] + [0]*11,
                "December Solstice": [0]*5 + [0.5, 1.2, 1.8, 2.0, 1.8, 1.2, 0.5] + [0]*12
            }
        }
    }
    
    out_pdf = generate_pdf_report(dummy_results, img_path, "Test_Report.pdf")
    print(f"Success! PDF Report generated at: {out_pdf}")