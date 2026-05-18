import io

import streamlit as st
import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.express as px

from streamlit_folium import st_folium

from src.transform import preparar_datos_resumen
from src.mapas import preparar_gdf_mapa, crear_colormap, crear_mapa_folium


# ===========================
# CONFIG
# ===========================

st.set_page_config(layout="wide", page_title="Mapa y Estadísticas — TCU Nirien")

ruta_mapa = "data/limitecantonal_5k_fixed.geojson"
ruta_data = "data/mapa_latest.parquet"
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

st.title("📊 Mapa y Estadísticas — TCU Nirien")
st.caption("Build de prueba HF")

# ===========================
# CARGA DE DATOS
# ===========================

@st.cache_data
def cargar_datos():
    df = pd.read_parquet(ruta_data)

    # ======================
    # Normalizar tipos
    # ======================

    # AÑO
    if 'AÑO' in df.columns:
        df['AÑO'] = pd.to_numeric(df['AÑO'], errors='coerce').astype('Int64')
    else:
        df['AÑO'] = pd.Series([pd.NA] * len(df), dtype="Int64")

    # Flags
    for col in ['CERTIFICADO', 'DESERCION', 'INTERMITENTE']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        else:
            df[col] = 0

    # Strings limpias
    for col in ['CANTON_DEF', 'CURSO', 'CURSO_NORMALIZADO', 'EDAD_CLASIFICADA', 'SEXO_NORMALIZADO']:
        if col in df.columns:
            df[col] = df[col].fillna('Sin dato').astype(str).str.strip()
        else:
            df[col] = 'Sin dato'

    # CURSO_NORMALIZADO por si faltara
    if 'CURSO_NORMALIZADO' not in df.columns or (df['CURSO_NORMALIZADO'] == '').all():
        df['CURSO_NORMALIZADO'] = df['CURSO'].fillna('').astype(str).str.strip().str.lower()

    return df


@st.cache_data
def cargar_geojson():
    return gpd.read_file(ruta_mapa)


@st.cache_data
def convertir_a_excel(df_to_save):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_to_save.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()


try:
    df = cargar_datos()
except Exception as e:
    st.error(f"Error cargando parquet: {e}")
    st.stop()

try:
    gdf = cargar_geojson()
except Exception as e:
    st.error(f"Error cargando geojson: {e}")
    st.stop()


# ===========================
# SIDEBAR (filtros)
# ===========================

with st.sidebar:
    st.header("Filtros")

    # -------------------
    # CURSOS
    # -------------------
    select_all_cursos = st.checkbox("Seleccionar todos los cursos", value=True)

    cursos_disponibles_raw = sorted(df['CURSO_NORMALIZADO'].dropna().astype(str).str.strip().unique())
    cursos_display = [nombre_amigable.get(c, c.title()) for c in cursos_disponibles_raw]

    if not select_all_cursos:
        seleccion_cursos_display = st.multiselect(
            "Cursos",
            cursos_display,
            default=cursos_display
        )
    else:
        seleccion_cursos_display = None

    # -------------------
    # AÑOS
    # -------------------
    select_all_anios = st.checkbox("Seleccionar todos los años", value=True)

    anios_disponibles = sorted(
        df['AÑO'].dropna().astype(int).unique().tolist()
    )

    if not select_all_anios:
        seleccion_anios = st.multiselect(
            "Años",
            anios_disponibles,
            default=anios_disponibles
        )
    else:
        seleccion_anios = None

    # -------------------
    # CANTONES
    # -------------------
    select_all_cantones = st.checkbox("Seleccionar todos los cantones", value=True)

    cantones_disponibles = sorted(df['CANTON_DEF'].dropna().astype(str).str.strip().unique())

    if not select_all_cantones:
        seleccion_cantones = st.multiselect(
            "Cantones",
            cantones_disponibles,
            default=cantones_disponibles
        )
    else:
        seleccion_cantones = None

    # -------------------
    # FLAGS
    # -------------------
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

    # -------------------
    # EDAD
    # -------------------
    st.markdown("---")
    select_all_edades = st.checkbox("Seleccionar todos los grupos de edad", value=True)

    edades_disponibles = sorted(df['EDAD_CLASIFICADA'].dropna().astype(str).str.strip().unique())

    if not select_all_edades:
        seleccion_edades = st.multiselect(
            "Edad",
            edades_disponibles,
            default=edades_disponibles
        )
    else:
        seleccion_edades = None

    # -------------------
    # SEXO
    # -------------------
    select_all_sexos = st.checkbox("Seleccionar todos los sexos", value=True)

    sexos_disponibles = sorted(df['SEXO_NORMALIZADO'].dropna().astype(str).str.strip().unique())

    if not select_all_sexos:
        seleccion_sexos = st.multiselect(
            "Sexo",
            sexos_disponibles,
            default=sexos_disponibles
        )
    else:
        seleccion_sexos = None


# ===========================
# RESOLVER SELECCIONES
# ===========================

# Cursos: convertir desde nombre visible a valor real
if seleccion_cursos_display is None:
    cursos_filtrados = list(cursos_disponibles_raw)
else:
    cursos_filtrados = []

    for raw, disp in zip(cursos_disponibles_raw, cursos_display):
        if disp in seleccion_cursos_display:
            cursos_filtrados.append(raw)

if seleccion_anios is None:
    anios_filtrados = anios_disponibles
else:
    anios_filtrados = seleccion_anios

if seleccion_cantones is None:
    cantones_filtrados = cantones_disponibles
else:
    cantones_filtrados = seleccion_cantones

if seleccion_edades is None:
    edades_filtradas = edades_disponibles
else:
    edades_filtradas = seleccion_edades

if seleccion_sexos is None:
    sexos_filtrados = sexos_disponibles
else:
    sexos_filtrados = seleccion_sexos


# ===========================
# FILTRADO
# ===========================

mask = pd.Series(True, index=df.index)

if cursos_filtrados:
    mask &= df['CURSO_NORMALIZADO'].isin(cursos_filtrados)

if anios_filtrados:
    mask &= df['AÑO'].isin(anios_filtrados)

if cantones_filtrados:
    mask &= df['CANTON_DEF'].isin(cantones_filtrados)

if edades_filtradas:
    mask &= df['EDAD_CLASIFICADA'].isin(edades_filtradas)

if sexos_filtrados:
    mask &= df['SEXO_NORMALIZADO'].isin(sexos_filtrados)

# Flags (OR entre seleccionadas)
if not select_all_flags:
    mask_flag = pd.Series(False, index=df.index)

    if flag_cert:
        mask_flag |= (df['CERTIFICADO'] == 1)
    if flag_des:
        mask_flag |= (df['DESERCION'] == 1)
    if flag_int:
        mask_flag |= (df['INTERMITENTE'] == 1)

    if not (flag_cert or flag_des or flag_int):
        mask &= False
    else:
        mask &= mask_flag

df_filtrado = df[mask].copy()


# ===========================
# MAPA Y RESÚMENES
# ===========================

df_cantonal, df_detalle = preparar_datos_resumen(df_filtrado)

gdf_para_mapa, gdf_merged = preparar_gdf_mapa(gdf, df_cantonal, columna_mapa)

max_val = int(gdf_merged['cantidad_color'].max() or 0)
colormap, color_cero = crear_colormap(max_val)

st.subheader("🗺️ Mapa")

m = crear_mapa_folium(
    gdf_para_mapa=gdf_para_mapa,
    columna_mapa=columna_mapa,
    colormap=colormap,
    color_cero=color_cero,
    select_all_cantones=select_all_cantones,
    cantones_seleccionados=cantones_filtrados
)

st_folium(m, width=950, height=620, returned_objects=[])


# ===========================
# DETALLE SIN DATO
# ===========================

df_sin_dato = df_filtrado[df_filtrado['CANTON_DEF'].fillna('Sin dato') == "Sin dato"]
total_sin_dato = len(df_sin_dato)

if total_sin_dato > 0:
    with st.expander(f"ℹ️ Observaciones 'Sin dato' (fuera del mapa): {total_sin_dato} personas"):
        detalles_sin_dato = df_detalle[df_detalle['CANTON_DEF'] == "Sin dato"]

        if detalles_sin_dato.empty:
            st.write("No se encontró detalle para las observaciones 'Sin dato'.")
        else:
            st.markdown("**Detalle por curso y año:**")
            for _, d in detalles_sin_dato.iterrows():
                curso = nombre_amigable.get(d['CURSO_NORMALIZADO'], str(d['CURSO_NORMALIZADO']).title())
                anio = d['AÑO'] if pd.notna(d['AÑO']) else 'ND'
                st.write(f"- {curso} ({anio}): {d['conteo']} personas")


# ===========================
# ESTADÍSTICAS
# ===========================

st.subheader("📊 Estadísticas Descriptivas")

if df_filtrado.empty:
    st.info("No hay datos con los filtros seleccionados.")
else:
    # Resumen por curso
    st.subheader("Resumen por Curso")
    resumen_curso = df_filtrado.groupby(['CURSO_NORMALIZADO', 'CERTIFICADO']).size().unstack(fill_value=0)
    resumen_curso['Total'] = resumen_curso.sum(axis=1)
    resumen_curso['% Certificado'] = (
        resumen_curso.get(1, 0) / resumen_curso['Total']
    ).replace([np.inf, -np.inf, np.nan], 0) * 100
    resumen_curso = resumen_curso.rename(index=nombre_amigable)
    st.dataframe(resumen_curso, use_container_width=True)

    # Resumen por cantón
    st.subheader("Resumen por Cantón")
    resumen_canton = df_filtrado.groupby(['CANTON_DEF', 'CERTIFICADO']).size().unstack(fill_value=0)
    resumen_canton['Total'] = resumen_canton.sum(axis=1)
    resumen_canton['% Certificado'] = (
        resumen_canton.get(1, 0) / resumen_canton['Total']
    ).replace([np.inf, -np.inf, np.nan], 0) * 100
    st.dataframe(resumen_canton, use_container_width=True)

    # Línea por año
    st.subheader("Gráfico de Línea por Año")
    df_anual_filtrado = df_filtrado.dropna(subset=['AÑO']).copy()

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
                + df_temp['AÑO'].astype(str)
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
