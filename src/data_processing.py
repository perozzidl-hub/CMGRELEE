import pandas as pd
import numpy as np
import streamlit as st

@st.cache_data
def load_and_transform_data(uploaded_file):
    excel = pd.ExcelFile(uploaded_file)
    
    # 1. Carga y Limpieza de Hojas
    # VENTA
    df_venta = pd.read_excel(excel, sheet_name='VENTA')
    if 'Material' in df_venta.iloc[0].values:
        df_venta.columns = df_venta.iloc[0]
        df_venta = df_venta.iloc[1:].reset_index(drop=True)
    
    df_venta['Fe.Liquidación'] = pd.to_datetime(df_venta['Fe.Liquidación'])
    df_venta['Mes'] = df_venta['Fe.Liquidación'].dt.to_period('M').dt.to_timestamp()
    df_venta['Cod. Venta'] = pd.to_numeric(df_venta['Material'], errors='coerce')
    df_venta['Cantidad_Fisica'] = pd.to_numeric(df_venta['Suma de SUMA_CF'], errors='coerce').fillna(0)
    df_venta['Facturacion_Neta'] = pd.to_numeric(df_venta['Suma de Facturación Neta'], errors='coerce').fillna(0)
    
    # Maestro Artículos
    df_maestro = pd.read_excel(excel, sheet_name='Maestro Artículos', header=1)
    df_maestro.columns = df_maestro.iloc[0]
    df_maestro = df_maestro.iloc[1:].reset_index(drop=True)
    df_maestro['Cod. Venta'] = pd.to_numeric(df_maestro['Cod. Venta'], errors='coerce')
    
    # Receta (Agrupada por Mes y Cod. Venta)
    df_receta = pd.read_excel(excel, sheet_name='Receta')
    df_receta['Mes'] = pd.to_datetime(df_receta['Mes'])
    df_receta['Cod. Venta'] = pd.to_numeric(df_receta['Cod. Venta'], errors='coerce')
    receta_agg = df_receta.groupby(['Mes', 'Cod. Venta']).agg(
        costo_receta_std=('Costo Estándar ($)', 'sum'),
        costo_desp_operativo=('Desperdicio PT ($)', 'sum')
    ).reset_index()

    # Mano de Obra (MO)
    df_mo = pd.read_excel(excel, sheet_name='MO', header=1).dropna(how='all')
    df_mo['Mes'] = pd.to_datetime(df_mo['Mes'])
    df_mo['Cod. Venta'] = pd.to_numeric(df_mo['Cod. Venta'], errors='coerce')
    df_mo['mo_unitario_total'] = (
        pd.to_numeric(df_mo['Mano de Obra Directa'], errors='coerce').fillna(0) +
        pd.to_numeric(df_mo['Mano de Obra Indirecta'], errors='coerce').fillna(0) +
        pd.to_numeric(df_mo['Electricidad / Gas'], errors='coerce').fillna(0) +
        pd.to_numeric(df_mo['Repuestos y Lubricación'], errors='coerce').fillna(0)
    )

    # Datos por Locación
    df_loc = pd.read_excel(excel, sheet_name='DatosxLocacion', header=1)
    df_loc.columns = df_loc.iloc[0]
    df_loc = df_loc.iloc[1:].reset_index(drop=True)
    df_loc['Mes'] = pd.to_datetime(df_loc['Mes'])

    # Fletes T0
    df_flete = pd.read_excel(excel, sheet_name='FletesT0', header=1).dropna(how='all')
    df_flete['Mes'] = pd.to_datetime(df_flete['Mes'])
    df_flete['Cod. Venta'] = pd.to_numeric(df_flete['Cod. Venta'], errors='coerce')
    df_flete['flete_t0_unitario'] = pd.to_numeric(df_flete['Flete T0 (Prod. Comprado)'], errors='coerce').fillna(0)

    # 2. Joins a la Tabla de Hechos (VENTA)
    df = df_venta.merge(df_maestro, on='Cod. Venta', how='left')
    df = df.merge(receta_agg, on=['Mes', 'Cod. Venta'], how='left')
    df = df.merge(df_mo[['Mes', 'Cod. Venta', 'mo_unitario_total']], on=['Mes', 'Cod. Venta'], how='left')
    df = df.merge(df_loc, on=['Mes', 'Locación'], how='left')
    df = df.merge(df_flete[['Mes', 'Cod. Venta', 'flete_t0_unitario']], on=['Mes', 'Cod. Venta'], how='left')

    # Relleno de Nulos
    cols_fill = [
        'costo_receta_std', 'costo_desp_operativo', 'mo_unitario_total', 'flete_t0_unitario',
        'Mano de Obra Warehouse', 'Tasa Seguridad e Higiene ($)', 'Impuestos a los Créditos/Débitos',
        'Flete T1 (Interdeposito)', 'Comisiones x Bulto de Fletes', 'Comisiones de Ventas ( en Fisicos)',
        'Desperdicio Concentrado', 'Impuesto a los Ingresos Brutos'
    ]
    for c in cols_fill:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    # 3. Aplicación de la Regla de Oro y Cálculo de Costos
    cant = df['Cantidad_Fisica']
    fact_neta = df['Facturacion_Neta']
    es_propio = df['Tipo de Prod.'] == 'P'
    es_reventa = df['Tipo de Prod.'] == 'R'

    # Costo Materia Prima e Insumos
    df['costo_materia_prima'] = 0.0
    # Propios (P): Receta Estándar ($) + Concentrado Variable (% sobre Facturación Neta)
    df.loc[es_propio, 'costo_materia_prima'] = (
        (df.loc[es_propio, 'costo_receta_std'] * cant.loc[es_propio]) +
        (df.loc[es_propio, 'Desperdicio Concentrado'] * fact_neta.loc[es_propio])
    )
    # Reventa (R): Costo Compra / Receta
    df.loc[es_reventa, 'costo_materia_prima'] = df.loc[es_reventa, 'costo_receta_std'] * cant.loc[es_reventa]

    # Desperdicio Operativo ($ * Unidades)
    df['costo_desp_operativo_total'] = df['costo_desp_operativo'] * cant

    # Flete T0 ($ * Unidades)
    df['costo_flete_t0_total'] = np.where(es_reventa, df['flete_t0_unitario'] * cant, 0.0)

    # Mano de Obra ($ * Unidades)
    df['costo_mo_total'] = df['mo_unitario_total'] * cant

    # Costos Locativos y Estructura
    df['costo_warehouse_total'] = df['Mano de Obra Warehouse'] * cant
    df['costo_flete_t1_total'] = df['Flete T1 (Interdeposito)'] * cant
    df['costo_comisiones_flete'] = df['Comisiones x Bulto de Fletes'] * cant
    df['costo_comisiones_ventas'] = df['Comisiones de Ventas ( en Fisicos)'] * cant

    # Impuestos en % sobre Facturación Neta
    pct_impuestos = df['Tasa Seguridad e Higiene ($)'] + df['Impuestos a los Créditos/Débitos'] + df['Impuesto a los Ingresos Brutos']
    df['costo_impuestos_total'] = pct_impuestos * fact_neta

    # Costo Total Consolidad
    df['costo_total'] = (
        df['costo_materia_prima'] +
        df['costo_desp_operativo_total'] +
        df['costo_flete_t0_total'] +
        df['costo_mo_total'] +
        df['costo_warehouse_total'] +
        df['costo_flete_t1_total'] +
        df['costo_comisiones_flete'] +
        df['costo_comisiones_ventas'] +
        df['costo_impuestos_total']
    )

    # Contribución Marginal
    df['contribucion_marginal'] = df['Facturacion_Neta'] - df['costo_total']
    df['cm_porcentual'] = np.where(df['Facturacion_Neta'] > 0, df['contribucion_marginal'] / df['Facturacion_Neta'], 0.0)

    return df
