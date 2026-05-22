from datetime import datetime
import shutil
import pandas as pd

from src.config import (
    RUTA_XLSX_ORIGINAL,
    HOJA_ORIGEN,
    RUTA_PARQUET_DRIVE,
    RUTA_CSV_DRIVE,
    RUTA_INVALIDOS_DRIVE,
    RUTA_PARQUET_REPO,
    RUTA_CSV_REPO,
    RUTA_INVALIDOS_REPO,
    RUTA_CORRECCIONES,
    asegurar_directorios,
)
from src.etl_logic import cargar_correcciones, crear_df_app


def _copiar_si_existe(origen, destino):
    if origen.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)


def main():
    print("====================================")
    print("ETL TCU NIRIEN — INICIO")
    print("====================================")
    print(f"HOJA ORIGEN: {HOJA_ORIGEN}")
    print(f"EXCEL ORIGEN: {RUTA_XLSX_ORIGINAL}")

    asegurar_directorios()

    if not RUTA_XLSX_ORIGINAL.exists():
        raise FileNotFoundError(f"No encontré el archivo Excel: {RUTA_XLSX_ORIGINAL}")

    print(f"📥 Leyendo Excel origen: {RUTA_XLSX_ORIGINAL}")
    df_original = pd.read_excel(RUTA_XLSX_ORIGINAL, sheet_name=HOJA_ORIGEN, engine="openpyxl")
    print(f"✅ Filas leídas: {len(df_original):,}")

    correcciones = cargar_correcciones(RUTA_CORRECCIONES)
    print(f"📚 Correcciones cargadas: {len(correcciones)}")

    df_app = crear_df_app(
        df_original=df_original,
        correcciones=correcciones,
        ruta_invalidos=RUTA_INVALIDOS_DRIVE,
    )

    # Metadatos ETL
    fecha_etl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_app["__HOJA_ORIGEN__"] = HOJA_ORIGEN
    df_app["__FECHA_ETL__"] = fecha_etl
    df_app["__FILAS_ETL__"] = len(df_app)

    print(f"✅ Filas finales para app: {len(df_app):,}")
    print("Columnas finales:")
    print(df_app.columns.tolist())

    # =========================
    # Guardar fuente de verdad en Drive
    # =========================
    df_app.to_parquet(RUTA_PARQUET_DRIVE, index=False)
    print(f"💾 Parquet guardado en Drive: {RUTA_PARQUET_DRIVE}")

    df_app.to_csv(RUTA_CSV_DRIVE, index=False, encoding="utf-8-sig")
    print(f"💾 CSV guardado en Drive: {RUTA_CSV_DRIVE}")

    # =========================
    # Copiar espejo al repo para la app / deploy
    # =========================
    _copiar_si_existe(RUTA_PARQUET_DRIVE, RUTA_PARQUET_REPO)
    _copiar_si_existe(RUTA_CSV_DRIVE, RUTA_CSV_REPO)
    _copiar_si_existe(RUTA_INVALIDOS_DRIVE, RUTA_INVALIDOS_REPO)

    print(f"📦 Parquet copiado al repo: {RUTA_PARQUET_REPO}")
    print(f"📦 CSV copiado al repo: {RUTA_CSV_REPO}")
    if RUTA_INVALIDOS_DRIVE.exists():
        print(f"📦 Reporte de inválidos copiado al repo: {RUTA_INVALIDOS_REPO}")

    print("====================================")
    print("ETL TCU NIRIEN — FIN OK")
    print("====================================")


if __name__ == "__main__":
    main()
