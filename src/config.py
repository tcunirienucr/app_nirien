from pathlib import Path

# =====================================================
# CONFIG CENTRALIZADA DEL PROYECTO
# =====================================================
# Cambia SOLO estas dos rutas si algún día se mueve el proyecto.

# Carpeta persistente en Google Drive donde se guardan los artefactos ETL.
DRIVE_AUX_DIR = Path(
    r"G:\Mi unidad\Logistica y administración\Datos para información interactiva"
)

# Archivo Excel original sincronizado desde Google Drive.
RUTA_XLSX_ORIGINAL = Path(
    r"G:\Mi unidad\Logistica y administración\Datos para información interactiva\tcunirien_basetotal.xlsx"
)

# Hoja origen actual del Excel.
HOJA_ORIGEN = "junio2026v1"

# =====================================================
# RUTAS DEL REPO
# =====================================================
# Directorio raíz del proyecto (un nivel arriba de src/)
BASE_DIR = Path(__file__).resolve().parent.parent
REPO_DATA_DIR = BASE_DIR / "data"

# =====================================================
# ARTEFACTOS ETL: FUENTE DE VERDAD EN DRIVE
# =====================================================
RUTA_PARQUET_DRIVE = DRIVE_AUX_DIR / "mapa_latest.parquet"
RUTA_CSV_DRIVE = DRIVE_AUX_DIR / "mapa_latest.csv"
RUTA_INVALIDOS_DRIVE = DRIVE_AUX_DIR / "reporte_invalidos_canton.csv"

# =====================================================
# MIRROR PARA LA APP (EL REPO /data QUE LEE STREAMLIT/HF)
# =====================================================
RUTA_PARQUET_REPO = REPO_DATA_DIR / "mapa_latest.parquet"
RUTA_CSV_REPO = REPO_DATA_DIR / "mapa_latest.csv"
RUTA_INVALIDOS_REPO = REPO_DATA_DIR / "reporte_invalidos_canton.csv"

# Correcciones de cantones (se mantiene en el repo)
RUTA_CORRECCIONES = REPO_DATA_DIR / "correcciones_cantones.json"

# GeoJSON que usa la app
RUTA_MAPA_REPO = REPO_DATA_DIR / "limitecantonal_5k_lite.geojson"


def asegurar_directorios():
    """Crea carpetas necesarias si no existen."""
    DRIVE_AUX_DIR.mkdir(parents=True, exist_ok=True)
    REPO_DATA_DIR.mkdir(parents=True, exist_ok=True)
