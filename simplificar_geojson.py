import geopandas as gpd

# =========================
# RUTAS
# =========================
ruta_entrada = "data/limitecantonal_5k_fixed.geojson"
ruta_salida = "data/limitecantonal_5k_lite.geojson"

# =========================
# CARGAR
# =========================
gdf = gpd.read_file(ruta_entrada)

print("Columnas disponibles:", list(gdf.columns))
print("Filas:", len(gdf))

# =========================
# CONSERVAR SOLO LO NECESARIO
# =========================
columnas_necesarias = [c for c in ["CANTÓN", "geometry"] if c in gdf.columns]
gdf = gdf[columnas_necesarias].copy()

# =========================
# SIMPLIFICAR GEOMETRÍA
# =========================
# Si deforma demasiado el mapa, baja a 0.001 o 0.0008
# Si sigue pesado, sube a 0.002 o 0.003
gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.0015, preserve_topology=True)

# =========================
# GUARDAR
# =========================
gdf.to_file(ruta_salida, driver="GeoJSON")

print(f"✅ Archivo simplificado guardado en: {ruta_salida}")