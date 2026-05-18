import streamlit as st
import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.express as px
from datetime import date, datetime

from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection

from src.limpieza import clasificar_edad, normalizar_sexo, strip_accents, safe_get_column
from src.transform import preparar_datos_resumen
from src.mapas import preparar_gdf_mapa, crear_colormap, crear_mapa_folium


# ===========================
# CONFIGURACIÓN GENERAL
# ===========================

st.set_page_config(layout="wide", page_title="Mapa y Estadísticas — TCU Nirien")

ruta_mapa = "data/limitecantonal_5k_fixed.geojson"
columna_mapa = "CANTÓN"

nombre_amigable = {
    "admision": "Admisión y lógica",
    "admisión": "Admisión y lógica",
    "eplve": "Economía para la vida",
    "eplvim": "Economía para la vida: indicadores macroeconómicos",
    "eplvmys": "Economía para la Vida: mercado y sociedad",
    "excel": "Excel",
    "excelbasico": "Excel básico",
    "excelintermedio": "Excel intermedio",
    "redaccion": "Redacción Consciente"
}

st.title("📊 Mapa y Estadísticas de las personas beneficiarias: TCU Nirien - Habilidades para la Vida - UCR")


# ===========================
# CONEXIÓN Y CARGA DE DATOS
# ===========================

conn = st.connection("gsheets", type=GSheetsConnection)


@st.cache_data(ttl=600)
def cargar_datos():
    df = conn.read(worksheet="mapa_abril2026v1")

    def convert_dates(x):
        if isinstance(x, (pd.Timestamp, datetime, date)):
            return x.strftime("%Y-%m-%d")
        return x

    df = df.map(convert_dates)

    # CURSO
    if 'CURSO' in df.columns:
        df['CURSO'] = df['CURSO'].fillna('').astype(str)
    else:
        df['CURSO'] = ''

    df['CURSO_NORMALIZADO'] = df['CURSO'].str.lower().apply(strip_accents).str.strip()

    # AÑO
    if 'AÑO' in df.columns:
        df['AÑO'] = pd.to_numeric(df['AÑO'], errors='coerce').astype('Int64')
    else:
        df['AÑO'] = pd.NA

    # FLAGS
    for col in ['CERTIFICADO', 'DESERCION', 'INTERMITENTE']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        else:
            df[col] = 0

    # CANTON_DEF
    if 'CANTON_DEF' not in df.columns:
        alt = safe_get_column(df, ['CANTÓN', 'Canton', 'CANTON', 'canton'])
        if alt is not None:
            df['CANTON_DEF'] = df[alt].fillna('Sin dato').astype(str).str.strip()
        else:
            df['CANTON_DEF'] = 'Sin dato'
    else:
        df['CANTON_DEF'] = df['CANTON_DEF'].fillna('Sin dato').astype(str).str.strip()

    # EDAD
    if 'EDAD' in df.columns:
        df['EDAD_CLASIFICADA'] = df['EDAD'].apply(clasificar_edad)
    else:
        df['EDAD_CLASIFICADA'] = 'Sin dato'

    # SEXO
    if 'SEXO' in df.columns:
        df['SEXO_NORMALIZADO'] = df['SEXO'].apply(normalizar_sexo)
    else:
        df['SEXO_NORMALIZADO'] = 'Sin dato'

    return df


@st.cache_data(ttl=3600)
def cargar_geojson():
    return gpd.read_file(ruta_mapa)


try:
    df = cargar_datos()
except Exception as e:
    st.error(f"Error cargando Google Sheet: {e}")
    st.stop()

try:
    gdf = cargar_geojson()
except Exception as e:
    st.error(f"Error cargando GeoJSON: {e}")
    st.stop()


# ===========================
# SIDEBAR / FILTROS
# ===========================

with st.sidebar:
    st.header("Filtros")

    # Cursos
    select_all_cursos = st.checkbox("Seleccionar todos los cursos", value=True)
    cursos_disponibles_raw = sorted(df['CURSO_NORMALIZADO'].dropna().unique())
    cursos_display = [nombre_amigable.get(c, c.title()) for c in cursos_disponibles_raw]

    if not select_all_cursos:
        seleccion_cursos_display = st.multiselect(
            "Cursos (seleccioná uno o más)",
            cursos_display,
            default=cursos_display[:3] if len(cursos_display) >= 3 else cursos_display
        )
    else:
        seleccion_cursos_display = None

    # Años
    select_all_anios = st.checkbox("Seleccionar todos los años", value=True)
    anios_disponibles = sorted([int(i) for i in df['AÑO'].dropna().unique()])

    if not select_all_anios:
        seleccion_anios = st.multiselect(
            "Años (seleccioná uno o más)",
            anios_disponibles,
            default=anios_disponibles
        )
    else:
        seleccion_anios = None

    # Cantones
    select_all_cantones = st.checkbox("Seleccionar todos los cantones", value=True)
    cantones_disponibles = sorted(gdf[columna_mapa].dropna().unique())

    if not select_all_cantones:
        seleccion_cantones = st.multiselect(
            "Cantones (seleccioná uno o más)",
            cantones_disponibles,
            default=cantones_disponibles[:5] if len(cantones_disponibles) >= 5 else cantones_disponibles
        )
    else:
        seleccion_cantones = None

    # Flags
    st.markdown("---")
    select_all_flags = st.checkbox(
        "Seleccionar todos los estados (CERTIFICADO / DESERCION / INTERMITENTE)",
        value=True
    )

    if not select_all_flags:
        flag_cert = st.checkbox("CERTIFICADO == 1", value=True)
        flag_des = st.checkbox("DESERCION == 1", value=False)
        flag_int = st.checkbox("INTERMITENTE == 1", value=False)
    else:
        flag_cert = True
        flag_des = True
        flag_int = True

    # Edad
    st.markdown("---")
    select_all_edades = st.checkbox("Seleccionar todos los grupos de edad", value=True)
    edades_disponibles = sorted(df['EDAD_CLASIFICADA'].dropna().unique())

    if not select_all_edades:
        seleccion_edades = st.multiselect(
            "Grupo de Edad",
            edades_disponibles,
            default=edades_disponibles
        )
    else:
        seleccion_edades = None

    # Sexo
    select_all_sexos = st.checkbox("Seleccionar todos los sexos", value=True)
    sexos_disponibles = sorted(df['SEXO_NORMALIZADO'].dropna().unique())

    if not select_all_sexos:
        seleccion_sexos = st.multiselect(
            "Sexo",
            sexos_disponibles,
            default=sexos_disponibles
        )
    else:
        seleccion_sexos = None


# ===========================
# LISTAS FINALES DE FILTRO
# ===========================

if seleccion_cursos_display is None:
    cursos_filtrados = list(cursos_disponibles_raw)
else:
    cursos_filtrados = []

    for key, friendly in nombre_amigable.items():
        if friendly in seleccion_cursos_display:
            cursos_filtrados.append(key)

    for raw, disp in zip(cursos_disponibles_raw, cursos_display):
        if disp in seleccion_cursos_display and raw not in cursos_filtrados:
            cursos_filtrados.append(raw)

if seleccion_anios is None:
    anios_seleccionados = anios_disponibles
else:
    anios_seleccionados = seleccion_anios

if seleccion_cantones is None:
    cantones_seleccionados = cantones_disponibles
else:
    cantones_seleccionados = seleccion_cantones

cert_flags = {
    'CERTIFICADO': flag_cert,
    'DESERCION': flag_des,
    'INTERMITENTE': flag_int
}

if seleccion_edades is None:
    edades_seleccionadas = edades_disponibles
else:
    edades_seleccionadas = seleccion_edades

if seleccion_sexos is None:
    sexos_seleccionados = sexos_disponibles
else:
    sexos_seleccionados = seleccion_sexos


# ===========================
# FILTRADO
# ===========================

mask = pd.Series(True, index=df.index)

if cursos_filtrados:
    mask &= df['CURSO_NORMALIZADO'].isin(cursos_filtrados)

if len(anios_seleccionados) > 0:
    mask &= df['AÑO'].isin(anios_seleccionados)

if cantones_seleccionados:
    mask &= df['CANTON_DEF'].isin(cantones_seleccionados)

if not select_all_flags:
    mask_flag = pd.Series(False, index=df.index)

    if cert_flags['CERTIFICADO']:
        mask_flag |= (df['CERTIFICADO'] == 1)
    if cert_flags['DESERCION']:
        mask_flag |= (df['DESERCION'] == 1)
    if cert_flags['INTERMITENTE']:
        mask_flag |= (df['INTERMITENTE'] == 1)

    if not (cert_flags['CERTIFICADO'] or cert_flags['DESERCION'] or cert_flags['INTERMITENTE']):
        mask &= False
    else:
        mask &= mask_flag

if edades_seleccionadas:
    mask &= df['EDAD_CLASIFICADA'].isin(edades_seleccionadas)

if sexos_seleccionados:
    mask &= df['SEXO_NORMALIZADO'].isin(sexos_seleccionados)

df_filtrado = df[mask].copy()


# ===========================
# RESÚMENES Y MAPA
# ===========================

df_cantonal, df_detalle = preparar_datos_resumen(df_filtrado)

gdf_para_mapa, gdf_merged = preparar_gdf_mapa(gdf, df_cantonal, columna_mapa)

max_beneficiarios = int(gdf_merged['cantidad_color'].max() or 0)
colormap, color_cero = crear_colormap(max_beneficiarios)

st.subheader("🗺️ Mapa Interactivo")

m = crear_mapa_folium(
    gdf_para_mapa=gdf_para_mapa,
    columna_mapa=columna_mapa,
    colormap=colormap,
    color_cero=color_cero,
    select_all_cantones=select_all_cantones,
    cantones_seleccionados=cantones_seleccionados
)

st_folium(m, width=900, height=600, returned_objects=[])


# ===========================
# SIN DATO
# ===========================

df_sin_dato = df_filtrado[df_filtrado['CANTON_DEF'].fillna('Sin dato') == "Sin dato"]
total_sin_dato = len(df_sin_dato)

if total_sin_dato > 0:
    with st.expander(f"ℹ️ Observaciones 'Sin dato' (fuera del mapa): {total_sin_dato} personas"):
        detalles_sin_dato = df_detalle[df_detalle['CANTON_DEF'] == "Sin dato"]

        if detalles_sin_dato.empty:
            st.write("No se encontró detalle para las observaciones 'Sin dato'.")
        else:
            st.markdown("<strong>Detalle por curso y año:</strong>", unsafe_allow_html=True)
            detalle_html = "<ul>"

            for _, d in detalles_sin_dato.iterrows():
                curso = nombre_amigable.get(d['CURSO_NORMALIZADO'], d['CURSO_NORMALIZADO'].title())
                anio = int(d['AÑO']) if not pd.isna(d['AÑO']) else 'ND'
                detalle_html += f"<li>{curso} ({anio}): {d['conteo']} personas</li>"

            detalle_html += "</ul>"
            st.markdown(detalle_html, unsafe_allow_html=True)


# ===========================
# ESTADÍSTICAS
# ===========================

st.subheader("📊 Estadísticas Descriptivas")

if df_filtrado.empty:
    st.info("No hay datos con los filtros seleccionados.")
else:
    # Curso
    st.subheader("Resumen por Curso")
    resumen_curso = df_filtrado.groupby(['CURSO_NORMALIZADO', 'CERTIFICADO']).size().unstack(fill_value=0)
    resumen_curso['Total'] = resumen_curso.sum(axis=1)
    resumen_curso['% Certificado'] = (
        resumen_curso.get(1, 0) / resumen_curso['Total']
    ).replace([np.inf, -np.inf, np.nan], 0) * 100
    resumen_curso = resumen_curso.rename(index=nombre_amigable)
    st.dataframe(resumen_curso)

    # Cantón
    st.subheader("Resumen por Cantón")
    resumen_canton = df_filtrado.groupby(['CANTON_DEF', 'CERTIFICADO']).size().unstack(fill_value=0)
    resumen_canton['Total'] = resumen_canton.sum(axis=1)
    resumen_canton['% Certificado'] = (
        resumen_canton.get(1, 0) / resumen_canton['Total']
    ).replace([np.inf, -np.inf, np.nan], 0) * 100
    st.dataframe(resumen_canton)

    # Línea por año
    st.subheader("Gráfico de Línea por Año")
    df_anual_filtrado = df_filtrado.dropna(subset=['AÑO'])

    if not df_anual_filtrado.empty:
        df_anual = df_anual_filtrado.groupby(['AÑO', 'CERTIFICADO']).size().unstack(fill_value=0)
        df_anual['Total'] = df_anual.sum(axis=1)
        df_anual['% Certificado'] = (
            df_anual.get(1, 0) / df_anual['Total']
        ).replace([np.inf, -np.inf, np.nan], 0) * 100
        df_anual = df_anual.sort_index()

        fig_linea = px.line(
            df_anual.reset_index(),
            x='AÑO',
            y='% Certificado',
            title='Evolución de la Participación y Aprobación por Año',
            labels={'AÑO': 'Año', '% Certificado': '% Certificado'}
        )
        st.plotly_chart(fig_linea, use_container_width=True)
    else:
        st.info("No hay datos con año asignado para graficar la evolución.")


# ===========================
# DESCARGAS
# ===========================

st.subheader("📥 Descargar Datos Filtrados")

@st.cache_data
def convertir_a_excel(df_to_save):
    import io
    from pandas import ExcelWriter

    output = io.BytesIO()
    with ExcelWriter(output, engine='xlsxwriter') as writer:
        df_to_save.to_excel(writer, index=False, sheet_name='DatosFiltrados')

    return output.getvalue()


if not df_filtrado.empty:
    archivo_excel = convertir_a_excel(df_filtrado)

    st.download_button(
        label="📥 Descargar datos filtrados en Excel",
        data=archivo_excel,
        file_name='datos_filtrados.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
else:
    st.warning("No hay datos filtrados para descargar.")


st.subheader("📥 Descargar Datos Colapsados (por Cantón - Curso - Año)")
activar_colapsado = st.checkbox("Quiero descargar los datos colapsados por Cantón - Curso - Año")

if activar_colapsado:
    if df_filtrado.empty:
        st.warning("No hay datos para colapsar con los filtros actuales.")
    else:
        df_temp = df_filtrado.dropna(subset=['AÑO', 'CANTON_DEF']).copy()

        if not df_temp.empty:
            df_temp['CURSO_AÑO'] = (
                df_temp['CURSO_NORMALIZADO']
                .map(nombre_amigable)
                .fillna(df_temp['CURSO_NORMALIZADO'].str.title())
                + " "
                + df_temp['AÑO'].astype(int).astype(str)
            )

            df_pivot = (
                df_temp
                .pivot_table(
                    index='CANTON_DEF',
                    columns='CURSO_AÑO',
                    values='CERTIFICADO',
                    aggfunc='count',
                    fill_value=0
                )
                .reset_index()
            )

            df_pivot['TOTAL'] = df_pivot.drop(columns='CANTON_DEF').sum(axis=1)

            columnas_ordenadas = (
                ['CANTON_DEF']
                + sorted([c for c in df_pivot.columns if c not in ['CANTON_DEF', 'TOTAL']])
                + ['TOTAL']
            )

            df_pivot = df_pivot[columnas_ordenadas]

            archivo_excel_colapsado = convertir_a_excel(df_pivot)

            st.download_button(
                label="📥 Descargar datos colapsados en Excel",
                data=archivo_excel_colapsado,
                file_name='datos_colapsados.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            st.warning("No hay datos con información de Año y Cantón para colapsar.")
