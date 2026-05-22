from pathlib import Path
import pandas as pd

from src.etl_logic import cargar_correcciones, crear_df_mapa


# =====================================================
# CONFIGURACIÓN: SOLO EDITA ESTA PARTE
# =====================================================

# Ruta al archivo Excel original que tú editas manualmente
RUTA_XLSX_ORIGINAL = Path(
    r"G:\Mi unidad\Logistica y administración\Datos para información interactiva\tcunirien_basetotal.xlsx"
)

# Nombre de hoja dentro del Excel.
# Si tu archivo tiene solo una hoja principal, puedes dejar 0.
HOJA_ORIGEN = "mayo2026v4"

# =====================================================
# RUTAS INTERNAS DEL REPO
# =====================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

RUTA_PARQUET = DATA_DIR / "mapa_latest.parquet"
RUTA_CSV = DATA_DIR / "mapa_latest.csv"
RUTA_CORRECCIONES = DATA_DIR / "correcciones_cantones.json"
RUTA_INVALIDOS = DATA_DIR / "reporte_invalidos_canton.csv"


def main():
    print("====================================")
    print("ETL TCU NIRIEN — INICIO")
    print("====================================")

    if not RUTA_XLSX_ORIGINAL.exists():
        raise FileNotFoundError(f"No encontré el archivo Excel: {RUTA_XLSX_ORIGINAL}")

    print(f"📥 Leyendo Excel origen: {RUTA_XLSX_ORIGINAL}")
    df_original = pd.read_excel(RUTA_XLSX_ORIGINAL, sheet_name=HOJA_ORIGEN, engine="openpyxl")

    print(f"✅ Filas leídas: {len(df_original):,}")

    correcciones = cargar_correcciones(RUTA_CORRECCIONES)
    print(f"📚 Correcciones cargadas: {len(correcciones)}")

    df_mapa = crear_df_mapa(
        df_original=df_original,
        correcciones=correcciones,
        ruta_invalidos=RUTA_INVALIDOS
    )

    from datetime import datetime

    df_mapa['__HOJA_ORIGEN__'] = HOJA_ORIGEN
    df_mapa['__FECHA_ETL__'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_mapa['__FILAS_ETL__'] = len(df_mapa)

    print(f"✅ Filas finales para mapa: {len(df_mapa):,}")

    # Guardar parquet
    df_mapa.to_parquet(RUTA_PARQUET, index=False)
    print(f"💾 Parquet guardado en: {RUTA_PARQUET}")

    # Guardar CSV de auditoría
    df_mapa.to_csv(RUTA_CSV, index=False, encoding="utf-8-sig")
    print(f"💾 CSV guardado en: {RUTA_CSV}")

    print("====================================")
    print("ETL TCU NIRIEN — FIN OK")
    print("====================================")


if __name__ == "__main__":
    main()

print("====================================")
print("HOJA QUE SE ESTÁ LEYENDO:")
print(HOJA_ORIGEN)
print("====================================")
