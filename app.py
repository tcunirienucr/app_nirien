import io
import time

import streamlit as st
import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.express as px

from streamlit_folium import st_folium

from src.transform import preparar_datos_resumen
from src.mapas import preparar_gdf_mapa, crear_colormap, crear_mapa_folium
from src.tablas_maestras import (
    construir_tabla_maestra,
    exportar_tabla_maestra_excel,
    construir_panel_exportacion,
    obtener_etiquetas_disponibles,
)


# ===========================
# CONFIG
# ===========================

st.set_page_config(layout="wide", page_title="Mapa y Estadísticas — TCU Nirien")

ruta_mapa = "data/limitecantonal_5k_lite.geojson"
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

etiquetas_dimensiones = {
    "CANTON_FINAL": "Cantón",
    "AÑO": "Año",
    "CURSO": "Curso",
    "CONVOCATORIA": "Convocatoria",
    "SEXO_MAESTRO": "Sexo",
    "CONDICION_CURSO": "Condición del curso"
}

filas_permitidas = ["CANTON_FINAL", "AÑO", "CURSO", "CONVOCATORIA"]
columnas_permitidas = ["SEXO_MAESTRO", "CONDICION_CURSO"]

st.title("📊 Mapa y Estadísticas — TCU Nirien")


# ===========================
# UTILIDAD PARA TIEMPOS
# ===========================

def iniciar_timer():
    return time.perf_counter()


def cerrar_timer(t0):
    return round(time.perf_counter() - t0, 4)


tiempos = {}


# ===========================
# HELPERS
# ===========================

def columna_canton_activa(df_local: pd.DataFrame) -> str:
    """
    Mientras el parquet todavía no traiga CANTON_FINAL, usamos fallback a CANTON_DEF.
    En el siguiente paso del ETL esto se corregirá definitivamente.
    """
    if "CANTON_FINAL" in df_local.columns:
        return "CANTON_FINAL"
    if "CANTON_DEF" in df_local.columns:
        return "CANTON_DEF"
    raise KeyError("No existe ni CANTON_FINAL ni CANTON_DEF en el parquet.")


# ===========================
# CARGA DE DATOS
# ===========================

@st.cache_data
def cargar_datos():
    df = pd.read_parquet(ruta_data)

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
    for col in [
        'CANTON_FINAL',
        'CANTON_DEF',
        'CURSO',
        'CURSO_NORMALIZADO',
        'EDAD_CLASIFICADA',
        'SEXO_NORMALIZADO',
        'CONVOCATORIA'
    ]:
        if col in df.columns:
            df[col] = df[col].fillna('Sin dato').astype(str).str.strip()

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


# ===========================
# EJECUCIÓN CON MEDICIÓN
# ===========================

t0 = iniciar_timer()
try:
    df = cargar_datos()
    tiempos["1. cargar_datos()"] = cerrar_timer(t0)
except Exception as e:
    st.error(f"Error cargando parquet: {e}")
    st.stop()

t0 = iniciar_timer()
try:
    gdf = cargar_geojson()
    tiempos["2. cargar_geojson()"] = cerrar_timer(t0)
except Exception as e:
    st.error(f"Error cargando geojson: {e}")
    st.stop()


# ===========================
# METADATA DE FUENTE
# ===========================

col_meta1, col_meta2 = st.columns([2, 3])

with col_meta1:
    if "__HOJA_ORIGEN__" in df.columns:
        st.caption(f"Hoja origen: {df['__HOJA_ORIGEN__'].iloc[0]}")

with col_meta2:
    if "__FECHA_ETL__" in df.columns:
        st.caption(f"Última actualización ETL: {df['__FECHA_ETL__'].iloc[0]}")


# ===========================
# SIDEBAR (filtros globales)
# ===========================

with st.sidebar:
    st.header("Filtros globales")

    mostrar_tiempos = st.checkbox("Mostrar tiempos de ejecución", value=False)

    # Cursos
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

    # Años
    select_all_anios = st.checkbox("Seleccionar todos los años", value=True)
    anios_disponibles = sorted(df['AÑO'].dropna().astype(int).unique().tolist())

    if not select_all_anios:
        seleccion_anios = st.multiselect(
            "Años",
            anios_disponibles,
            default=anios_disponibles
        )
    else:
        seleccion_anios = None

    # Cantones
    select_all_cantones = st.checkbox("Seleccionar todos los cantones", value=True)
    col_canton_sidebar = columna_canton_activa(df)
    cantones_disponibles = sorted(df[col_canton_sidebar].dropna().astype(str).str.strip().unique())

    if not select_all_cantones:
        seleccion_cantones = st.multiselect(
            "Cantones",
            cantones_disponibles,
            default=cantones_disponibles
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

    # Sexo
    st.markdown("---")
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
# RESOLVER SELECCIONES GLOBALES
# ===========================

t0 = iniciar_timer()

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

if seleccion_sexos is None:
    sexos_filtrados = sexos_disponibles
else:
    sexos_filtrados = seleccion_sexos

tiempos["3. resolver selecciones globales"] = cerrar_timer(t0)


# ===========================
# FILTRADO GLOBAL
# ===========================

t0 = iniciar_timer()

mask = pd.Series(True, index=df.index)

if cursos_filtrados:
    mask &= df['CURSO_NORMALIZADO'].isin(cursos_filtrados)

if anios_filtrados:
    mask &= df['AÑO'].isin(anios_filtrados)

if cantones_filtrados:
    mask &= df[columna_canton_activa(df)].isin(cantones_filtrados)

if sexos_filtrados:
    mask &= df['SEXO_NORMALIZADO'].isin(sexos_filtrados)

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

tiempos["4. filtrar dataframe global"] = cerrar_timer(t0)


# ===========================
# MAPA Y RESÚMENES
# ===========================

t0 = iniciar_timer()
df_cantonal, df_detalle = preparar_datos_resumen(df_filtrado)
tiempos["5. preparar_datos_resumen()"] = cerrar_timer(t0)

t0 = iniciar_timer()
gdf_para_mapa, gdf_merged = preparar_gdf_mapa(gdf, df_cantonal, columna_mapa)
tiempos["6. preparar_gdf_mapa()"] = cerrar_timer(t0)

t0 = iniciar_timer()
max_val = int(gdf_merged['cantidad_color'].max() or 0)
colormap, color_cero = crear_colormap(max_val)
tiempos["7. crear_colormap()"] = cerrar_timer(t0)

st.subheader("🗺️ Mapa")

t0 = iniciar_timer()
m = crear_mapa_folium(
    gdf_para_mapa=gdf_para_mapa,
    columna_mapa=columna_mapa,
    colormap=colormap,
    color_cero=color_cero,
    select_all_cantones=select_all_cantones,
    cantones_seleccionados=cantones_filtrados
)

bounds = gdf.total_bounds
m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

tiempos["8. crear_mapa_folium()"] = cerrar_timer(t0)

t0 = iniciar_timer()
st_folium(m, width=950, height=620, returned_objects=[])
tiempos["9. st_folium() render server"] = cerrar_timer(t0)


# ===========================
# DETALLE SIN DATO
# ===========================

t0 = iniciar_timer()

col_canton_actual = columna_canton_activa(df_filtrado)

df_sin_dato = df_filtrado[df_filtrado[col_canton_actual].fillna('Sin dato') == "Sin dato"]
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

tiempos["10. bloque sin dato"] = cerrar_timer(t0)


# ===========================
# ESTADÍSTICAS
# ===========================

t0 = iniciar_timer()

st.subheader("📊 Estadísticas Descriptivas")

if df_filtrado.empty:
    st.info("No hay datos con los filtros seleccionados.")
else:
    st.subheader("Resumen por Curso")
    resumen_curso = df_filtrado.groupby(['CURSO_NORMALIZADO', 'CERTIFICADO']).size().unstack(fill_value=0)
    resumen_curso['Total'] = resumen_curso.sum(axis=1)
    resumen_curso['% Certificado'] = (
        resumen_curso.get(1, 0) / resumen_curso['Total']
    ).replace([np.inf, -np.inf, np.nan], 0) * 100
    resumen_curso = resumen_curso.rename(index=nombre_amigable)
    st.dataframe(resumen_curso, use_container_width=True)

    st.subheader("Resumen por Cantón")
    col_canton_resumen = columna_canton_activa(df_filtrado)
    resumen_canton = df_filtrado.groupby([col_canton_resumen, 'CERTIFICADO']).size().unstack(fill_value=0)
    resumen_canton['Total'] = resumen_canton.sum(axis=1)
    resumen_canton['% Certificado'] = (
        resumen_canton.get(1, 0) / resumen_canton['Total']
    ).replace([np.inf, -np.inf, np.nan], 0) * 100
    st.dataframe(resumen_canton, use_container_width=True)

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

tiempos["11. bloque estadísticas"] = cerrar_timer(t0)


# ===========================
# TABLA MAESTRA
# ===========================

st.subheader("🧮 Tabla resumen maestra")

st.markdown(
    """
    Esta tabla usa el **dataset actualmente filtrado** en la barra lateral y permite:
    - elegir el universo: **Todos** o **Beneficiarios**
    - elegir dimensiones de filas (verticales)
    - elegir dimensiones de columnas (horizontales)
    - descargar el resultado en Excel
    """
)

col_tm_1, col_tm_2, col_tm_3 = st.columns([1.2, 1.8, 1.8])

with col_tm_1:
    universo_visible = st.radio(
        "Universo",
        ["Todos", "Beneficiarios"],
        horizontal=False
    )
    universo_tabla = "todos" if universo_visible == "Todos" else "beneficiarios"

with col_tm_2:
    row_dims_visible = st.multiselect(
        "Dimensiones verticales",
        options=filas_permitidas,
        format_func=lambda x: etiquetas_dimensiones.get(x, x),
        default=["CANTON_FINAL"]
    )

with col_tm_3:
    col_dims_visible = st.multiselect(
        "Dimensiones horizontales",
        options=columnas_permitidas,
        format_func=lambda x: etiquetas_dimensiones.get(x, x),
        default=["SEXO_MAESTRO", "CONDICION_CURSO"]
    )

if len(row_dims_visible) == 0:
    st.warning("Debes seleccionar al menos una dimensión vertical.")
elif len(col_dims_visible) == 0:
    st.warning("Debes seleccionar al menos una dimensión horizontal.")
else:
    try:
        etiquetas_disponibles = obtener_etiquetas_disponibles(df_filtrado)

        with st.expander("🔎 Etiquetas disponibles según los filtros actuales", expanded=False):
            for dim in row_dims_visible + col_dims_visible:
                if dim == "CANTON_FINAL":
                    valores = etiquetas_disponibles["cantones_disponibles"]
                elif dim == "AÑO":
                    valores = etiquetas_disponibles["anios_disponibles"]
                elif dim == "CURSO":
                    valores = etiquetas_disponibles["cursos_disponibles"]
                elif dim == "CONVOCATORIA":
                    valores = etiquetas_disponibles["convocatorias_disponibles"]
                elif dim == "SEXO_MAESTRO":
                    valores = etiquetas_disponibles["sexos_disponibles"]
                elif dim == "CONDICION_CURSO":
                    valores = etiquetas_disponibles["condiciones_disponibles"]
                else:
                    valores = []

                st.write(f"**{etiquetas_dimensiones.get(dim, dim)}** ({len(valores)}): {valores}")

    except Exception as e:
        st.info(f"No se pudieron calcular etiquetas disponibles: {e}")

    t0 = iniciar_timer()
    try:
        tabla_maestra = construir_tabla_maestra(
            df_base=df_filtrado,
            row_dims=row_dims_visible,
            col_dims=col_dims_visible,
            universo=universo_tabla,
            incluir_total_fila=True,
            incluir_total_general=True
        )
        tiempos["12. construir_tabla_maestra()"] = cerrar_timer(t0)

        st.markdown("### Vista de la tabla maestra")
        tabla_para_ver = tabla_maestra.reset_index()
        st.dataframe(tabla_para_ver, use_container_width=True)

        panel_export = construir_panel_exportacion(
            df_base=df_filtrado,
            universo=universo_tabla
        )

        st.markdown("### Descargar tabla maestra")
        preparar_excel_tabla = st.button("Preparar Excel de la tabla maestra")

        if preparar_excel_tabla:
            archivo_excel_tabla = exportar_tabla_maestra_excel(
                tabla=tabla_maestra,
                panel_df=panel_export
            )

            st.download_button(
                label="📥 Descargar tabla maestra en Excel",
                data=archivo_excel_tabla,
                file_name=f"tabla_maestra_{universo_tabla}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Error construyendo la tabla maestra: {e}")


# ===========================
# DESCARGAS EXISTENTES
# ===========================

t0 = iniciar_timer()

st.subheader("📥 Descargar Datos Filtrados")

if not df_filtrado.empty:
    preparar_descarga = st.button("Preparar Excel filtrado")

    if preparar_descarga:
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
        df_temp = df_filtrado.dropna(subset=['AÑO']).copy()
        col_canton_colapso = columna_canton_activa(df_temp)
        df_temp = df_temp.dropna(subset=[col_canton_colapso]).copy()

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
                    index=col_canton_colapso,
                    columns='CURSO_AÑO',
                    values='CERTIFICADO',
                    aggfunc='count',
                    fill_value=0
                )
                .reset_index()
            )

            df_pivot['TOTAL'] = df_pivot.drop(columns=col_canton_colapso).sum(axis=1)

            columnas_ordenadas = (
                [col_canton_colapso]
                + sorted([c for c in df_pivot.columns if c not in [col_canton_colapso, 'TOTAL']])
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

tiempos["13. bloque descargas"] = cerrar_timer(t0)


# ===========================
# PANEL DE TIEMPOS
# ===========================

if mostrar_tiempos:
    with st.sidebar.expander("⏱️ Tiempos de ejecución", expanded=True):
        tiempos_df = pd.DataFrame(
            [{"Bloque": k, "Segundos": v} for k, v in tiempos.items()]
        ).sort_values("Segundos", ascending=False)

        st.dataframe(tiempos_df, use_container_width=True)

        total = tiempos_df["Segundos"].sum()
        st.metric("Tiempo total aproximado (backend)", f"{total:.3f} s")
