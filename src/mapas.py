import folium
import numpy as np
import branca.colormap as cm


def preparar_gdf_mapa(gdf, df_cantonal, columna_mapa):
    gdf_merged = gdf.merge(df_cantonal, how='left', left_on=columna_mapa, right_on='CANTON_DEF')
    gdf_merged['cantidad_beneficiarios'] = gdf_merged['cantidad_beneficiarios'].fillna(0).astype(int)
    gdf_merged['cantidad_color'] = gdf_merged['cantidad_beneficiarios'].astype(int)
    columnas = ['geometry', columna_mapa, 'cantidad_color']
    if 'popup_html' in gdf_merged.columns:
        columnas.append('popup_html')
    gdf_para_mapa = gdf_merged[[c for c in columnas if c in gdf_merged.columns]].copy()
    return gdf_para_mapa, gdf_merged


def crear_colormap(max_beneficiarios):
    color_cero = '#ece7f2'
    colores_escala = ['#a6bddb', '#74a9cf', '#3690c0', '#0570b0', '#034e7b']
    if max_beneficiarios < 10:
        max_beneficiarios = 10
    try:
        pasos = np.logspace(start=0, stop=np.log10(max_beneficiarios), num=6)
        pasos = [int(round(p)) for p in pasos]
        pasos = sorted(list(set(pasos)))
        if not pasos:
            pasos = [1, 10]
        n = max(1, len(pasos) - 1)
        colores_escala = colores_escala[:n] if n <= len(colores_escala) else colores_escala + [colores_escala[-1]] * (n - len(colores_escala))
    except Exception:
        pasos = [1, 10]
        colores_escala = [colores_escala[0]]
    if len(pasos) < 2:
        pasos = [1, max(2, max_beneficiarios)]
        colores_escala = [colores_escala[0]]
    colormap = cm.StepColormap(colors=colores_escala, index=pasos, vmin=1, vmax=max_beneficiarios, caption='Cantidad de Beneficiarios')
    return colormap, color_cero


def crear_mapa_folium(gdf_para_mapa, columna_mapa, colormap, color_cero, select_all_cantones, cantones_seleccionados, color_no_seleccionado='#D3D3D3'):
    m = folium.Map(location=[9.7489, -83.7534], zoom_start=8, tiles='cartodbpositron')
    def estilo_feature(feature):
        props = feature.get('properties', {})
        canton = props.get(columna_mapa, '')
        cantidad = int(props.get('cantidad_color', 0) or 0)
        if not select_all_cantones and canton not in cantones_seleccionados:
            return {'fillColor': color_no_seleccionado, 'color': 'black', 'weight': 1, 'fillOpacity': 0.25}
        if cantidad == 0:
            return {'fillColor': color_cero, 'color': 'black', 'weight': 1, 'fillOpacity': 0.7}
        return {'fillColor': colormap(cantidad), 'color': 'black', 'weight': 1, 'fillOpacity': 0.7}
    tooltip = folium.GeoJsonTooltip(fields=[columna_mapa, 'cantidad_color'], aliases=['Cantón', 'Beneficiarios'], localize=True)
    def popup_function(feature):
        html = feature['properties'].get('popup_html', '')
        return folium.Popup(html, max_width=350)
    folium.GeoJson(data=gdf_para_mapa.__geo_interface__, style_function=estilo_feature, tooltip=tooltip, popup=popup_function, name='Cantones').add_to(m)
    m.add_child(colormap)
    return m
