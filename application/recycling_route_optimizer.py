
import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import math
from typing import List, Tuple, Dict
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="Recycling Route Optimizer",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #2E8B57;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2E8B57;
    }
    .route-info {
        background-color: #e8f5e8;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

class RouteOptimizer:
    """
    Vehicle Routing Problem solver using Nearest Neighbor and 2-Opt algorithms
    Based on Firdaus (2023) and Chege (2023) methodologies
    """

    def __init__(self):
        self.routes = []
        self.total_distance = 0
        self.total_value = 0

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate Haversine distance between two points
        Reference: Chege (2023) - Geospatial Route Optimization
        """
        R = 6371  # Earth's radius in kilometers

        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c

    def create_distance_matrix(self, locations: List[Tuple[float, float]]) -> np.ndarray:
        """
        Create distance matrix for all locations
        Implementation based on Firdaus (2023) VRP methodology
        """
        n = len(locations)
        matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i][j] = self.calculate_distance(
                        locations[i][0], locations[i][1],
                        locations[j][0], locations[j][1]
                    )

        return matrix

    def nearest_neighbor_tsp(self, distance_matrix: np.ndarray, start_idx: int = 0) -> List[int]:
        """
        Nearest Neighbor algorithm for TSP
        Reference: Firdaus (2023) - Heuristic Methods for VRP
        """
        n = len(distance_matrix)
        unvisited = set(range(n))
        current = start_idx
        route = [current]
        unvisited.remove(current)

        while unvisited:
            nearest = min(unvisited, key=lambda x: distance_matrix[current][x])
            route.append(nearest)
            unvisited.remove(nearest)
            current = nearest

        route.append(start_idx)  # Return to start
        return route

    def two_opt_improvement(self, route: List[int], distance_matrix: np.ndarray, 
                          max_iterations: int = 1000) -> List[int]:
        """
        2-Opt local search improvement
        Implementation based on Firdaus (2023) optimization techniques
        """
        best_route = route.copy()
        best_distance = self.calculate_route_distance(best_route, distance_matrix)

        for iteration in range(max_iterations):
            improved = False

            for i in range(1, len(route) - 2):
                for j in range(i + 1, len(route) - 1):
                    # Create new route by reversing segment between i and j
                    new_route = route[:i] + route[i:j+1][::-1] + route[j+1:]
                    new_distance = self.calculate_route_distance(new_route, distance_matrix)

                    if new_distance < best_distance:
                        best_route = new_route
                        best_distance = new_distance
                        route = new_route
                        improved = True
                        break

                if improved:
                    break

            if not improved:
                break

        return best_route

    def calculate_route_distance(self, route: List[int], distance_matrix: np.ndarray) -> float:
        """Calculate total distance for a given route"""
        total = 0
        for i in range(len(route) - 1):
            total += distance_matrix[route[i]][route[i + 1]]
        return total

    def optimize_weekly_routes(self, weekly_data: pd.DataFrame, depots: pd.DataFrame, 
                             prices: pd.DataFrame) -> Dict:
        """
        Optimize routes for weekly collection schedule
        Integrates VRP methodology with business constraints
        """
        results = {}

        for day in weekly_data['Day'].unique():
            day_data = weekly_data[weekly_data['Day'] == day].copy()

            if len(day_data) == 0:
                continue

            # Find best depot for this day's collections
            best_depot_idx, depot_info = self.select_optimal_depot(day_data, depots)

            # Create locations list (depot + collection points)
            locations = [(depot_info['Latitude'], depot_info['Longitude'])]
            locations.extend([(row['Latitude'], row['Longitude']) 
                            for _, row in day_data.iterrows()])

            # Create distance matrix
            dist_matrix = self.create_distance_matrix(locations)

            # Solve TSP
            initial_route = self.nearest_neighbor_tsp(dist_matrix, 0)
            optimized_route = self.two_opt_improvement(initial_route, dist_matrix)

            # Calculate metrics
            total_distance = self.calculate_route_distance(optimized_route, dist_matrix)
            total_weight = day_data['Estimated_Weight_kg'].sum()

            # Calculate revenue
            day_data_with_prices = day_data.merge(prices, on='Material', how='left')
            total_revenue = (day_data_with_prices['Estimated_Weight_kg'] * 
                           day_data_with_prices['Price_per_kg']).sum()

            results[day] = {
                'route': optimized_route,
                'locations': locations,
                'distance': total_distance,
                'weight': total_weight,
                'revenue': total_revenue,
                'depot': depot_info,
                'collections': day_data,
                'efficiency': total_revenue / total_distance if total_distance > 0 else 0
            }

        return results

    def select_optimal_depot(self, day_data: pd.DataFrame, depots: pd.DataFrame) -> Tuple[int, Dict]:
        """Select the most efficient depot for given collection points"""
        best_depot_idx = 0
        min_total_distance = float('inf')

        for idx, depot in depots.iterrows():
            total_dist = 0
            for _, collection in day_data.iterrows():
                dist = self.calculate_distance(
                    depot['Latitude'], depot['Longitude'],
                    collection['Latitude'], collection['Longitude']
                )
                total_dist += dist

            if total_dist < min_total_distance:
                min_total_distance = total_dist
                best_depot_idx = idx

        return best_depot_idx, depots.iloc[best_depot_idx].to_dict()

def load_data():
    """Load and validate data files"""
    try:
        weekly_routes = pd.read_csv('weekly_routes.csv')
        depot_locations = pd.read_csv('depot_locations.csv')
        material_prices = pd.read_csv('material_prices.csv')

        return weekly_routes, depot_locations, material_prices
    except FileNotFoundError as e:
        st.error(f"Data file not found: {e}")
        return None, None, None

def create_route_map(route_data: Dict, day: str) -> folium.Map:
    """
    Create interactive map showing optimized route
    Visualization approach based on Chege (2023) geospatial methods
    """
    if not route_data:
        return None

    # Calculate map center
    lats = [loc[0] for loc in route_data['locations']]
    lons = [loc[1] for loc in route_data['locations']]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    # Create map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    # Add depot marker
    depot_loc = route_data['locations'][0]
    folium.Marker(
        depot_loc,
        popup=f"Depot: {route_data['depot']['Depot']}",
        icon=folium.Icon(color='red', icon='home')
    ).add_to(m)

    # Add collection points
    route = route_data['route']
    collections = route_data['collections']

    for i, (_, collection) in enumerate(collections.iterrows()):
        folium.Marker(
            [collection['Latitude'], collection['Longitude']],
            popup=f"""
            <b>{collection['Location']}</b><br>
            Material: {collection['Material']}<br>
            Weight: {collection['Estimated_Weight_kg']} kg<br>
            Stop #{route.index(i+1) if i+1 in route else 'N/A'}
            """,
            icon=folium.Icon(color='green', icon='recycle')
        ).add_to(m)

    # Add route lines
    route_coords = [route_data['locations'][i] for i in route]
    folium.PolyLine(
        route_coords,
        weight=3,
        color='blue',
        opacity=0.8
    ).add_to(m)

    return m

def main():
    """Main Streamlit application"""

    # Header
    st.markdown('<h1 class="main-header">♻️ Recycling Route Optimizer</h1>', 
                unsafe_allow_html=True)

    st.markdown("""
    **Advanced Vehicle Routing System for Waste Collection Optimization**

    This application implements state-of-the-art routing algorithms based on:
    - Firdaus, A. Z. (2023). Solving Vehicle Routing Problems with Python & Heuristics Algorithm
    - Chege, S. (2023). How to Create a Geospatial Route Optimization with Python
    """)

    # Load data
    weekly_routes, depot_locations, material_prices = load_data()

    if weekly_routes is None:
        st.error("Unable to load required data files. Please ensure all CSV files are available.")
        return

    # Sidebar controls
    st.sidebar.header("🎛️ Optimization Controls")

    selected_days = st.sidebar.multiselect(
        "Select Days to Optimize",
        options=weekly_routes['Day'].unique(),
        default=weekly_routes['Day'].unique()
    )

    optimization_level = st.sidebar.selectbox(
        "Optimization Level",
        ["Basic (Nearest Neighbor)", "Advanced (2-Opt)", "Premium (Multi-iteration)"],
        index=1
    )

    show_analytics = st.sidebar.checkbox("Show Advanced Analytics", value=True)

    # Initialize optimizer
    optimizer = RouteOptimizer()

    # Filter data based on selection
    filtered_data = weekly_routes[weekly_routes['Day'].isin(selected_days)]

    if len(filtered_data) == 0:
        st.warning("No data available for selected days.")
        return

    # Run optimization
    with st.spinner("🔄 Optimizing routes..."):
        results = optimizer.optimize_weekly_routes(filtered_data, depot_locations, material_prices)

    # Display results
    if results:
        # Summary metrics
        st.header("📊 Optimization Summary")

        col1, col2, col3, col4 = st.columns(4)

        total_distance = sum(r['distance'] for r in results.values())
        total_revenue = sum(r['revenue'] for r in results.values())
        total_weight = sum(r['weight'] for r in results.values())
        avg_efficiency = np.mean([r['efficiency'] for r in results.values()])

        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h3>🛣️ Total Distance</h3>
                <h2>{total_distance:.1f} km</h2>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h3>💰 Total Revenue</h3>
                <h2>R {total_revenue:.2f}</h2>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <h3>⚖️ Total Weight</h3>
                <h2>{total_weight:.1f} kg</h2>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <h3>📈 Avg Efficiency</h3>
                <h2>{avg_efficiency:.2f}</h2>
            </div>
            """, unsafe_allow_html=True)

        # Daily route details
        st.header("🗓️ Daily Route Optimization")

        for day, data in results.items():
            with st.expander(f"📅 {day} - {data['distance']:.1f}km, R{data['revenue']:.2f}"):

                col1, col2 = st.columns([2, 1])

                with col1:
                    # Create and display map
                    route_map = create_route_map(data, day)
                    if route_map:
                        st_folium(route_map, width=700, height=400)

                with col2:
                    st.markdown(f"""
                    <div class="route-info">
                        <h4>Route Details</h4>
                        <p><strong>Depot:</strong> {data['depot']['Depot']}</p>
                        <p><strong>Collections:</strong> {len(data['collections'])}</p>
                        <p><strong>Distance:</strong> {data['distance']:.1f} km</p>
                        <p><strong>Weight:</strong> {data['weight']:.1f} kg</p>
                        <p><strong>Revenue:</strong> R {data['revenue']:.2f}</p>
                        <p><strong>Efficiency:</strong> {data['efficiency']:.2f}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Collection details
                    st.subheader("Collection Points")
                    route_order = data['route'][1:-1]  # Exclude depot start/end

                    for i, stop_idx in enumerate(route_order):
                        if stop_idx > 0:  # Skip depot
                            collection = data['collections'].iloc[stop_idx - 1]
                            st.write(f"{i+1}. **{collection['Location']}** - {collection['Material']} ({collection['Estimated_Weight_kg']}kg)")

        # Analytics section
        if show_analytics:
            st.header("📈 Advanced Analytics")

            # Daily comparison chart
            daily_metrics = pd.DataFrame([
                {
                    'Day': day,
                    'Distance (km)': data['distance'],
                    'Revenue (R)': data['revenue'],
                    'Weight (kg)': data['weight'],
                    'Efficiency': data['efficiency'],
                    'Collections': len(data['collections'])
                }
                for day, data in results.items()
            ])

            col1, col2 = st.columns(2)

            with col1:
                fig_distance = px.bar(
                    daily_metrics, 
                    x='Day', 
                    y='Distance (km)',
                    title='Daily Distance Comparison',
                    color='Distance (km)',
                    color_continuous_scale='Viridis'
                )
                st.plotly_chart(fig_distance, use_container_width=True)

            with col2:
                fig_revenue = px.bar(
                    daily_metrics, 
                    x='Day', 
                    y='Revenue (R)',
                    title='Daily Revenue Comparison',
                    color='Revenue (R)',
                    color_continuous_scale='Greens'
                )
                st.plotly_chart(fig_revenue, use_container_width=True)

            # Efficiency analysis
            fig_efficiency = px.scatter(
                daily_metrics,
                x='Distance (km)',
                y='Revenue (R)',
                size='Weight (kg)',
                color='Efficiency',
                hover_data=['Day', 'Collections'],
                title='Route Efficiency Analysis',
                color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig_efficiency, use_container_width=True)

            # Material type analysis
            material_summary = filtered_data.groupby('Material').agg({
                'Estimated_Weight_kg': 'sum',
                'Day': 'count'
            }).reset_index()
            material_summary = material_summary.merge(material_prices, on='Material')
            material_summary['Total_Value'] = (material_summary['Estimated_Weight_kg'] * 
                                             material_summary['Price_per_kg'])

            fig_materials = px.pie(
                material_summary,
                values='Total_Value',
                names='Material',
                title='Revenue Distribution by Material Type'
            )
            st.plotly_chart(fig_materials, use_container_width=True)

    # Footer
    st.markdown("---")
    st.markdown("""
    **References:**
    - Firdaus, A. Z. (2023). Solving Vehicle Routing Problems with Python & Heuristics Algorithm. *Medium*.
    - Chege, S. (2023). How to Create a Geospatial Route Optimization with Python, A Comprehensive Guide. *Tierra Insights*.

    **Algorithm Implementation:** Nearest Neighbor TSP with 2-Opt local search optimization
    """)

if __name__ == "__main__":
    main()
