import json
from pathlib import Path
import pandas as pd

from src.limpieza import clasificar_edad, normalizar_sexo, strip_accents, safe_get_column


CANTONES_OFICIALES = {
    "San José","Escazú","Desamparados","Puriscal","Tarrazú","Aserrí","Mora",
    "Goicoechea","Santa Ana","Alajuelita","Vázquez de Coronado","Acosta","Tibás",
    "Moravia","Montes de Oca","Turrubares","Dota","Curridabat","Pérez Zeledón",
    "León Cortés Castro","Alajuela","San Ramón","Grecia","San Mateo","Atenas",
    "Naranjo","Palmares","Poás","Orotina","San Carlos","Zarcero","Sarchí","Upala",
    "Los Chiles","Guatuso","Río Cuarto","Cartago","Paraíso","La Unión","Jiménez",
    "Turrialba","Alvarado","Oreamuno","El Guarco","Heredia","Barva","Santo Domingo",
    "Santa Bárbara","San Rafael","San Isidro","Belén","Flores","San Pablo","Sarapiquí",
    "Liberia","Nicoya","Santa Cruz","Bagaces","Carrillo","Cañas","Abangares","Tilarán",
    "Nandayure","La Cruz","Hojancha","Puntarenas","Esparza","Buenos Aires","Montes de Oro",
    "Osa","Quepos","Golfito","Coto Brus","Parrita","Corredores","Garabito","Monteverde",
    "Puerto Jimenez","Limón","Pococí","Siquirres","Talamanca","Matina","Guácimo","Sin dato"
}


def cargar_correcciones(ruta_json: Path) -> dict:
    if ruta_json.exists():
        with open(ruta_json, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_invalidos(invalidos, ruta_salida: Path):
    df_invalidos = pd.DataFrame({"CANTON_INVALIDO": sorted(list(invalidos))})
    df_invalidos.to_csv(ruta_salida, index=False, encoding="utf-8-sig")


def buscar_columna(df, candidatos):
    col = safe_get_column(df, candidatos)
    if col is None:
        raise KeyError(f"No encontré ninguna de estas columnas: {candidatos}")
    return col


def crear_df_mapa(df_original: pd.DataFrame, correcciones: dict, ruta_invalidos: Path) -> pd.DataFrame:
    df = df_original.copy()

    # =====================
    # DETECTAR COLUMNAS
    # =====================

    col_benef = buscar_columna(df, ['beneficiario', 'BENEFICIARIO'])
    col_canton = buscar_columna(df, ['CANTON_FINAL'])
    col_sexo = buscar_columna(df, ['SEXO_FINAL'])
    col_edad = buscar_columna(df, ['EDAD_FINAL'])
    col_curso = buscar_columna(df, ['curso'])
    col_conv = buscar_columna(df, ['convocatoria'])
    col_anio = buscar_columna(df, ['anio'])

    col_cert = buscar_columna(df, ['CERTIFICADO'])
    col_des = buscar_columna(df, ['DESERCION'])
    col_int = buscar_columna(df, ['INTERMITENTE'])

    # =====================
    # FILTRAR BENEFICIARIOS
    # =====================

    df_mapa = df[df[col_benef] == 1].copy()

    # =====================
    # SELECCIONAR VARIABLES LIMPIAS
    # =====================

    df_mapa = df_mapa[[
        col_canton,
        col_curso,
        col_conv,
        col_anio,
        col_cert,
        col_des,
        col_int,
        col_edad,
        col_sexo
    ]].copy()

    # =====================
    # RENOMBRAR
    # =====================

    df_mapa.columns = [
        'CANTON_DEF',
        'CURSO',
        'CONVOCATORIA',
        'AÑO',
        'CERTIFICADO',
        'DESERCION',
        'INTERMITENTE',
        'EDAD',
        'SEXO'
    ]

    # =====================
    # LIMPIEZA BÁSICA
    # =====================

    df_mapa = df_mapa.fillna("NR")

    df_mapa['CANTON_DEF'] = df_mapa['CANTON_DEF'].replace(['NR', '', None], 'Sin dato')
    df_mapa['CANTON_DEF'] = df_mapa['CANTON_DEF'].replace(correcciones)

    # =====================
    # VALIDACIÓN DE CANTONES
    # =====================

    invalidos = set(
        df_mapa.loc[
            ~df_mapa['CANTON_DEF'].isin(CANTONES_OFICIALES) | df_mapa['CANTON_DEF'].isna(),
            'CANTON_DEF'
        ].dropna().astype(str).unique()
    )

    if invalidos:
        guardar_invalidos(invalidos, ruta_invalidos)
        raise ValueError(f"Se detectaron cantones inválidos. Ver: {ruta_invalidos}")

    # =====================
    # NORMALIZACIÓN FINAL
    # =====================

    df_mapa['CURSO_NORMALIZADO'] = df_mapa['CURSO'].astype(str).str.lower().apply(strip_accents).str.strip()
    df_mapa['AÑO'] = pd.to_numeric(df_mapa['AÑO'], errors='coerce').astype('Int64')

    df_mapa['CERTIFICADO'] = pd.to_numeric(df_mapa['CERTIFICADO'], errors='coerce').fillna(0).astype(int)
    df_mapa['DESERCION'] = pd.to_numeric(df_mapa['DESERCION'], errors='coerce').fillna(0).astype(int)
    df_mapa['INTERMITENTE'] = pd.to_numeric(df_mapa['INTERMITENTE'], errors='coerce').fillna(0).astype(int)

    df_mapa['EDAD_CLASIFICADA'] = df_mapa['EDAD'].apply(clasificar_edad)
    df_mapa['SEXO_NORMALIZADO'] = df_mapa['SEXO'].apply(normalizar_sexo)

    # 🔥 CLAVE PARA PARQUET
    for col in df_mapa.columns:
        df_mapa[col] = df_mapa[col].astype(str)

    return df_mapa
