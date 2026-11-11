import folium
import numpy as np
import geopandas as gpd
from branca.element import MacroElement
from jinja2 import Template
import http.server
import socketserver
import webbrowser
import threading
import time


CARTO_API_KEY = "cb1_4utm_1_da260965efee8931814afec9"

PIEZO_COLORS = {
    'piezometer': '#2471A3',     # Blue
    'river_sensor': '#27AE60',   # Green
}

class MapScale(MacroElement):
    def __init__(self):
        super().__init__()
        self._name = "MapScale"
        self._template = Template("""
        {% macro script(this, kwargs) %}
        L.control.scale({
            position: 'bottomright',
            metric: true,
            imperial: false,
            maxWidth: 150
        }).addTo({{ this._parent.get_name() }});
        {% endmacro %}
        """)

def map_sensors_orgeval(sensors_to_plot:gpd.GeoDataFrame, limite:gpd.GeoDataFrame, hydro:gpd.GeoDataFrame, location:list, 
                        zoom_start : int=13, output_path:str='map_bassin_lorgeval.html'):
    
    # 🔥 Modification pour occuper tout l'écran (Full page)
    map = folium.Map(location=location, zoom_start=zoom_start, tiles=None,
                   width="100%", height="100%", position="absolute", left="0%", top="0%",  
                   zoom_control=True, attribution_control=False)
    
    # ── Basemaps (CARTO & Satellite) ───────────────────────────────────────
    # 1. CARTO Voyager
    osm = folium.TileLayer(
        tiles=(
            "https://basemaps.cartocdn.com/"
            "rastertiles/voyager/{z}/{x}/{y}.png"
            f"?key={CARTO_API_KEY}"
        ),
        attr='&copy; OpenStreetMap contributors &copy; CARTO',
        name='CARTO Voyager',
        show=True,
        max_native_zoom=18,
        max_zoom=1000
    )
    osm.add_to(map)
    
    # 2. Esri World Imagery (Satellite)
    satellite = folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles &copy; Esri',
        name='Esri Satellite (Imagery)',
        show=False,
        max_zoom=19
    )
    satellite.add_to(map)
    
    # ── Watershed boundary ─────────────────────────────────────────────────
    limite_fg = folium.FeatureGroup(name='Limite du bassin versant', show=True)
    folium.GeoJson(
        limite.__geo_interface__,
        style_function=lambda _: {'fillOpacity': 0, 'color': '#111', 'weight': 2.5},
        tooltip=folium.GeoJsonTooltip(fields=['SBV_KM2'], aliases=['Area (km²) :']),
    ).add_to(limite_fg)
    limite_fg.add_to(map)

    # ── Hydrographic network ───────────────────────────────────────────────
    def hydro_style(feature):
        s = feature['properties'].get('strahler') or 1
        return {'color': '#1a6faf', 'weight': 0.7 + int(s) * 0.55, 'opacity': 0.9}

    hydro_fg = folium.FeatureGroup(name='Réseau hydrographique', show=True)
    folium.GeoJson(
        hydro.__geo_interface__,
        style_function=hydro_style,
        tooltip=folium.GeoJsonTooltip(fields=['NOM', 'strahler'], aliases=["Watercourse :", 'Strahler :']),
    ).add_to(hydro_fg)
    hydro_fg.add_to(map)

    # ── Piezometers ────────────────────────────────────────────────────────
    piezo_group = folium.FeatureGroup(name='Capteurs (Piézomètres)', show=True)

    for idx, row in sensors_to_plot.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        
        lat = row.geometry.y
        lon = row.geometry.x
        
        nom = row.get('LIBELLE', 'Inconnu')
        type_instr = str(row.get('TYPE_INSTR', '')).lower()
        
        # Déterminer la couleur (Vert pour rivière, Bleu pour piézo)
        if 'piezo' in type_instr:
            color = 'blue'
        else:
            color = 'green'

        # 🔥 Modification : Affichage du Nom ET du Type dans le popup
        texte_info = f"<b>{nom}</b><br>Type: {type_instr}"

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(texte_info, max_width=250),
            tooltip=texte_info,
            icon=folium.Icon(color=color, icon='tint')
        ).add_to(piezo_group)
    
    piezo_group.add_to(map)
    
    # 🔥 Ajout du contrôle des couches pour basculer entre CARTO et Satellite
    folium.LayerControl(position='topright', collapsed=False).add_to(map)
    
    map.add_child(MapScale())
    map.save(output_path)
    return map, location


# ── Load Data and Create the Map ──────────────────────────────────────────────
print("Loading shapefiles...")
limite = gpd.read_file("GIS/limites_avenelles.shp")
hydro = gpd.read_file("GIS/reseau_hydraugraphique.shp")
sensors = gpd.read_file("GIS/stations_water_temp_piezo.shp")

print("Converting coordinates to EPSG:4326...")
if limite.crs is not None and limite.crs.to_epsg() != 4326:
    limite = limite.to_crs(epsg=4326)
if hydro.crs is not None and hydro.crs.to_epsg() != 4326:
    hydro = hydro.to_crs(epsg=4326)
if sensors.crs is not None and sensors.crs.to_epsg() != 4326:
    sensors = sensors.to_crs(epsg=4326)

# On affiche TOUS les capteurs
sensors_subset = sensors 

if len(sensors_subset) > 0:
    initial_location = [sensors_subset.iloc[0].geometry.y, sensors_subset.iloc[0].geometry.x]
else:
    initial_location = [48.85, 3.15]

print("Generating map...")
map_obj, loc = map_sensors_orgeval(
    sensors_to_plot=sensors_subset,
    limite=limite,
    hydro=hydro,
    location=initial_location,
    zoom_start=12, 
    output_path='carte_capteurs.html'
)

print("Map generated successfully!")

# ── Run a Local Server to display the map ─────────────────────────────────────
PORT = 8000

def open_browser():
    time.sleep(1)
    webbrowser.open(f"http://localhost:{PORT}/carte_capteurs.html")

Handler = http.server.SimpleHTTPRequestHandler
threading.Thread(target=open_browser).start()

print(f"Map is running at: http://localhost:{PORT}/carte_capteurs.html")
print("Press Ctrl+C in the terminal to stop the server.")

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()