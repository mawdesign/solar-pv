from reportlab.platypus import Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

def get_report_story(data: dict, plot_image_path: str) -> list:
    """
    Builds and returns the sequence of ReportLab elements (the 'story')
    for the Solar PV Assessment PDF.
    """
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    h2_style = styles['Heading2']
    normal_style = styles['Normal']

    story = []

    # --- Title ---
    story.append(Paragraph("Solar PV Assessment Report", title_style))
    story.append(Spacer(1, 0.2 * inch))

    # --- Summary Box ---
    inputs = data.get('inputs', {})
    story.append(Paragraph(f"<b>Location:</b> {inputs.get('latitude')}, {inputs.get('longitude')}", normal_style))
    
    stc_capacity = round(inputs.get('stc_capacity_kw', 0), 2)
    story.append(Paragraph(f"<b>Panel Type:</b> {inputs.get('panel_type')} ({stc_capacity} kW STC Capacity)", normal_style))
    
    array_setup = f"<b>Array Setup:</b> {inputs.get('width')}m x {inputs.get('length')}m ({inputs.get('area_m2')}m²), Tilt: {inputs.get('tilt')}°, Azimuth: {inputs.get('azimuth')}°"
    story.append(Paragraph(array_setup, normal_style))
    story.append(Spacer(1, 0.3 * inch))

    # --- Generation Summary ---
    metrics = data.get('metrics', {})
    story.append(Paragraph("Generation Summary", h2_style))
    story.append(Spacer(1, 0.1 * inch))
    
    annual_out = round(metrics.get('annual_output_kwh', 0), 2)
    story.append(Paragraph(f"<b>Estimated Annual Output:</b> {annual_out} kWh", normal_style))
    
    peak_out = round(metrics.get('max_hour_output_kw', 0), 2)
    story.append(Paragraph(f"<b>Peak Hourly Output:</b> {peak_out} kW", normal_style))
    story.append(Spacer(1, 0.3 * inch))

    # --- Seasonal Peak Performance ---
    story.append(Paragraph("Seasonal Peak Performance", h2_style))
    story.append(Spacer(1, 0.1 * inch))
    
    table_data = [['Season / Milestone', 'Peak Output During Day (kW)']]
    for season, profile in metrics.get('seasonal_daily_profiles_kw', {}).items():
        peak = max(profile) if profile else 0
        table_data.append([season, f"{round(peak, 2)} kW"])

    # Style the table
    t = Table(table_data, colWidths=[2.5 * inch, 2.5 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4 * inch))

    # --- 3D Output Profile ---
    story.append(Paragraph("3D Output Profile", h2_style))
    story.append(Spacer(1, 0.1 * inch))
    
    try:
        # Constrain image size to roughly fit page width
        img = Image(plot_image_path, width=6*inch, height=4*inch)
        story.append(img)
    except Exception as e:
        story.append(Paragraph(f"<i>[Plot image could not be loaded: {e}]</i>", normal_style))

    return story