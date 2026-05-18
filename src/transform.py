import pandas as pd


def preparar_datos_resumen(df_local):
    df_local = df_local.copy()

    df_local['CANTON_DEF'] = df_local['CANTON_DEF'].fillna('Sin dato')

    df_cantonal = (
        df_local
        .groupby('CANTON_DEF')
        .size()
        .reset_index(name='cantidad_beneficiarios')
    )

    df_detalle = (
        df_local
        .groupby(['CANTON_DEF', 'CURSO_NORMALIZADO', 'AÑO'])
        .size()
        .reset_index(name='conteo')
    )

    return df_cantonal, df_detalle