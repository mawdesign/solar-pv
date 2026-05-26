import numpy as np
from PIL import Image, ImageDraw
import math
import pvlib
import pandas as pd
import tempfile
import zipfile
import requests
import os
import json

try:
    import geopandas as gpd
    from shapely.geometry import box
    from pyproj import Geod
    import pdal
    from scipy.ndimage import maximum_filter1d
    LIDAR_AVAILABLE = True
except ImportError:
    LIDAR_AVAILABLE = False
    print("Note: Advanced LIDAR requires 'geopandas', 'shapely', 'pyproj', 'pdal', and 'scipy'.")
    print("Install via: conda install -c conda-forge pdal python-pdal geopandas pyproj scipy")


class SkyLayerGenerator:
    """
    A class to generate realistic sky backgrounds with sun glow and lens artifacts
    for solar path analysis charts.
    """
    def __init__(self, width=1200, height=600):
        self.width = width
        self.height = height
        # Default sky colors (RGB)
        self.zenith_color = np.array([20, 110, 200])   # Deep blue at the top
        self.horizon_color = np.array([160, 220, 255]) # Light cyan near horizon
        
    def generate_base_sky(self):
        """Creates a smooth linear gradient for the clear sky."""
        print("Generating base sky gradient...")
        sky = np.zeros((self.height, self.width, 3), dtype=np.float32)
        
        # Create a vertical gradient
        for y in range(self.height):
            # Non-linear progression to make the horizon scattering look more realistic
            t = (y / self.height) ** 1.5 
            sky[y, :, :] = self.zenith_color * (1 - t) + self.horizon_color * t
            
        return sky

    def add_sun_glow(self, sky_array, sun_pos):
        """Adds a realistic, mathematically calculated sun glow using exponential decay."""
        print(f"Adding sun glow at {sun_pos}...")
        sun_x, sun_y = sun_pos
        
        # Create grid of coordinates
        y_indices, x_indices = np.indices((self.height, self.width))
        
        # Calculate distance of every pixel to the sun center
        dist = np.sqrt((x_indices - sun_x)**2 + (y_indices - sun_y)**2)
        
        # 1. Broad atmospheric glow (soft, yellowish)
        glow_intensity = np.exp(-dist / 200.0)
        sun_color = np.array([255, 230, 150]) # Warm sunlight
        sky_array += glow_intensity[..., np.newaxis] * sun_color * 0.4
        
        # 2. Intense core (bright white)
        core_intensity = np.exp(-dist / 40.0)
        sky_array += core_intensity[..., np.newaxis] * np.array([255, 255, 255])
        
        # Clip values to valid RGB range [0, 255]
        sky_array = np.clip(sky_array, 0, 255).astype(np.uint8)
        return sky_array

    def _draw_hexagon(self, draw, center, radius, color):
        """Helper to draw a hexagon for aperture lens artifacts."""
        cx, cy = center
        points = []
        for i in range(6):
            # Rotate by 30 degrees (pi/6) so it points upwards
            angle = (math.pi / 3 * i) + (math.pi / 6)
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            points.append((x, y))
        draw.polygon(points, fill=color)

    def add_lens_flare(self, image, sun_pos):
        """Adds subtle lens flare artifacts along a specific axis."""
        print("Adding lens flare artifacts...")
        # Create a transparent overlay for drawing
        overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        sun_x, sun_y = sun_pos
        
        # Direct the flare towards the bottom-left third of the image
        target_x = self.width * 0.33
        target_y = self.height * 0.75
        
        # Vector from sun to the new target
        dx = target_x - sun_x
        dy = target_y - sun_y
        
        artifacts = [
            (0.3, 40, (255, 255, 255, 10), 'circle'),      
            (0.8, 20, (100, 255, 100, 25), 'hexagon'),     
            (1.2, 7,  (255, 100, 100, 40), 'circle'),      
            (1.5, 30, (100, 150, 255, 15), 'hexagon'),     
            (1.8, 60, (255, 255, 100, 8),  'circle')       
        ]
        
        for mult, size, color, shape in artifacts:
            pos_x = sun_x + (dx * mult)
            pos_y = sun_y + (dy * mult)
            
            if shape == 'circle':
                bbox = [pos_x - size, pos_y - size, pos_x + size, pos_y + size]
                draw.ellipse(bbox, fill=color)
            elif shape == 'hexagon':
                self._draw_hexagon(draw, (pos_x, pos_y), size, color)
                
        return Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')

    def generate(self, output_path="sky_layer.png", sun_elevation_pct=0.4):
        """Coordinates the full generation of the sky layer."""
        sun_x = self.width / 2 
        sun_y = self.height * sun_elevation_pct
        sun_pos = (sun_x, sun_y)

        sky_array = self.generate_base_sky()
        sky_array = self.add_sun_glow(sky_array, sun_pos)
        img = Image.fromarray(sky_array)
        img = self.add_lens_flare(img, sun_pos)
        
        img.save(output_path)
        print(f"Sky layer saved successfully to '{output_path}'")
        return img


class HorizonLayerGenerator:
    """
    A class to fetch horizon data via PVGIS and draw it onto the background image.
    It also exposes the raw horizon profile for PVlib shading analysis.
    """
    def __init__(self, width=1200, height=600):
        self.width = width
        self.height = height
        # Chart mapping parameters (approximating the reference image)
        self.center_azimuth = 0 # North (0 or 360) is centered for the Southern Hemisphere
        self.fov = 240 # Degrees total field of view (e.g., from 240 through 0 to 120)
        self.min_elevation = -5 # Degrees (y-axis bottom, allowing space below 0)
        self.max_elevation = 75 # Degrees (y-axis top)
        
    def fetch_opentopo_lidar(self, lat, lon, radius_m=1000, sensor_height_agl=2.0):
        """
        Identifies public datasets on OpenTopography, streams the point cloud using PDAL,
        and calculates the azimuth/elevation obstacles.
        """
        if not LIDAR_AVAILABLE:
            print("Lidar processing libraries not found. Skipping Lidar data.")
            return None
            
        print(f"Searching OpenTopography for Lidar data at lat={lat}, lon={lon} (radius {radius_m}m)...")
        
        d_lat = radius_m / 111111.0
        d_lon = radius_m / (111111.0 * math.cos(math.radians(lat)))
        minlon, maxlon = lon - d_lon, lon + d_lon
        minlat, maxlat = lat - d_lat, lat + d_lat

        url = "https://portal.opentopography.org/API/otCatalog"
        params = {
            "productFormat": "PointCloud",
            "minx": minlon, "miny": minlat,
            "maxx": maxlon, "maxy": maxlat,
            "detail": "true",
            "outputFormat": "json"
        }
        try:
            res = requests.get(url, params=params, timeout=10)
            data = res.json()
        except Exception as e:
            print(f"Failed to query OpenTopography API: {e}")
            return None
            
        if 'Datasets' not in data or len(data['Datasets']) == 0:
            print("No high-res lidar found in this area on OpenTopography.")
            return None

        dataset = data['Datasets'][0]['Dataset']
        alt_name = dataset.get('alternateName', None)
        if not alt_name:
            return None

        print(f"Found Lidar Dataset: {alt_name}")
        tile_url = f"https://opentopography.s3.sdsc.edu/pc-bulk/{alt_name}/{alt_name}_TileIndex.zip"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "index.zip")
            try:
                r = requests.get(tile_url, stream=True, timeout=15)
                with open(zip_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                with zipfile.ZipFile(zip_path, 'r') as z:
                    z.extractall(tmpdir)
            except Exception as e:
                print(f"Failed to download or extract Tile Index: {e}")
                return None
            
            shp_files = [f for f in os.listdir(tmpdir) if f.endswith('.shp')]
            if not shp_files:
                return None
                
            shp_path = os.path.join(tmpdir, shp_files[0])
            gdf = gpd.read_file(shp_path)
            
            if gdf.crs != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
                
            aoi = box(minlon, minlat, maxlon, maxlat)
            intersecting = gdf[gdf.intersects(aoi)]
            urls = intersecting["URL"].dropna().tolist()
            
            if not urls:
                print("No overlapping LAZ tiles found in the shapefile.")
                return None
                
            print(f"Found {len(urls)} intersecting LAZ tiles. Streaming data via PDAL...")
            
            stages = []
            for u in urls:
                stages.extend([
                    {"type": "readers.las", "filename": u},
                    {"type": "filters.crop", "bounds": {"minx": minlon, "miny": minlat, "maxx": maxlon, "maxy": maxlat}, "a_srs": "EPSG:4326"}
                ])
            stages.append({"type": "filters.merge"})
            stages.append({"type": "filters.reprojection", "out_srs": "EPSG:4326"})
            
            pipeline_json = {"pipeline": stages}
            try:
                pipeline = pdal.Pipeline(json.dumps(pipeline_json))
                pipeline.execute()
                arr = pipeline.arrays[0]
            except Exception as e:
                print(f"PDAL Pipeline failed: {e}")
                return None
            
            if len(arr) == 0:
                print("No points retrieved from the stream.")
                return None
                
            print(f"Streamed {len(arr)} points successfully. Calculating obstacles...")
            
            lons, lats, zs = arr['X'], arr['Y'], arr['Z']
            geod = Geod(ellps='WGS84')
            az, _, dist = geod.inv(np.full_like(lons, lon), np.full_like(lats, lat), lons, lats)
            az = (az + 360) % 360
            
            close_mask = dist < 10.0
            if np.any(close_mask):
                z_ground = np.percentile(zs[close_mask], 5)
            else:
                z_ground = np.min(zs)
                
            z_obs = z_ground + sensor_height_agl
            el = np.degrees(np.arctan2(zs - z_obs, dist))
            valid = dist > 1.0 
            
            df = pd.DataFrame({'azimuth': az[valid], 'distance': dist[valid], 'elevation': el[valid]})
            return df

    def fetch_pvgis_horizon(self, lat, lon):
        """Fetches the horizon profile from PVGIS for given coordinates."""
        print(f"Fetching PVGIS horizon data for lat={lat}, lon={lon}...")
        profile, meta = pvlib.iotools.get_pvgis_horizon(lat, lon)
        return profile

    def draw_horizon(self, image, horizon_profile, lidar_df=None):
        """
        Draws the PVGIS horizon silhouette and layers local LIDAR obstacles.
        Returns the updated image and the final combined horizon_profile Series.
        """
        print("Drawing horizon layer(s)...")
        overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        plot_azimuths = np.linspace(-self.fov/2, self.fov/2, 1000)
        profile_az = horizon_profile.index.values
        profile_el = horizon_profile.values
        rel_profile_az = (profile_az - self.center_azimuth + 180) % 360 - 180
        
        sort_idx = np.argsort(rel_profile_az)
        sorted_az = rel_profile_az[sort_idx]
        sorted_el = profile_el[sort_idx]
        
        skyline_so_far = np.interp(plot_azimuths, sorted_az, sorted_el)
        
        points = [(0, self.height)]
        for az, el in zip(plot_azimuths, skyline_so_far):
            x = (az - (-self.fov / 2)) / self.fov * self.width
            y = self.height - ((el - self.min_elevation) / (self.max_elevation - self.min_elevation) * self.height)
            points.append((x, y))
        points.append((self.width, self.height))
        draw.polygon(points, fill=(130, 130, 140, 255))
        
        if lidar_df is not None and not lidar_df.empty:
            print("Layering Local Lidar Obstructions...")
            bands = [
                (1000, 500, (110, 110, 115, 255)),
                (500, 250,  (90, 90, 95, 255)),
                (250, 100,  (70, 70, 75, 255)),
                (100, 50,   (50, 50, 55, 255)),
                (50, 0,     (35, 35, 40, 255))
            ]
            for d_max, d_min, color in bands:
                mask = (lidar_df['distance'] <= d_max) & (lidar_df['distance'] > d_min)
                band_df = lidar_df[mask]
                if band_df.empty:
                    continue
                band_rel_az = (band_df['azimuth'].values - self.center_azimuth + 180) % 360 - 180
                bin_idx = np.searchsorted(plot_azimuths, band_rel_az)
                valid_idx = (bin_idx >= 0) & (bin_idx < len(plot_azimuths))
                
                band_el = np.full(len(plot_azimuths), self.min_elevation)
                np.maximum.at(band_el, bin_idx[valid_idx], band_df['elevation'].values[valid_idx])
                
                if LIDAR_AVAILABLE:
                    band_el = maximum_filter1d(band_el, size=8) 
                
                new_skyline = np.maximum(skyline_so_far, band_el)
                
                points_top = []
                points_bot = []
                for az, el_top, el_bot in zip(plot_azimuths, new_skyline, skyline_so_far):
                    x = (az - (-self.fov / 2)) / self.fov * self.width
                    y_top = self.height - ((el_top - self.min_elevation) / (self.max_elevation - self.min_elevation) * self.height)
                    y_bot = self.height - ((el_bot - self.min_elevation) / (self.max_elevation - self.min_elevation) * self.height)
                    points_top.append((x, y_top))
                    points_bot.append((x, y_bot))
                    
                points_bot.reverse()
                draw.polygon(points_top + points_bot, fill=color)
                skyline_so_far = new_skyline
        
        real_azimuths = (plot_azimuths + self.center_azimuth) % 360
        final_profile = pd.Series(data=skyline_so_far, index=real_azimuths).sort_index()
            
        return Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB'), final_profile


class SVGLayerGenerator:
    """
    Combines the rendered PNG background with precise vector paths for the 
    horizon tracing, angle calibrations, bearing indicator, and solar tracking lines.
    """
    def __init__(self, width=1200, height=600):
        self.width = width
        self.height = height
        
        # Margin definitions to enclose the PNG with a white border for text
        self.margin_top = 60
        self.margin_bottom = 50
        self.margin_left = 50
        self.margin_right = 50
        
        self.svg_width = self.width + self.margin_left + self.margin_right
        self.svg_height = self.height + self.margin_top + self.margin_bottom
        
        self.center_azimuth = 0
        self.fov = 240
        self.min_elevation = -5
        self.max_elevation = 75
        
    def _az_el_to_xy(self, az, el):
        """Converts geographic azimuth/elevation to canvas X/Y coordinates."""
        rel_az = (az - self.center_azimuth + 180) % 360 - 180
        x = (rel_az - (-self.fov / 2)) / self.fov * self.width
        y = self.height - ((el - self.min_elevation) / (self.max_elevation - self.min_elevation) * self.height)
        return round(x, 2), round(y, 2)
        
    def _get_horizon_elevation(self, az, horizon_profile):
        """Safely interpolates horizon elevation for a specific azimuth wrapped to 0-360."""
        # Pandas series is indexed by azimuth [0-360]
        az = az % 360
        return np.interp(az, horizon_profile.index.values, horizon_profile.values)

    def generate_svg(self, project_name, tilt, bearing, lat, lon, bg_image_path, horizon_profile, seasons_data, output_path="solar_analysis.svg"):
        print("Generating final SVG overlay...")
        
        svg = []
        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.svg_width} {self.svg_height}" width="{self.svg_width}" height="{self.svg_height}">')
        
        # --- 0. White Background for Margins ---
        svg.append('  <rect width="100%" height="100%" fill="white" />')
        
        # --- 1. Top Margin Labels ---
        svg.append(f'  <text x="{self.svg_width/2}" y="{self.margin_top/2 + 6}" fill="black" font-family="sans-serif" font-size="18" text-anchor="middle" font-weight="bold">{project_name}</text>')
        svg.append(f'  <text x="{self.margin_left}" y="{self.margin_top/2 + 6}" fill="black" font-family="sans-serif" font-size="16">Lat: {lat:.4f}&#176;  Lon: {lon:.4f}&#176;</text>')
        svg.append(f'  <text x="{self.svg_width - self.margin_right}" y="{self.margin_top/2 + 6}" fill="black" font-family="sans-serif" font-size="16" text-anchor="end">Tilt: {tilt}&#176;   Bearing: {bearing}&#176;</text>')
        
        # --- 2. Translation Group for the Main Canvas ---
        # Everything inside this group is offset by the margins so local math still uses 0-1200 / 0-600
        svg.append(f'  <g transform="translate({self.margin_left}, {self.margin_top})">')
        
        # Defs & Sky Clip Path
        svg.append('    <defs>')
        svg.append('      <clipPath id="chart_clip">')
        svg.append(f'        <rect x="0" y="0" width="{self.width}" height="{self.height}" />')
        svg.append('      </clipPath>')
        svg.append('      <clipPath id="sky_clip">')
        clip_points = [f"0,0 {self.width},0"]
        for pixel_x in range(self.width, -1, -1):
            rel_az = (-self.fov / 2) + (pixel_x / self.width) * self.fov
            az = (rel_az + self.center_azimuth) % 360
            el = self._get_horizon_elevation(az, horizon_profile)
            x, y = self._az_el_to_xy(az, el)
            clip_points.append(f"{x},{y}")
        svg.append(f'        <polygon points="{" ".join(clip_points)}" />')
        svg.append('      </clipPath>')
        svg.append('    </defs>')
        
        # Background Image
        svg.append(f'    <image href="{bg_image_path}" x="0" y="0" width="{self.width}" height="{self.height}" />')
        
        # Horizon Trace (Crisp line tracing the tops of the hills, changed to black)
        horizon_trace_pts = []
        for pixel_x in range(0, self.width + 1):
            rel_az = (-self.fov / 2) + (pixel_x / self.width) * self.fov
            az = (rel_az + self.center_azimuth) % 360
            el = self._get_horizon_elevation(az, horizon_profile)
            x, y = self._az_el_to_xy(az, el)
            horizon_trace_pts.append(f"{x},{y}")
        svg.append(f'    <polyline points="{" ".join(horizon_trace_pts)}" fill="none" stroke="black" stroke-width="1.5" opacity="0.8" />')
        
        # Calibrations & Markings inside image
        _, zero_y = self._az_el_to_xy(0, 0)
        svg.append(f'    <line x1="0" y1="{zero_y}" x2="{self.width}" y2="{zero_y}" stroke="white" stroke-width="1" stroke-dasharray="5,5" opacity="0.6"/>')
        
        b_x, _ = self._az_el_to_xy(bearing, 0)
        svg.append(f'    <polygon points="{b_x},{zero_y+2} {b_x-6},{zero_y+12} {b_x+6},{zero_y+12}" fill="#FFFF00" stroke="black" stroke-width="0.5" />')
        
        # Elevation axes (Left Margin)
        for el_tick in [20, 40, 60]:
            _, y = self._az_el_to_xy(0, el_tick)
            svg.append(f'    <text x="-8" y="{y+4}" fill="black" font-family="sans-serif" font-size="12" text-anchor="end">{el_tick}&#176;</text>')
            svg.append(f'    <line x1="-5" y1="{y}" x2="0" y2="{y}" stroke="black" stroke-width="1" />')

        # Azimuth axes (Bottom Margin)
        for az_tick in range(0, 360, 30):
            rel_az = (az_tick - self.center_azimuth + 180) % 360 - 180
            if -self.fov/2 <= rel_az <= self.fov/2:
                x, _ = self._az_el_to_xy(az_tick, 0)
                svg.append(f'    <text x="{x}" y="{self.height + 20}" fill="black" font-family="sans-serif" font-size="12" text-anchor="middle">{az_tick}&#176;</text>')
                svg.append(f'    <line x1="{x}" y1="{self.height}" x2="{x}" y2="{self.height + 5}" stroke="black" stroke-width="1" />')

        # Sun Curves (Double layered for shading!)
        svg.append('    <g id="shaded_paths" clip-path="url(#chart_clip)">')
        for season, data in seasons_data.items():
            pts = []
            for az, el in data['path']:
                x, y = self._az_el_to_xy(az, el)
                pts.append(f"{x},{y}")
            svg.append(f'      <polyline points="{" ".join(pts)}" fill="none" stroke="{data["color_dark"]}" stroke-width="2.5" />')
        svg.append('    </g>')
        
        svg.append('    <g id="bright_paths" clip-path="url(#sky_clip)">')
        for season, data in seasons_data.items():
            pts = []
            for az, el in data['path']:
                x, y = self._az_el_to_xy(az, el)
                pts.append(f"{x},{y}")
            svg.append(f'      <polyline points="{" ".join(pts)}" fill="none" stroke="{data["color_light"]}" stroke-width="3.5" />')
        svg.append('    </g>')

        # Hourly Markers and Text
        svg.append('    <g id="hourly_markers" clip-path="url(#chart_clip)">')
        for season, data in seasons_data.items():
            for mark in data['markers']:
                az = mark['az']
                el = mark['el']
                time_str = mark['time']
                power = mark['power']
                
                # Filter entirely out-of-bounds dots below -5
                if el < 0:
                    continue
                    
                x, y = self._az_el_to_xy(az, el)
                color = data['color_light']
                
                horizon_el_at_az = self._get_horizon_elevation(az, horizon_profile)
                is_shaded = el < horizon_el_at_az
                
                if is_shaded:
                    svg.append(f'      <circle cx="{x}" cy="{y}" r="3" fill="{data["color_dark"]}" />')
                else:
                    svg.append(f'      <circle cx="{x}" cy="{y}" r="3" fill="{color}" />')
                
                text_col = data["color_dark"] if is_shaded else color
                svg.append(f'      <text x="{x}" y="{y+14}" fill="{text_col}" font-family="sans-serif" font-size="10" text-anchor="middle">{time_str}</text>')
                
                if not is_shaded:
                    svg.append(f'      <text x="{x}" y="{y-6}" fill="{color}" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">{power:.2f}</text>')

        svg.append('    </g>')
        
        svg.append('  </g>') # Closes the main translation group
        svg.append('</svg>')
        
        with open(output_path, 'w') as f:
            f.write("\n".join(svg))
            
        print(f"Final SVG saved successfully to '{output_path}'")


if __name__ == "__main__":
    # Parameters matching the reference image / location
    lat, lon = -41.3083, 174.8225  # Wellington, NZ
    project_name = "Park Road PV Analysis"
    array_tilt = 15
    array_bearing = 15 # Azimuth from North
    
    # Calculate optimal sun elevation percentage based on equinox noon
    # Ensures the sun's glow aligns with the peak of the equinox curve
    min_el = -5
    max_el = 75
    equinox_noon_el = 90 - abs(lat)
    sun_elev_pct = 1.0 - (equinox_noon_el - min_el) / (max_el - min_el)
    
    # --- 1. Background Layers ---
    sky_gen = SkyLayerGenerator(width=1200, height=600)
    base_image = sky_gen.generate("sky_background.png", sun_elevation_pct=sun_elev_pct)
    
    horizon_gen = HorizonLayerGenerator(width=1200, height=600)
    pvgis_profile = horizon_gen.fetch_pvgis_horizon(lat, lon)
    lidar_df = horizon_gen.fetch_opentopo_lidar(lat, lon, radius_m=1000, sensor_height_agl=2.0)
    combined_image, final_pvlib_profile = horizon_gen.draw_horizon(base_image, pvgis_profile, lidar_df)
    combined_image.save("sky_with_horizon.png")

    # --- 2. Solar Path Data Generation ---
    # We define 3 dates: Summer Solstice, Equinox, Winter Solstice for the Southern Hemisphere
    dates = {
        'Summer Solstice': ('2026-12-21', '#FFFF00', '#888800'), # Bright Yellow, Dark Yellow
        'Equinox':         ('2026-03-21', '#00FF00', '#006600'), # Bright Green, Dark Green
        'Winter Solstice': ('2026-06-21', '#FF6600', '#883300')  # Bright Orange, Dark Orange
    }
    
    seasons_data = {}
    for season_name, (date_str, col_light, col_dark) in dates.items():
        # High-res path for the smooth SVG line
        times_smooth = pd.date_range(f"{date_str} 00:00", f"{date_str} 23:59", freq='10min', tz='Pacific/Auckland')
        solpos_smooth = pvlib.solarposition.get_solarposition(times_smooth, lat, lon)
        # Filter above min_elevation
        valid_smooth = solpos_smooth[solpos_smooth['apparent_elevation'] > horizon_gen.min_elevation]
        
        path_coords = list(zip(valid_smooth['azimuth'], valid_smooth['apparent_elevation']))
        
        # Hourly markers for the data dots
        times_hourly = pd.date_range(f"{date_str} 00:00", f"{date_str} 23:59", freq='1h', tz='Pacific/Auckland')
        solpos_hourly = pvlib.solarposition.get_solarposition(times_hourly, lat, lon)
        valid_hourly = solpos_hourly[solpos_hourly['apparent_elevation'] > horizon_gen.min_elevation]
        
        markers = []
        for time_idx, row in valid_hourly.iterrows():
            az, el = row['azimuth'], row['apparent_elevation']
            # Dummy power generation algorithm (peaks at solar noon, depends on altitude)
            dummy_power = max(0, el * 0.08) 
            markers.append({
                'az': az,
                'el': el,
                'time': time_idx.strftime('%H'),
                'power': dummy_power
            })
            
        seasons_data[season_name] = {
            'color_light': col_light,
            'color_dark': col_dark,
            'path': path_coords,
            'markers': markers
        }

    # --- 3. Final SVG Generation ---
    svg_gen = SVGLayerGenerator(width=1200, height=600)
    svg_gen.generate_svg(
        project_name=project_name,
        tilt=array_tilt,
        bearing=array_bearing,
        lat=lat,
        lon=lon,
        bg_image_path="sky_with_horizon.png",
        horizon_profile=final_pvlib_profile,
        seasons_data=seasons_data,
        output_path="solar_analysis.svg"
    )