import json
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.limpieza import normalizar_sexo, strip_accents, safe_get_column


CANTONES_OFICIALES = {
    "San José", "Escazú", "Desamparados", "Puriscal", "Tarrazú", "Aserrí", "Mora",
    "Goicoechea", "Santa Ana", "Alajuelita", "Vázquez de Coronado", "Acosta", "Tibás",
    "Moravia", "Montes de Oca", "Turrubares", "Dota", "Curridabat", "Pérez Zeledón",
    "León Cortés Castro", "Alajuela", "San Ramón", "Grecia", "San Mateo", "Atenas",
    "Naranjo", "Palmares", "Poás", "Orotina", "San Carlos", "Zarcero", "Sarchí", "Upala",
    "Los Chiles", "Guatuso", "Río Cuarto", "Cartago", "Paraíso", "La Unión", "Jiménez",
    "Turrialba", "Alvarado", "Oreamuno", "El Guarco", "Heredia", "Barva", "Santo Domingo",
    "Santa Bárbara", "San Rafael", "San Isidro", "Belén", "Flores", "San Pablo", "Sarapiquí",
    "Liberia", "Nicoya", "Santa Cruz", "Bagaces", "Carrillo", "Cañas", "Abangares", "Tilarán",
    "Nandayure", "La Cruz", "Hojancha", "Puntarenas", "Esparza", "Buenos Aires", "Montes de Oro",
    "Osa", "Quepos", "Golfito", "Coto Brus", "Parrita", "Corredores", "Garabito", "Monteverde",
    "Puerto Jimenez", "Limón", "Pococí", "Siquirres", "Talamanca", "Matina", "Guácimo", "Sin dato"
}


# =========================
# HELPERS
# =========================

def _buscar_columna(df: pd.DataFrame, candidatos: List[str]) -> Optional[str]:
    return safe_get_column(df, candidatos)


def _asegurar_columna(df: pd.DataFrame, candidatos: List[str], nombre_logico: str) -> str:
    col = _buscar_columna(df, candidatos)
    if col is None:
        raise KeyError(f"No encontré columna para '{nombre_logico}'. Busqué: {candidatos}")
    return col


def _quitar_columnas_duplicadas(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, ~df.columns.duplicated()].copy()


def cargar_correcciones(ruta_json: Path) -> dict:
    if ruta_json.exists():
        with open(ruta_json, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_invalidos(invalidos, ruta_salida: Path):
    df_invalidos = pd.DataFrame({"CANTON_INVALIDO": sorted(list(invalidos))})
    df_invalidos.to_csv(ruta_salida, index=False, encoding="utf-8-sig")


# =========================
# DERIVACIONES ROBUSTAS
# =========================

def _resolver_canton_final(df: pd.DataFrame) -> pd.Series:
    """
    Prioridad:
    1. CANTON_FINAL
    2. CANTON_DEF
    3. CANTON
    4. Sin dato
    """
    if "CANTON_FINAL" in df.columns:
        s = df["CANTON_FINAL"].copy()
    elif "CANTON_DEF" in df.columns:
        s = df["CANTON_DEF"].copy()
    elif "CANTON" in df.columns:
        s = df["CANTON"].copy()
    else:
        s = pd.Series(["Sin dato"] * len(df), index=df.index)

    s = s.fillna("Sin dato").astype(str).str.strip()
    s = s.replace({"": "Sin dato", "nan": "Sin dato", "None": "Sin dato", "NR": "Sin dato"})
    return s


def _resolver_sexo_final(df: pd.DataFrame) -> pd.Series:
    """
    Prioridad:
    1. SEXO_FINAL
    2. SEXO_NORMALIZADO
    3. SEXO
    Faltantes se etiquetan como 'Sexo' por decisión de UX.
    """
    col = _buscar_columna(df, ["SEXO_FINAL", "SEXO_NORMALIZADO", "SEXO"])
    if col is None:
        s = pd.Series(["Sexo"] * len(df), index=df.index)
    else:
        s = df[col].copy().apply(normalizar_sexo)

    s = s.fillna("Sexo").astype(str)
    s = s.replace({"NR": "Sexo", "Sin dato": "Sexo", "": "Sexo", "nan": "Sexo", "None": "Sexo"})
    return s


def _resolver_curso(df: pd.DataFrame) -> pd.Series:
    col = _buscar_columna(df, ["CURSO", "curso"])
    if col is not None:
        s = df[col].copy()
    elif "EDICION" in df.columns:
        s = df["EDICION"].astype(str).str.extract(r'([^-]+)-', expand=False)
    else:
        s = pd.Series(["Sin dato"] * len(df), index=df.index)
    return s.fillna("Sin dato").astype(str).str.strip()


def _resolver_convocatoria(df: pd.DataFrame) -> pd.Series:
    col = _buscar_columna(df, ["CONVOCATORIA", "convocatoria"])
    if col is not None:
        s = df[col].copy()
    elif "EDICION" in df.columns:
        s = df["EDICION"].astype(str).str.extract(r'^[^-]+-(\d+)-', expand=False)
    else:
        s = pd.Series(["Sin dato"] * len(df), index=df.index)
    s = s.fillna("Sin dato").astype(str).str.strip()
    s = s.replace({"": "Sin dato", "nan": "Sin dato", "None": "Sin dato", "<NA>": "Sin dato"})
    return s


def _resolver_anio(df: pd.DataFrame) -> pd.Series:
    col = _buscar_columna(df, ["AÑO", "anio"])
    if col is not None:
        s = df[col].copy()
    elif "EDICION" in df.columns:
        s = df["EDICION"].astype(str).str.extract(r'-(\d{4})$', expand=False)
    else:
        s = pd.Series([pd.NA] * len(df), index=df.index)
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def _resolver_beneficiario(df: pd.DataFrame) -> pd.Series:
    col = _buscar_columna(df, ["BENEFICIARIO", "beneficiario"])
    if col is None:
        return pd.Series([0] * len(df), index=df.index, dtype="int64")
    return pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)


def _resolver_flag(df: pd.DataFrame, candidatos: List[str]) -> pd.Series:
    col = _buscar_columna(df, candidatos)
    if col is None:
        return pd.Series([0] * len(df), index=df.index, dtype="int64")
    return pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)


# =========================
# ETL PRINCIPAL PARA APP
# =========================

def crear_df_app(df_original: pd.DataFrame, correcciones: dict, ruta_invalidos: Path) -> pd.DataFrame:
    """
    Crea el dataset final para TODA la app.

    Importante:
    - NO filtra solo beneficiarios.
    - Conserva BENEFICIARIO como variable para el filtro global.
    - Genera CANTON_FINAL y deja CANTON_DEF = CANTON_FINAL como compatibilidad temporal.
    - Genera SEXO_FINAL y SEXO_NORMALIZADO.
    """
    df = _quitar_columnas_duplicadas(df_original.copy())
    out = pd.DataFrame(index=df.index)

    out["CANTON_FINAL"] = _resolver_canton_final(df).replace(correcciones)
    out["CANTON_DEF"] = out["CANTON_FINAL"]  # compatibilidad temporal con módulos del mapa/resumen antiguos

    # Validación cantonal
    invalidos = set(
        out.loc[
            ~out["CANTON_FINAL"].isin(CANTONES_OFICIALES) | out["CANTON_FINAL"].isna(),
            "CANTON_FINAL"
        ].dropna().astype(str).unique()
    )
    if invalidos:
        guardar_invalidos(invalidos, ruta_invalidos)
        raise ValueError(f"Se detectaron cantones inválidos. Revisa: {ruta_invalidos}")

    out["CURSO"] = _resolver_curso(df)
    out["CURSO_NORMALIZADO"] = out["CURSO"].astype(str).str.lower().apply(strip_accents).str.strip()
    out["CONVOCATORIA"] = _resolver_convocatoria(df)
    out["AÑO"] = _resolver_anio(df)

    out["SEXO_FINAL"] = _resolver_sexo_final(df)
    out["SEXO_NORMALIZADO"] = out["SEXO_FINAL"]

    # EDAD se preserva aunque por ahora no sea dimensión maestra
    col_edad = _buscar_columna(df, ["EDAD_FINAL", "EDAD", "edad"])
    if col_edad is not None:
        out["EDAD"] = df[col_edad].fillna("Sin dato").astype(str).str.strip()
    else:
        out["EDAD"] = "Sin dato"

    col_edad_clas = _buscar_columna(df, ["EDAD_CLASIFICADA"])
    if col_edad_clas is not None:
        out["EDAD_CLASIFICADA"] = df[col_edad_clas].fillna("Sin dato").astype(str).str.strip()
    else:
        out["EDAD_CLASIFICADA"] = "Sin dato"

    out["BENEFICIARIO"] = _resolver_beneficiario(df)
    out["CERTIFICADO"] = _resolver_flag(df, ["CERTIFICADO", "certificado"])
    out["DESERCION"] = _resolver_flag(df, ["DESERCION", "DESERCIÓN", "desercion"])
    out["INTERMITENTE"] = _resolver_flag(df, ["INTERMITENTE", "intermitente"])

    if "EDICION" in df.columns:
        out["EDICION"] = df["EDICION"].fillna("Sin dato").astype(str).str.strip()

    return out
