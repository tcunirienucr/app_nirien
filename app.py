import io
import time
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
import geopandas as gpd
from streamlit_folium import st_folium

from src.config import RUTA_MAPA_REPO, RUTA_PARQUET_REPO
from src.transform import preparar_datos_resumen
from src.mapas import preparar_gdf_mapa, crear_colormap, crear_mapa_folium
from src.tablas_maestras import construir_tabla_maestra, exportar_tabla_maestra_excel, construir_panel_exportacion, obtener_etiquetas_disponibles, aplanar_tabla_maestra

st.set_page_config(layout='wide', page_title='Mapa y Estadísticas — TCU Nirien')

ruta_mapa = str(RUTA_MAPA_REPO)
ruta_data = str(RUTA_PARQUET_REPO)
columna_mapa = 'CANTÓN'

nombre_amigable = {
    'admision': 'Admisión y lógica', 'admisión': 'Admisión y lógica', 'eplve': 'Economía para la vida',
    'eplvim': 'Economía para la vida: indicadores macroeconómicos', 'eplvmys': 'Economía para la Vida: mercado y sociedad',
    'excel': 'Excel', 'excelbasico': 'Excel básico', 'excelintermedio': 'Excel intermedio', 'redaccion': 'Redacción Consciente'
}
etiquetas_dimensiones = {'CANTON_FINAL': 'Cantón','AÑO': 'Año','CURSO': 'Curso','CONVOCATORIA': 'Convocatoria','SEXO_MAESTRO': 'Sexo','CONDICION_CURSO': 'Condición del curso'}
filas_permitidas = ['CANTON_FINAL', 'AÑO', 'CURSO', 'CONVOCATORIA']
columnas_permitidas = ['SEXO_MAESTRO', 'CONDICION_CURSO']

st.markdown("""<style>
.block-container {padding-top: 1.4rem; padding-bottom: 1.5rem;}
.kpi-card {background:#f7fbfc; padding:0.8rem 1rem; border-radius:14px; border:1px solid #d9eef2;}
.small-note {color:#5b6572; font-size:0.9rem;}
</style>""", unsafe_allow_html=True)

st.title('📊 TCU Nirien — Panel interactivo')
st.caption('Panel de monitoreo territorial, estadístico y exportación avanzada')

def columna_canton_activa(df_local):
    return 'CANTON_FINAL' if 'CANTON_FINAL' in df_local.columns else 'CANTON_DEF'

def columna_sexo_activa(df_local):
    if 'SEXO_FINAL' in df_local.columns: return 'SEXO_FINAL'
    if 'SEXO_NORMALIZADO' in df_local.columns: return 'SEXO_NORMALIZADO'
    return 'SEXO'

@st.cache_data
def cargar_datos():
    df = pd.read_parquet(ruta_data)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    if 'AÑO' in df.columns: df['AÑO'] = pd.to_numeric(df['AÑO'], errors='coerce').astype('Int64')
    else: df['AÑO'] = pd.Series([pd.NA] * len(df), dtype='Int64')
    for col in ['CERTIFICADO', 'DESERCION', 'INTERMITENTE', 'BENEFICIARIO']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int) if col in df.columns else 0
    for col in ['CANTON_FINAL','CANTON_DEF','CURSO','CURSO_NORMALIZADO','SEXO_FINAL','SEXO_NORMALIZADO','CONVOCATORIA','EDICION']:
        if col in df.columns: df[col] = df[col].fillna('Sin dato').astype(str).str.strip()
    if 'CURSO_NORMALIZADO' not in df.columns or (df['CURSO_NORMALIZADO'] == '').all():
        df['CURSO_NORMALIZADO'] = df['CURSO'].fillna('').astype(str).str.strip().str.lower()
    col_sexo = columna_sexo_activa(df)
    df[col_sexo] = df[col_sexo].replace({'NR': 'Sexo', 'Sin dato': 'Sexo', '': 'Sexo', 'nan': 'Sexo', 'None': 'Sexo'})
    if 'SEXO_FINAL' in df.columns: df['SEXO_FINAL'] = df[col_sexo]
    if 'SEXO_NORMALIZADO' in df.columns: df['SEXO_NORMALIZADO'] = df[col_sexo]
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

def construir_popup_por_canton(df_local):
    col_canton = columna_canton_activa(df_local)
    col_sexo = columna_sexo_activa(df_local)
    resumen = {}
    for canton, sub in df_local.groupby(col_canton):
        cursos = sub['CURSO'].astype(str).str.lower().map(nombre_amigable).fillna(sub['CURSO']).value_counts().to_dict()
        anios = sub['AÑO'].astype(str).value_counts().to_dict()
        sexos = sub[col_sexo].fillna('Sexo').replace({'NR': 'Sexo', 'Sin dato': 'Sexo'}).value_counts().to_dict()
        html = f"<div style='font-size:13px'><b>{canton}</b><br><br>"
        html += "<b>Curso</b><br>" + "<br>".join([f"{k}: {v}" for k, v in cursos.items()]) + "<br><br>"
        html += "<b>Año</b><br>" + "<br>".join([f"{k}: {v}" for k, v in anios.items()]) + "<br><br>"
        html += "<b>Sexo</b><br>" + "<br>".join([f"{k}: {v}" for k, v in sexos.items()]) + "</div>"
        resumen[canton] = html
    return resumen

try:
    df = cargar_datos()
    gdf = cargar_geojson()
except Exception as e:
    st.error(f'Error cargando datos o geojson: {e}')
    st.stop()

meta1, meta2 = st.columns([2,3])
with meta1:
    if '__HOJA_ORIGEN__' in df.columns: st.caption(f"Hoja origen: {df['__HOJA_ORIGEN__'].iloc[0]}")
with meta2:
    if '__FECHA_ETL__' in df.columns: st.caption(f"Última actualización ETL: {df['__FECHA_ETL__'].iloc[0]}")

with st.sidebar:
    st.header('Filtros globales')
    mostrar_tiempos = st.checkbox('Mostrar tiempos de ejecución', value=False)
    universo_visible = st.radio('Población', ['Todos', 'Beneficiarios'], horizontal=False)
    universo_global = 'todos' if universo_visible == 'Todos' else 'beneficiarios'
    df_base_app = df[df['BENEFICIARIO'] == 1].copy() if universo_global == 'beneficiarios' else df.copy()
    st.markdown('---')
    select_all_cursos = st.checkbox('Seleccionar todos los cursos', value=True)
    cursos_raw = sorted(df_base_app['CURSO_NORMALIZADO'].dropna().astype(str).str.strip().unique())
    cursos_display = [nombre_amigable.get(c, c.title()) for c in cursos_raw]
    seleccion_cursos_display = None if select_all_cursos else st.multiselect('Cursos', cursos_display, default=cursos_display)
    select_all_anios = st.checkbox('Seleccionar todos los años', value=True)
    anios_disp = sorted(df_base_app['AÑO'].dropna().astype(int).unique().tolist())
    seleccion_anios = None if select_all_anios else st.multiselect('Años', anios_disp, default=anios_disp)
    select_all_cantones = st.checkbox('Seleccionar todos los cantones', value=True)
    cantones_disp = sorted(df_base_app[columna_canton_activa(df_base_app)].dropna().astype(str).str.strip().unique())
    seleccion_cantones = None if select_all_cantones else st.multiselect('Cantones', cantones_disp, default=cantones_disp)
    st.markdown('---')
    select_all_flags = st.checkbox('Seleccionar todos los estados (CERTIFICADO / DESERCION / INTERMITENTE)', value=True)
    if not select_all_flags:
        flag_cert = st.checkbox('CERTIFICADO == 1', value=True)
        flag_des = st.checkbox('DESERCION == 1', value=False)
        flag_int = st.checkbox('INTERMITENTE == 1', value=False)
    else:
        flag_cert = flag_des = flag_int = True
    st.markdown('---')
    select_all_sexos = st.checkbox('Seleccionar todos los sexos', value=True)
    sexos_disp = sorted(df_base_app[columna_sexo_activa(df_base_app)].dropna().astype(str).str.strip().unique())
    seleccion_sexos = None if select_all_sexos else st.multiselect('Sexo', sexos_disp, default=sexos_disp)

cursos_filtrados = list(cursos_raw) if seleccion_cursos_display is None else [raw for raw, disp in zip(cursos_raw, cursos_display) if disp in seleccion_cursos_display]
anios_filtrados = anios_disp if seleccion_anios is None else seleccion_anios
cantones_filtrados = cantones_disp if seleccion_cantones is None else seleccion_cantones
sexos_filtrados = sexos_disp if seleccion_sexos is None else seleccion_sexos

mask = pd.Series(True, index=df_base_app.index)
if cursos_filtrados: mask &= df_base_app['CURSO_NORMALIZADO'].isin(cursos_filtrados)
if anios_filtrados: mask &= df_base_app['AÑO'].isin(anios_filtrados)
if cantones_filtrados: mask &= df_base_app[columna_canton_activa(df_base_app)].isin(cantones_filtrados)
if sexos_filtrados: mask &= df_base_app[columna_sexo_activa(df_base_app)].isin(sexos_filtrados)
if not select_all_flags:
    mask_flag = pd.Series(False, index=df_base_app.index)
    if flag_cert: mask_flag |= (df_base_app['CERTIFICADO'] == 1)
    if flag_des: mask_flag |= (df_base_app['DESERCION'] == 1)
    if flag_int: mask_flag |= (df_base_app['INTERMITENTE'] == 1)
    mask &= mask_flag if (flag_cert or flag_des or flag_int) else False

df_filtrado = df_base_app[mask].copy()

c1, c2, c3, c4 = st.columns(4)
c1.markdown(f"<div class='kpi-card'><b>Personas</b><br><span style='font-size:1.6rem'>{len(df_filtrado)}</span></div>", unsafe_allow_html=True)
c2.markdown(f"<div class='kpi-card'><b>Beneficiarios</b><br><span style='font-size:1.6rem'>{int((df_filtrado['BENEFICIARIO'] == 1).sum())}</span></div>", unsafe_allow_html=True)
pct = 100 * df_filtrado['CERTIFICADO'].mean() if len(df_filtrado) else 0
c3.markdown(f"<div class='kpi-card'><b>% Certificado</b><br><span style='font-size:1.6rem'>{pct:.1f}%</span></div>", unsafe_allow_html=True)
c4.markdown(f"<div class='kpi-card'><b>Cantones</b><br><span style='font-size:1.6rem'>{df_filtrado[columna_canton_activa(df_filtrado)].nunique() if len(df_filtrado) else 0}</span></div>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(['🗺️ Mapa', '📊 Indicadores', '🧮 Tabla maestra', '📥 Descargas'])

df_cantonal, df_detalle = preparar_datos_resumen(df_filtrado)
popup_dict = construir_popup_por_canton(df_filtrado) if len(df_filtrado) else {}
gdf_para_mapa, gdf_merged = preparar_gdf_mapa(gdf, df_cantonal, columna_mapa)
if popup_dict: gdf_para_mapa['popup_html'] = gdf_para_mapa[columna_mapa].map(popup_dict).fillna('Sin detalle disponible')
max_val = int(gdf_merged['cantidad_color'].max() or 0)
colormap, color_cero = crear_colormap(max_val)

with tab1:
    st.subheader('Mapa interactivo por cantón')
    st.caption('Haz clic en un cantón para ver el detalle por curso, año y sexo.')
    m = crear_mapa_folium(gdf_para_mapa, columna_mapa, colormap, color_cero, select_all_cantones, cantones_filtrados)
    bounds = gdf.total_bounds
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    st_folium(m, width=980, height=650, returned_objects=[])

with tab2:
    st.subheader('Indicadores y resúmenes')
    if df_filtrado.empty:
        st.info('No hay datos con los filtros seleccionados.')
    else:
        ca, cb = st.columns(2)
        with ca:
            st.markdown('#### Resumen por curso')
            resumen_curso = df_filtrado.groupby(['CURSO_NORMALIZADO', 'CERTIFICADO']).size().unstack(fill_value=0)
            resumen_curso['Total'] = resumen_curso.sum(axis=1)
            resumen_curso['% Certificado'] = (resumen_curso.get(1, 0) / resumen_curso['Total']).replace([np.inf, -np.inf, np.nan], 0) * 100
            resumen_curso = resumen_curso.rename(index=nombre_amigable)
            st.dataframe(resumen_curso, width='stretch')
        with cb:
            st.markdown('#### Resumen por cantón')
            col_canton = columna_canton_activa(df_filtrado)
            resumen_canton = df_filtrado.groupby([col_canton, 'CERTIFICADO']).size().unstack(fill_value=0)
            resumen_canton['Total'] = resumen_canton.sum(axis=1)
            resumen_canton['% Certificado'] = (resumen_canton.get(1, 0) / resumen_canton['Total']).replace([np.inf, -np.inf, np.nan], 0) * 100
            st.dataframe(resumen_canton, width='stretch')
        st.markdown('#### Evolución de la certificación por año')
        df_anual = df_filtrado.dropna(subset=['AÑO']).groupby(['AÑO', 'CERTIFICADO']).size().unstack(fill_value=0)
        if not df_anual.empty:
            df_anual['Total'] = df_anual.sum(axis=1)
            df_anual['% Certificado'] = (df_anual.get(1,0)/df_anual['Total']).replace([np.inf,-np.inf,np.nan],0)*100
            fig = px.line(df_anual.reset_index(), x='AÑO', y='% Certificado', title='Evolución de la certificación', labels={'AÑO':'Año','% Certificado':'% Certificado'})
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader('Tabla resumen maestra')
    st.markdown("<div class='small-note'>La vista en Streamlit respeta el orden de selección. El Excel exportado se reordena automáticamente al formato canónico profesional.</div>", unsafe_allow_html=True)
    tc1, tc2 = st.columns([1.7,1.7])
    with tc1:
        row_dims_visible = st.multiselect('Dimensiones verticales', options=filas_permitidas, format_func=lambda x: etiquetas_dimensiones.get(x,x), default=['CANTON_FINAL'])
    with tc2:
        col_dims_visible = st.multiselect('Dimensiones horizontales', options=columnas_permitidas, format_func=lambda x: etiquetas_dimensiones.get(x,x), default=['SEXO_MAESTRO','CONDICION_CURSO'])
    if len(row_dims_visible)==0:
        st.warning('Debes seleccionar al menos una dimensión vertical.')
    elif len(col_dims_visible)==0:
        st.warning('Debes seleccionar al menos una dimensión horizontal.')
    else:
        etiquetas = obtener_etiquetas_disponibles(df_filtrado)
        with st.expander('🔎 Etiquetas disponibles según los filtros actuales', expanded=False):
            mapa_keys = {'CANTON_FINAL':'cantones_disponibles','AÑO':'anios_disponibles','CURSO':'cursos_disponibles','CONVOCATORIA':'convocatorias_disponibles','SEXO_MAESTRO':'sexos_disponibles','CONDICION_CURSO':'condiciones_disponibles'}
            for dim in row_dims_visible + col_dims_visible:
                vals = etiquetas.get(mapa_keys.get(dim,''),[])
                st.write(f"**{etiquetas_dimensiones.get(dim, dim)}** ({len(vals)}): {vals}")
        tabla_maestra = construir_tabla_maestra(df_filtrado, row_dims_visible, col_dims_visible, universo_global, True, True, False)
        st.dataframe(aplanar_tabla_maestra(tabla_maestra), width='stretch')
        tabla_export = construir_tabla_maestra(df_filtrado, row_dims_visible, col_dims_visible, universo_global, True, True, True)
        row_export = [d for d in ['CANTON_FINAL','AÑO','CURSO','CONVOCATORIA'] if d in row_dims_visible]
        col_export = [d for d in ['SEXO_MAESTRO','CONDICION_CURSO'] if d in col_dims_visible]
        panel_export = construir_panel_exportacion(df_filtrado, universo_global)
        if st.button('Preparar Excel de la tabla maestra'):
            archivo = exportar_tabla_maestra_excel(tabla_export, panel_export, row_export, col_export)
            st.download_button('📥 Descargar tabla maestra en Excel', archivo, file_name=f'tabla_maestra_{universo_global}.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

with tab4:
    st.subheader('Descargas')
    if not df_filtrado.empty and st.button('Preparar Excel filtrado'):
        archivo = convertir_a_excel(df_filtrado)
        st.download_button('📥 Descargar datos filtrados en Excel', archivo, file_name='datos_filtrados.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    elif df_filtrado.empty:
        st.warning('No hay datos filtrados para descargar.')
