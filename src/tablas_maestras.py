import io
from typing import List, Optional, Dict
import pandas as pd

FILAS_CANONICAS = ["CANTON_FINAL", "AÑO", "CURSO", "CONVOCATORIA"]
COLUMNAS_CANONICAS = ["SEXO_MAESTRO", "CONDICION_CURSO"]
FILAS_PERMITIDAS = FILAS_CANONICAS.copy()
COLUMNAS_PERMITIDAS = COLUMNAS_CANONICAS.copy()
ORDEN_SEXO = ["Femenino", "Masculino", "Sexo"]
ORDEN_CONDICION = ["Certificado", "Deserción", "Intermitente", "Sin condición"]
CURSOS_AMIGABLES = {
    "admision": "Admisión y lógica", "admisión": "Admisión y lógica",
    "eplve": "Economía para la vida", "eplvim": "Economía para la vida: indicadores macroeconómicos",
    "eplvmys": "Economía para la Vida: mercado y sociedad", "excel": "Excel",
    "excelbasico": "Excel básico", "excelintermedio": "Excel intermedio", "redaccion": "Redacción Consciente",
}

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

def _quitar_columnas_duplicadas(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, ~df.columns.duplicated()].copy()

def _ordenar_dimensiones_seleccionadas(dims: List[str], canonicas: List[str]) -> List[str]:
    return [d for d in canonicas if d in dims]

def preparar_base_tabla_maestra(df: pd.DataFrame) -> pd.DataFrame:
    out = _quitar_columnas_duplicadas(df.copy())
    if "CANTON_FINAL" in out.columns:
        out["CANTON_FINAL"] = out["CANTON_FINAL"].fillna("Sin dato").astype(str).str.strip()
    else:
        col_canton = _asegurar_columna(out, ["CANTON_DEF", "CANTON"], "CANTON_FINAL")
        out["CANTON_FINAL"] = out[col_canton].fillna("Sin dato").astype(str).str.strip()
    out.loc[out["CANTON_FINAL"].isin(["", "nan", "None"]), "CANTON_FINAL"] = "Sin dato"

    col_curso = _asegurar_columna(out, ["CURSO", "curso"], "CURSO")
    out["CURSO"] = out[col_curso].fillna("Sin dato").astype(str).str.strip()
    out["CURSO_AMIGABLE"] = out["CURSO"].astype(str).str.lower().map(CURSOS_AMIGABLES).fillna(out["CURSO"])

    col_conv = _asegurar_columna(out, ["CONVOCATORIA", "convocatoria"], "CONVOCATORIA")
    out["CONVOCATORIA"] = out[col_conv].fillna("Sin dato").astype(str).str.strip()
    out.loc[out["CONVOCATORIA"].isin(["", "nan", "None", "<NA>"]), "CONVOCATORIA"] = "Sin dato"

    col_anio = _asegurar_columna(out, ["AÑO", "anio"], "AÑO")
    out["AÑO"] = out[col_anio].astype(str).str.strip()
    out.loc[out["AÑO"].isin(["", "nan", "None", "<NA>"]), "AÑO"] = "Sin dato"

    col_sexo = _buscar_columna(out, ["SEXO_FINAL", "SEXO_NORMALIZADO", "SEXO"])
    if col_sexo is None:
        out["SEXO_MAESTRO"] = "Sexo"
    else:
        out["SEXO_MAESTRO"] = out[col_sexo].fillna("Sexo").astype(str).str.strip().replace({"": "Sexo", "nan": "Sexo", "None": "Sexo", "Sin dato": "Sexo", "NR": "Sexo"})
    out.loc[~out["SEXO_MAESTRO"].isin(ORDEN_SEXO), "SEXO_MAESTRO"] = "Sexo"

    col_benef = _buscar_columna(out, ["BENEFICIARIO", "beneficiario"])
    out["BENEFICIARIO_MAESTRO"] = pd.to_numeric(out[col_benef], errors="coerce").fillna(0).astype(int) if col_benef else 0
    col_cert = _buscar_columna(out, ["CERTIFICADO", "certificado"])
    col_des = _buscar_columna(out, ["DESERCION", "DESERCIÓN", "desercion"])
    col_int = _buscar_columna(out, ["INTERMITENTE", "intermitente"])
    out["CERTIFICADO_MAESTRO"] = pd.to_numeric(out[col_cert], errors="coerce").fillna(0).astype(int) if col_cert else 0
    out["DESERCION_MAESTRO"] = pd.to_numeric(out[col_des], errors="coerce").fillna(0).astype(int) if col_des else 0
    out["INTERMITENTE_MAESTRO"] = pd.to_numeric(out[col_int], errors="coerce").fillna(0).astype(int) if col_int else 0

    def resolver_condicion(row):
        if row["CERTIFICADO_MAESTRO"] == 1: return "Certificado"
        if row["DESERCION_MAESTRO"] == 1: return "Deserción"
        if row["INTERMITENTE_MAESTRO"] == 1: return "Intermitente"
        return "Sin condición"

    out["CONDICION_CURSO"] = out.apply(resolver_condicion, axis=1)
    out["CONDICION_CURSO"] = pd.Categorical(out["CONDICION_CURSO"], categories=ORDEN_CONDICION, ordered=True)
    out["SEXO_MAESTRO"] = pd.Categorical(out["SEXO_MAESTRO"], categories=ORDEN_SEXO, ordered=True)
    out["__CONTEO__"] = 1
    return out

def filtrar_universo(df_base: pd.DataFrame, universo: str = "todos") -> pd.DataFrame:
    return df_base[df_base["BENEFICIARIO_MAESTRO"] == 1].copy() if (universo or "todos").strip().lower() == "beneficiarios" else df_base.copy()

def construir_tabla_maestra(df_base, row_dims, col_dims, universo="todos", incluir_total_fila=True, incluir_total_general=True, ordenar_para_exportacion=False):
    if not row_dims: raise ValueError("Debes seleccionar al menos una dimensión de filas.")
    if not col_dims: raise ValueError("Debes seleccionar al menos una dimensión de columnas.")
    df = filtrar_universo(preparar_base_tabla_maestra(df_base), universo)
    row_dims_pivot = _ordenar_dimensiones_seleccionadas(row_dims, FILAS_CANONICAS) if ordenar_para_exportacion else row_dims.copy()
    col_dims_pivot = _ordenar_dimensiones_seleccionadas(col_dims, COLUMNAS_CANONICAS) if ordenar_para_exportacion else col_dims.copy()
    df_pivot = df.copy()
    if "CURSO" in row_dims_pivot:
        df_pivot["CURSO"] = df_pivot["CURSO_AMIGABLE"]
    tabla = pd.pivot_table(df_pivot, index=row_dims_pivot, columns=col_dims_pivot, values="__CONTEO__", aggfunc="sum", fill_value=0, observed=False)
    if col_dims_pivot == ["SEXO_MAESTRO", "CONDICION_CURSO"]:
        columnas_esperadas = pd.MultiIndex.from_product([ORDEN_SEXO, ORDEN_CONDICION], names=col_dims_pivot)
        tabla = tabla.reindex(columns=columnas_esperadas, fill_value=0)
    if incluir_total_fila:
        tabla[("TOTAL_POR_FILA", "") if isinstance(tabla.columns, pd.MultiIndex) else "TOTAL_POR_FILA"] = tabla.sum(axis=1)
    if incluir_total_general:
        total_general = tabla.sum(axis=0)
        total_general.name = tuple(["TOTAL_GENERAL"] * len(row_dims_pivot)) if len(row_dims_pivot) > 1 else "TOTAL_GENERAL"
        tabla = pd.concat([tabla, total_general.to_frame().T])
    return tabla

def aplanar_tabla_maestra(tabla):
    out = tabla.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [" | ".join([str(x) for x in col if str(x) not in ["", "None"]]) if isinstance(col, tuple) else str(col) for col in out.columns]
    else:
        out.columns = [str(c) for c in out.columns]
    return out.reset_index()

def construir_panel_exportacion(df_base, universo="todos", columnas_extra=None):
    df = filtrar_universo(preparar_base_tabla_maestra(df_base), universo)
    columnas_base = ["CANTON_FINAL", "AÑO", "CURSO_AMIGABLE", "CONVOCATORIA", "SEXO_MAESTRO", "CONDICION_CURSO", "BENEFICIARIO_MAESTRO", "CERTIFICADO_MAESTRO", "DESERCION_MAESTRO", "INTERMITENTE_MAESTRO"]
    if columnas_extra:
        columnas_base += [c for c in columnas_extra if c in df.columns]
    columnas_base = [c for c in columnas_base if c in df.columns]
    panel = df[columnas_base].copy()
    return panel.rename(columns={"CURSO_AMIGABLE": "CURSO"})

def exportar_tabla_maestra_excel(tabla, panel_df, row_dims_export, col_dims_export, nombre_hoja_tabla="TablaMaestra", nombre_hoja_panel="PanelLong"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        wb = writer.book
        ws = wb.add_worksheet(nombre_hoja_tabla)
        writer.sheets[nombre_hoja_tabla] = ws
        fmt_header_top = wb.add_format({"bold": True, "align": "center", "valign": "vcenter", "bg_color": "#5EA8BD", "border": 1})
        fmt_header_second = wb.add_format({"bold": True, "align": "center", "valign": "vcenter", "bg_color": "#D9EEF2", "border": 1})
        fmt_stub_header = wb.add_format({"bold": True, "align": "center", "valign": "vcenter", "bg_color": "#5EA8BD", "border": 1})
        fmt_row_label = wb.add_format({"bold": True, "bg_color": "#D9EEF2", "border": 1})
        fmt_total = wb.add_format({"bold": True, "bg_color": "#D9EEF2", "border": 1})
        fmt_data = wb.add_format({"align": "center", "border": 1})
        tabla_export = tabla.copy()
        if "CURSO" in row_dims_export and isinstance(tabla_export.index, pd.MultiIndex):
            idx_names = list(tabla_export.index.names)
            if "CURSO" in idx_names:
                idx_df = tabla_export.index.to_frame(index=False)
                idx_df["CURSO"] = idx_df["CURSO"].astype(str).str.lower().map(CURSOS_AMIGABLES).fillna(idx_df["CURSO"])
                tabla_export.index = pd.MultiIndex.from_frame(idx_df)
                tabla_export.index.names = idx_names
        row_df = tabla_export.reset_index()
        n_row_dims = len(row_dims_export)
        if isinstance(tabla_export.columns, pd.MultiIndex):
            col_tuples = list(tabla_export.columns)
            n_header_rows = tabla_export.columns.nlevels
            for i, dim in enumerate(row_dims_export):
                ws.merge_range(0, i, n_header_rows - 1, i, dim.replace("_", " "), fmt_stub_header)
            for level in range(n_header_rows):
                start_col = n_row_dims
                j = 0
                while j < len(col_tuples):
                    val = col_tuples[j][level]
                    end_j = j
                    while end_j + 1 < len(col_tuples) and col_tuples[end_j + 1][level] == val and col_tuples[end_j + 1][:level] == col_tuples[j][:level]:
                        end_j += 1
                    c1, c2 = start_col + j, start_col + end_j
                    fmt = fmt_header_top if level == 0 else fmt_header_second
                    if c1 == c2: ws.write(level, c1, str(val), fmt)
                    else: ws.merge_range(level, c1, level, c2, str(val), fmt)
                    j = end_j + 1
            start_row = n_header_rows
            for r_idx in range(len(row_df)):
                for c_idx in range(len(row_df.columns)):
                    val = row_df.iloc[r_idx, c_idx]
                    fmt = fmt_row_label if c_idx < n_row_dims else fmt_data
                    if r_idx == len(row_df)-1 or str(val) == "TOTAL_GENERAL": fmt = fmt_total
                    ws.write(start_row + r_idx, c_idx, val, fmt)
        else:
            for c_idx, col_name in enumerate(row_df.columns):
                fmt = fmt_stub_header if c_idx < n_row_dims else fmt_header_second
                ws.write(0, c_idx, str(col_name), fmt)
            for r_idx in range(len(row_df)):
                for c_idx in range(len(row_df.columns)):
                    val = row_df.iloc[r_idx, c_idx]
                    fmt = fmt_row_label if c_idx < n_row_dims else fmt_data
                    if r_idx == len(row_df)-1 or str(val) == "TOTAL_GENERAL": fmt = fmt_total
                    ws.write(r_idx+1, c_idx, val, fmt)
        for i, col in enumerate(row_df.columns):
            ws.set_column(i, i, max(12, min(28, len(str(col))+2)))
        freeze_row = tabla_export.columns.nlevels if isinstance(tabla_export.columns, pd.MultiIndex) else 1
        ws.freeze_panes(freeze_row, len(row_dims_export))
        panel_df.to_excel(writer, sheet_name=nombre_hoja_panel, index=False)
        ws_panel = writer.sheets[nombre_hoja_panel]
        for i, col in enumerate(panel_df.columns):
            ws_panel.set_column(i, i, max(12, min(26, len(str(col))+2)))
    return output.getvalue()

def obtener_etiquetas_disponibles(df_base):
    df = preparar_base_tabla_maestra(df_base)
    return {
        "filas_permitidas": FILAS_PERMITIDAS,
        "columnas_permitidas": COLUMNAS_PERMITIDAS,
        "sexos_disponibles": [s for s in ORDEN_SEXO if s in df["SEXO_MAESTRO"].astype(str).unique().tolist()],
        "condiciones_disponibles": [c for c in ORDEN_CONDICION if c in df["CONDICION_CURSO"].astype(str).unique().tolist()],
        "cursos_disponibles": sorted(df["CURSO_AMIGABLE"].dropna().astype(str).unique().tolist()),
        "anios_disponibles": sorted(df["AÑO"].dropna().astype(str).unique().tolist()),
        "convocatorias_disponibles": sorted(df["CONVOCATORIA"].dropna().astype(str).unique().tolist()),
        "cantones_disponibles": sorted(df["CANTON_FINAL"].dropna().astype(str).unique().tolist()),
    }
