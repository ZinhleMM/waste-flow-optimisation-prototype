"""
Configuration settings for the Recycling Route Optimizer
"""

# Application Settings
APP_TITLE = "Recycling Route Optimizer"
APP_ICON = "♻️"
PAGE_LAYOUT = "wide"

# Optimization Parameters
DEFAULT_MAX_ITERATIONS = 1000
OPTIMIZATION_LEVELS = {
    "Basic (Nearest Neighbor)": {"iterations": 0, "algorithm": "nearest_neighbor"},
    "Advanced (2-Opt)": {"iterations": 1000, "algorithm": "two_opt"},
    "Premium (Multi-iteration)": {"iterations": 5000, "algorithm": "two_opt_premium"}
}

# Map Settings
DEFAULT_ZOOM = 12
MAP_HEIGHT = 400
MAP_WIDTH = 700

# Color Scheme
COLORS = {
    "depot": "red",
    "collection": "green",
    "route": "blue",
    "primary": "#2E8B57",
    "secondary": "#f0f2f6",
    "success": "#e8f5e8"
}

# Business Rules
MIN_COLLECTION_WEIGHT = 5  # kg
MAX_ROUTE_DISTANCE = 100   # km
FUEL_COST_PER_KM = 2.50   # ZAR

# File Paths
DATA_FILES = {
    "routes": "weekly_routes.csv",
    "depots": "depot_locations.csv",
    "prices": "material_prices.csv"
}
