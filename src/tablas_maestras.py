import io
from typing import List, Optional, Tuple

import pandas as pd


# =========================
# CONSTANTES
# =========================

FILAS_PERMITIDAS = ["CANTON_FINAL", "AÑO", "CURSO", "CONVOCATORIA"]
COLUMNAS_PERMITIDAS = ["SEXO_MAESTRO", "CONDICION_CURSO"]

ORDEN_SEXO = ["Femenino", "Masculino", "NR", "Sin dato"]
ORDEN_CONDICION = ["Certificado", "Deserción", "Intermitente", "Sin condición"]


# =========================
# HELPERS DE COLUMNAS
# =========================

def _buscar_columna(df: pd.DataFrame, candidatos: List[str]) -> Optional[str]:
    for c in candidatos:
        if c in df.columns:
            return c
    return None


def _asegurar_columna(df: pd.DataFrame, candidatos: List[str], nombre_logico: str) -> str:
    col = _buscar_columna(df, candidatos)
    if col is None:
        raise KeyError(f"No encontré una columna para '{nombre_logico}'. Busqué: {candidatos}")
    return col


# =========================
# BASE MAESTRA
# =========================

def preparar_base_tabla_maestra(df: pd.DataFrame) -> pd.DataFrame:
    """
    Toma un DataFrame base y construye una versión estandarizada para la tabla maestra.

    Reglas:
    - Usa CANTON_FINAL como dimensión geográfica principal.
    - Construye SEXO_MAESTRO desde SEXO_NORMALIZADO o SEXO.
    - Construye CONDICION_CURSO usando CERTIFICADO / DESERCION / INTERMITENTE.
    - Construye BENEFICIARIO_MAESTRO para distinguir 'todos' vs 'beneficiarios'.
    """

    out = df.copy()

    # -------------------------
    # CANTON_FINAL
    # -------------------------
    col_canton = _asegurar_columna(
        out,
        ["CANTON_FINAL", "CANTON_DEF", "CANTON"],
        "CANTON_FINAL"
    )
    out["CANTON_FINAL"] = out[col_canton].fillna("Sin dato").astype(str).str.strip()
    out.loc[out["CANTON_FINAL"].isin(["", "nan", "None"]), "CANTON_FINAL"] = "Sin dato"

    # -------------------------
    # CURSO / CONVOCATORIA / AÑO
    # -------------------------
    col_curso = _asegurar_columna(out, ["CURSO", "curso"], "CURSO")
    col_conv = _asegurar_columna(out, ["CONVOCATORIA", "convocatoria"], "CONVOCATORIA")
    col_anio = _asegurar_columna(out, ["AÑO", "anio"], "AÑO")

    out["CURSO"] = out[col_curso].fillna("Sin dato").astype(str).str.strip()
    out["CONVOCATORIA"] = out[col_conv].fillna("Sin dato").astype(str).str.strip()

    # AÑO lo dejamos como string para no tener problemas en pivots/Excel
    out["AÑO"] = out[col_anio].astype(str).str.strip()
    out.loc[out["AÑO"].isin(["<NA>", "nan", "None", ""]), "AÑO"] = "Sin dato"

    # -------------------------
    # SEXO_MAESTRO
    # -------------------------
    col_sexo = _buscar_columna(out, ["SEXO_NORMALIZADO", "SEXO_FINAL", "SEXO"])
    if col_sexo is None:
        out["SEXO_MAESTRO"] = "Sin dato"
    else:
        out["SEXO_MAESTRO"] = out[col_sexo].fillna("Sin dato").astype(str).str.strip()
        out.loc[out["SEXO_MAESTRO"].isin(["", "nan", "None"]), "SEXO_MAESTRO"] = "Sin dato"

    # Normalizar a orden conocido
    out.loc[~out["SEXO_MAESTRO"].isin(ORDEN_SEXO), "SEXO_MAESTRO"] = "Sin dato"

    # -------------------------
    # BENEFICIARIO
    # -------------------------
    col_benef = _buscar_columna(out, ["BENEFICIARIO", "beneficiario"])
    if col_benef is None:
        out["BENEFICIARIO_MAESTRO"] = 0
    else:
        out["BENEFICIARIO_MAESTRO"] = pd.to_numeric(out[col_benef], errors="coerce").fillna(0).astype(int)

    # -------------------------
    # FLAGS DE CONDICIÓN
    # -------------------------
    col_cert = _buscar_columna(out, ["CERTIFICADO", "certificado"])
    col_des = _buscar_columna(out, ["DESERCION", "DESERCIÓN", "desercion"])
    col_int = _buscar_columna(out, ["INTERMITENTE", "intermitente"])

    out["CERTIFICADO_MAESTRO"] = pd.to_numeric(out[col_cert], errors="coerce").fillna(0).astype(int) if col_cert else 0
    out["DESERCION_MAESTRO"] = pd.to_numeric(out[col_des], errors="coerce").fillna(0).astype(int) if col_des else 0
    out["INTERMITENTE_MAESTRO"] = pd.to_numeric(out[col_int], errors="coerce").fillna(0).astype(int) if col_int else 0

    # -------------------------
    # CONDICION_CURSO (exclusiva)
    # -------------------------
    def resolver_condicion(row):
        if row["CERTIFICADO_MAESTRO"] == 1:
            return "Certificado"
        if row["DESERCION_MAESTRO"] == 1:
            return "Deserción"
        if row["INTERMITENTE_MAESTRO"] == 1:
            return "Intermitente"
        return "Sin condición"

    out["CONDICION_CURSO"] = out.apply(resolver_condicion, axis=1)

    # Asegurar orden conocido
    out["CONDICION_CURSO"] = pd.Categorical(
        out["CONDICION_CURSO"],
        categories=ORDEN_CONDICION,
        ordered=True
    )

    out["SEXO_MAESTRO"] = pd.Categorical(
        out["SEXO_MAESTRO"],
        categories=ORDEN_SEXO,
        ordered=True
    )

    return out


# =========================
# FILTRO DE UNIVERSO
# =========================

def filtrar_universo(df_base: pd.DataFrame, universo: str = "todos") -> pd.DataFrame:
    """
    universo:
    - 'todos'
    - 'beneficiarios'
    """
    universo = (universo or "todos").strip().lower()

    if universo == "beneficiarios":
        return df_base[df_base["BENEFICIARIO_MAESTRO"] == 1].copy()

    return df_base.copy()


# =========================
# TABLA MAESTRA
# =========================

def construir_tabla_maestra(
    df_base: pd.DataFrame,
    row_dims: List[str],
    col_dims: List[str],
    universo: str = "todos",
    incluir_total_fila: bool = True,
    incluir_total_general: bool = True
) -> pd.DataFrame:
    """
    Construye una tabla maestra tipo pivot con:
    - filas jerárquicas (row_dims)
    - columnas jerárquicas (col_dims)
    - conteo de registros
    """

    if not row_dims:
        raise ValueError("Debes seleccionar al menos una dimensión de filas.")
    if not col_dims:
        raise ValueError("Debes seleccionar al menos una dimensión de columnas.")

    for dim in row_dims:
        if dim not in FILAS_PERMITIDAS:
            raise ValueError(f"Dimensión de fila no permitida: {dim}")

    for dim in col_dims:
        if dim not in COLUMNAS_PERMITIDAS:
            raise ValueError(f"Dimensión de columna no permitida: {dim}")

    df = preparar_base_tabla_maestra(df_base)
    df = filtrar_universo(df, universo=universo)

    # Pivot
    tabla = pd.pivot_table(
        df,
        index=row_dims,
        columns=col_dims,
        values="CANTON_FINAL",   # cualquier columna no nula sirve para count
        aggfunc="count",
        fill_value=0,
        observed=False
    )

    # Asegurar orden de columnas si aplica
    # Solo reordenamos explícitamente cuando las dimensiones son exactamente las esperadas
    if col_dims == ["SEXO_MAESTRO", "CONDICION_CURSO"]:
        columnas_esperadas = pd.MultiIndex.from_product(
            [ORDEN_SEXO, ORDEN_CONDICION],
            names=col_dims
        )
        tabla = tabla.reindex(columns=columnas_esperadas, fill_value=0)

    # Total por fila
    if incluir_total_fila:
        tabla["TOTAL_POR_FILA"] = tabla.sum(axis=1)

    # Total general
    if incluir_total_general:
        total_general = tabla.sum(axis=0)
        total_general.name = tuple(["TOTAL_GENERAL"] * len(row_dims)) if len(row_dims) > 1 else "TOTAL_GENERAL"
        tabla = pd.concat([tabla, total_general.to_frame().T])

    return tabla


# =========================
# APLANAR PARA VISUALIZACIÓN / DESCARGA
# =========================

def aplanar_tabla_maestra(tabla: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte MultiIndex de columnas e índice en algo más amigable para ver/descargar.
    """
    out = tabla.copy()

    # Aplanar columnas
    if isinstance(out.columns, pd.MultiIndex):
        nuevas_cols = []
        for col in out.columns:
            if isinstance(col, tuple):
                nuevas_cols.append(" | ".join([str(x) for x in col if str(x) != ""]))
            else:
                nuevas_cols.append(str(col))
        out.columns = nuevas_cols
    else:
        out.columns = [str(c) for c in out.columns]

    # Reset index para dejar dimensiones visibles
    out = out.reset_index()

    return out


# =========================
# PANEL PLANO PARA EXPORTACIÓN
# =========================

def construir_panel_exportacion(
    df_base: pd.DataFrame,
    universo: str = "todos",
    columnas_extra: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Devuelve una base plana lista para exportar en la segunda hoja del Excel.
    """
    df = preparar_base_tabla_maestra(df_base)
    df = filtrar_universo(df, universo=universo)

    columnas_base = [
        "CANTON_FINAL",
        "AÑO",
        "CURSO",
        "CONVOCATORIA",
        "SEXO_MAESTRO",
        "CONDICION_CURSO",
        "BENEFICIARIO_MAESTRO",
        "CERTIFICADO_MAESTRO",
        "DESERCION_MAESTRO",
        "INTERMITENTE_MAESTRO"
    ]

    if columnas_extra:
        columnas_base = columnas_base + [c for c in columnas_extra if c in df.columns]

    columnas_base = [c for c in columnas_base if c in df.columns]

    return df[columnas_base].copy()


# =========================
# EXPORTAR A EXCEL
# =========================

def exportar_tabla_maestra_excel(
    tabla: pd.DataFrame,
    panel_df: pd.DataFrame
) -> bytes:
    """
    Genera un archivo Excel en memoria con:
    - Hoja 1: tabla maestra (aplanada)
    - Hoja 2: panel filtrado
    """
    output = io.BytesIO()

    tabla_export = aplanar_tabla_maestra(tabla)

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        tabla_export.to_excel(writer, sheet_name="TablaMaestra", index=False)
        panel_df.to_excel(writer, sheet_name="PanelFiltrado", index=False)

    return output.getvalue()


# =========================
# ETIQUETAS DISPONIBLES
# =========================

def obtener_etiquetas_disponibles(df_base: pd.DataFrame) -> dict:
    """
    Devuelve las etiquetas / dimensiones disponibles para poblar controles en la app.
    """
    df = preparar_base_tabla_maestra(df_base)

    return {
        "filas_permitidas": FILAS_PERMITIDAS,
        "columnas_permitidas": COLUMNAS_PERMITIDAS,
        "sexos_disponibles": sorted(df["SEXO_MAESTRO"].dropna().astype(str).unique().tolist()),
        "condiciones_disponibles": [c for c in ORDEN_CONDICION if c in df["CONDICION_CURSO"].astype(str).unique().tolist()],
        "cursos_disponibles": sorted(df["CURSO"].dropna().astype(str).unique().tolist()),
        "anios_disponibles": sorted(df["AÑO"].dropna().astype(str).unique().tolist()),
        "convocatorias_disponibles": sorted(df["CONVOCATORIA"].dropna().astype(str).unique().tolist()),
        "cantones_disponibles": sorted(df["CANTON_FINAL"].dropna().astype(str).unique().tolist())
    }
