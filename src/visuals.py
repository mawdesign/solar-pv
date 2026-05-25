import os
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go

def _prepare_surface_data(hourly_kw_list: list):
    """
    Helper function to reshape 8760 hourly data points 
    into a 365 (days) x 24 (hours) grid.
    """
    # Ensure we only take the first 8760 hours (standard year) 
    # to avoid reshape errors on leap years
    data = np.array(hourly_kw_list[:8760])
    z_data = data.reshape((365, 24))
    
    x_hours = np.arange(24)
    y_days = np.arange(1, 366)
    
    return x_hours, y_days, z_data

def generate_3d_surface_png(hourly_kw_list: list, output_path: str = "output_3d_plot.png") -> str:
    """
    Generates a headless 3D surface plot using Matplotlib and saves it as a PNG.
    Useful for OpenClaw agent responses and PDF report embedding.
    """
    x_hours, y_days, z_data = _prepare_surface_data(hourly_kw_list)
    X, Y = np.meshgrid(x_hours, y_days)
    
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    
    # Plot the surface
    surf = ax.plot_surface(X, Y, z_data, cmap='viridis', edgecolor='none', alpha=0.9)
    
    ax.set_title('Annual Solar Generation Profile')
    ax.set_xlabel('Hour of Day (0-23)')
    ax.set_ylabel('Day of Year (1-365)')
    ax.set_zlabel('Power Output (kW)')
    
    fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10, label='kW')
    
    # Adjust viewing angle for better visibility
    ax.view_init(elev=30, azim=-45)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    
    return os.path.abspath(output_path)

def generate_3d_surface_plotly(hourly_kw_list: list) -> go.Figure:
    """
    Generates an interactive 3D surface plot using Plotly.
    This will be embedded in the Flet desktop UI.
    """
    x_hours, y_days, z_data = _prepare_surface_data(hourly_kw_list)
    
    fig = go.Figure(data=[go.Surface(z=z_data, x=x_hours, y=y_days, colorscale='Viridis')])
    
    fig.update_layout(
        title='Interactive Annual Solar Generation Profile',
        scene=dict(
            xaxis_title='Hour of Day',
            yaxis_title='Day of Year',
            zaxis_title='Power Output (kW)'
        ),
        margin=dict(l=0, r=0, b=0, t=40)
    )
    
    return fig

if __name__ == "__main__":
    # Quick test to generate a dummy plot
    print("Testing 3D graph generation...")
    dummy_data = [np.sin(i / 100.0) * 5 for i in range(8760)]
    out_file = generate_3d_surface_png(dummy_data, "test_plot.png")
    print(f"Success! Plot saved to {out_file}")