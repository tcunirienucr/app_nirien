import pandas as pd
import numpy as np
import unicodedata

# ---------------------------
# Funciones auxiliares de limpieza
# ---------------------------

def clasificar_edad(valor):
    try:
        if pd.isna(valor):
            return 'Sin dato'
        if isinstance(valor, (int, float, np.integer, np.floating)):
            v = int(valor)
            if 13 <= v <= 18:
                return "13 a 18"
            elif 19 <= v <= 35:
                return "19 a 35"
            elif 36 <= v <= 64:
                return "36 a 64"
            elif v >= 65 and v < 98:
                return "Mayor a 65"
            elif v in (98, 102, 109):
                return "19 a 35"
            elif v in (99, 105, 106):
                return "36 a 64"
            elif v == 103:
                return "30 a 39"
            else:
                return 'Sin dato'

        v = str(valor).strip()
        if v == '' or v.lower() == 'información incompleta':
            return 'Sin dato'
        if v in ['15-19', '15 a 18', '15-18']:
            return '13 a 18'
        if v in ["19-35", "20-29", "20 a 29", "18 a 35 años", "20 o más", "Más de 20"]:
            return '19 a 35'
        if v in ["30-39", "30 a 39"]:
            return "30 a 39"
        if v in ["36-64", "40-49", "40 a 49", "50-59", "Más de 50", "36 a 64 años", "Más de 30"]:
            return '36 a 64'
        if v in ["Más de 60", "Más de 65"]:
            return 'Mayor a 65'
        if v in ["Sin dato"]:
            return "Sin dato"

    except Exception:
        return 'Sin dato'

    return 'Sin dato'


def normalizar_sexo(valor):
    if pd.isna(valor):
        return "Sin dato"

    v = str(valor).strip()
    if v == "":
        return "Sin dato"

    low = v.lower()

    if low in ['femenino', 'f', 'mujer', 'female']:
        return 'Femenino'
    if low in ['masculino', 'm', 'hombre', 'male']:
        return 'Masculino'
    if low in ['no indica', 'no responde', 'no contesta', 'nr']:
        return 'NR'
    if low in ['sin dato', 'ns']:
        return 'Sin dato'

    return 'Sin dato'


def strip_accents(s: str) -> str:
    return unicodedata.normalize('NFKD', s).encode('ascii', errors='ignore').decode('utf-8') if isinstance(s, str) else s


def safe_get_column(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None